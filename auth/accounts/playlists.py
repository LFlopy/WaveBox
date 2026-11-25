import json
from collections import defaultdict, deque

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from sqlalchemy import create_engine, or_, select
from sqlalchemy.orm import Session

from import_tracks import normalize_tag
from models import Artist, Track, TrackEnrichment

from .models import ImportedPlaylist
from .playlist_sources import (
    PlaylistInputError, PlaylistProviderError, canonical_mbid, fetch_listenbrainz, read_playlist_file,
)


def text_key(title, artist):
    return normalize_tag(title).casefold(), normalize_tag(artist).casefold()


def entry_key(entry):
    if entry["recordingMbid"]:
        return (entry["recordingMbid"],)
    return (*text_key(entry["title"], entry["artist"]), entry["durationMs"])


def match_entries(session, entries, previous=()):
    if not entries:
        return []
    recording_keys = {entry["recordingMbid"] for entry in entries if entry["recordingMbid"]}
    text_keys = {text_key(entry["title"], entry["artist"]) for entry in entries if entry["title"] and entry["artist"]}
    manual = defaultdict(deque)
    for entry in previous:
        manual[entry_key(entry)].append(entry["trackId"] if entry["status"] == "manual" else None)
    manual_ids = {value for choices in manual.values() for value in choices if value is not None}

    by_recording, by_tags = defaultdict(list), defaultdict(list)
    available_manual = set()
    catalog = (
        select(Track.id, Track.title, Artist.name, Track.duration_ms, TrackEnrichment.recording_mbid)
        .join(Track.artist).outerjoin(TrackEnrichment).order_by(Track.id)
        .execution_options(yield_per=1000)
    )
    if not text_keys:
        predicates = []
        if recording_keys:
            predicates.append(TrackEnrichment.recording_mbid.in_(recording_keys))
        if manual_ids:
            predicates.append(Track.id.in_(manual_ids))
        catalog = catalog.where(or_(*predicates))
    for track_id, title, artist, duration, recording in session.execute(catalog):
        if track_id in manual_ids:
            available_manual.add(track_id)
        if recording and recording in recording_keys:
            by_recording[recording].append(track_id)
        key = text_key(title, artist)
        if key in text_keys:
            by_tags[key].append((track_id, duration, recording))

    matched = []
    for entry in entries:
        recording = entry["recordingMbid"]
        duration = entry["durationMs"]
        key = entry_key(entry)
        manual_id = manual[key].popleft() if manual[key] else None
        exact = by_recording[recording] if recording else []
        tag_candidates = [
            (track_id, local_duration)
            for track_id, local_duration, local_recording in by_tags[text_key(entry["title"], entry["artist"])]
            if (not recording or not local_recording or local_recording == recording)
            and (duration is None or local_duration is None or abs(duration - local_duration) <= 2000)
        ]
        candidates = exact or [track_id for track_id, _ in tag_candidates]
        confident = bool(exact) or (
            not recording and duration is not None and len(tag_candidates) == 1 and tag_candidates[0][1] is not None
        )
        if manual_id in available_manual:
            status, track_id = "manual", manual_id
        elif len(candidates) == 1 and confident:
            status, track_id = "matched", candidates[0]
        else:
            status, track_id = ("ambiguous" if candidates else "missing"), None
        matched.append({
            **entry, "status": status, "trackId": track_id, "candidateIds": candidates[:20],
        })
    return matched


def match_catalog(entries, previous=()):
    engine = create_engine(settings.MUSIC_DATABASE_URL)
    try:
        with Session(engine) as session:
            return match_entries(session, entries, previous)
    finally:
        engine.dispose()


def serialize(playlist, detail=False):
    result = {
        "id": str(playlist.pk), "source": playlist.source, "name": playlist.name,
        "revision": playlist.revision, "updatedAt": playlist.updated_at.isoformat(),
    }
    if detail:
        result["entries"] = playlist.entries
        result["counts"] = {
            "matched": sum(entry["trackId"] is not None for entry in playlist.entries),
            "ambiguous": sum(entry["status"] == "ambiguous" for entry in playlist.entries),
            "missing": sum(entry["status"] == "missing" for entry in playlist.entries),
        }
    return result


def json_payload(request):
    try:
        data = json.loads(request.body)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise PlaylistInputError("Invalid JSON request.") from exc
    if not isinstance(data, dict):
        raise PlaylistInputError("Expected a JSON object.")
    return data


def source_error(exc):
    if isinstance(exc, PlaylistProviderError):
        headers = {"Retry-After": exc.retry_after} if exc.retry_after else None
        return JsonResponse({"error": str(exc)}, status=exc.status_code, headers=headers)
    return JsonResponse({"error": str(exc)}, status=400)


def update_snapshot(playlist, *, name, entries, source_key=None):
    updated_at = timezone.now()
    values = {"name": name, "entries": entries, "revision": F("revision") + 1, "updated_at": updated_at}
    if source_key is not None:
        values["source_key"] = source_key
    try:
        with transaction.atomic():
            changed = ImportedPlaylist.objects.filter(pk=playlist.pk, revision=playlist.revision).update(**values)
    except IntegrityError:
        if source_key is None or not ImportedPlaylist.objects.filter(
            user_id=playlist.user_id, source=playlist.source, source_key=source_key,
        ).exclude(pk=playlist.pk).exists():
            raise
        return JsonResponse({"error": "This file is already imported as a separate playlist."}, status=409)
    if not changed:
        return JsonResponse({"error": "This playlist changed. Reload it before trying again."}, status=409)
    playlist.name, playlist.entries = name, entries
    playlist.revision += 1
    playlist.updated_at = updated_at
    return JsonResponse(serialize(playlist, detail=True))


@never_cache
@require_http_methods(["GET", "POST"])
def imported_playlists(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Not authenticated."}, status=401)
    playlists = ImportedPlaylist.objects.filter(user=request.user)
    if request.method == "GET":
        return JsonResponse({"playlists": [
            serialize(playlist) for playlist in playlists.defer("entries").order_by("-updated_at", "id")
        ]})

    try:
        if request.content_type == "multipart/form-data":
            source = "file"
            key, name, entries = read_playlist_file(request.FILES.get("file"))
        else:
            data = json_payload(request)
            source = "listenbrainz"
            key = canonical_mbid(data.get("playlistId"))
            if not key:
                raise PlaylistInputError("Enter a valid ListenBrainz playlist UUID.")
            name, entries = fetch_listenbrainz(key, data.get("token", ""))
        existing = playlists.filter(source=source, source_key=key).first()
        if existing:
            return JsonResponse(serialize(existing, detail=True))
        matched = match_catalog(entries)
        playlist, created = ImportedPlaylist.objects.get_or_create(
            user=request.user, source=source, source_key=key, defaults={"name": name, "entries": matched},
        )
        return JsonResponse(serialize(playlist, detail=True), status=201 if created else 200)
    except (PlaylistInputError, PlaylistProviderError) as exc:
        return source_error(exc)


@never_cache
@require_GET
def imported_playlist(request, playlist_id):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Not authenticated."}, status=401)
    playlist = ImportedPlaylist.objects.filter(pk=playlist_id, user=request.user).first()
    if playlist is None:
        return JsonResponse({"error": "Playlist not found."}, status=404)
    return JsonResponse(serialize(playlist, detail=True))


@require_POST
def sync_imported_playlist(request, playlist_id):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Not authenticated."}, status=401)
    playlist = ImportedPlaylist.objects.filter(pk=playlist_id, user=request.user).first()
    if playlist is None:
        return JsonResponse({"error": "Playlist not found."}, status=404)
    try:
        is_file = request.content_type == "multipart/form-data"
        data = request.POST if is_file else json_payload(request)
        revision = data.get("revision")
        if is_file and isinstance(revision, str) and revision.isascii() and revision.isdecimal() and len(revision) <= 10:
            revision = int(revision)
        if type(revision) is not int or revision != playlist.revision:
            return JsonResponse({"error": "This playlist changed. Reload it before trying again."}, status=409)
        name, entries, source_key = playlist.name, playlist.entries, None
        if is_file:
            if playlist.source != "file":
                raise PlaylistInputError("This playlist is managed by ListenBrainz.")
            source_key, name, entries = read_playlist_file(request.FILES.get("file"))
        elif playlist.source == "listenbrainz" and data.get("remote") is True:
            name, entries = fetch_listenbrainz(playlist.source_key, data.get("token", ""))
        matched = match_catalog(entries, playlist.entries)
        return update_snapshot(playlist, name=name, entries=matched, source_key=source_key)
    except (PlaylistInputError, PlaylistProviderError) as exc:
        return source_error(exc)


@require_POST
def resolve_playlist_entry(request, playlist_id):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Not authenticated."}, status=401)
    playlist = ImportedPlaylist.objects.filter(pk=playlist_id, user=request.user).first()
    if playlist is None:
        return JsonResponse({"error": "Playlist not found."}, status=404)
    try:
        data = json_payload(request)
        if type(data.get("revision")) is not int or data["revision"] != playlist.revision:
            return JsonResponse({"error": "This playlist changed. Reload it before trying again."}, status=409)
        index, track_id = data.get("index"), data.get("trackId")
        if type(index) is not int or not 0 <= index < len(playlist.entries) or type(track_id) is not int:
            raise PlaylistInputError("Invalid playlist entry or track.")
        entry = playlist.entries[index]
        actual = match_catalog([entry])[0]
        if track_id not in actual["candidateIds"]:
            raise PlaylistInputError("This track is no longer a candidate.")
        playlist.entries[index] = {**actual, "status": "manual", "trackId": track_id}
        return update_snapshot(playlist, name=playlist.name, entries=playlist.entries)
    except PlaylistInputError as exc:
        return source_error(exc)
