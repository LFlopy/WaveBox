import csv
import hashlib
import http.client
import io
import json
import re
import time
from pathlib import Path
from uuid import UUID

from import_tracks import normalize_tag


MAX_PLAYLIST_SIZE = 1024 * 1024
MAX_PLAYLIST_ENTRIES = 500


class PlaylistInputError(ValueError):
    pass


class PlaylistProviderError(Exception):
    def __init__(self, message, status_code=502, retry_after=None):
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after


def canonical_mbid(value):
    if not isinstance(value, str) or not re.fullmatch(r"[\da-fA-F-]{36}", value):
        return None
    try:
        return str(UUID(value))
    except ValueError:
        return None


def recording_identifier(values):
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        return None
    identifiers = set()
    for value in values:
        if isinstance(value, str) and value.startswith(("https://musicbrainz.org/recording/", "http://musicbrainz.org/recording/")):
            identifier = canonical_mbid(value.rsplit("/", 1)[-1])
            if identifier:
                identifiers.add(identifier)
    if len(identifiers) > 1:
        raise PlaylistInputError("A playlist entry has conflicting Recording MBIDs.")
    return next(iter(identifiers), None)


def playlist_entry(title, artist, duration, recording):
    if not all(isinstance(value, str) for value in (title, artist)):
        raise PlaylistInputError("Track title and artist must be text.")
    title, artist = normalize_tag(title), normalize_tag(artist)
    if not recording and not (title and artist):
        raise PlaylistInputError("Every entry needs a Recording MBID or both title and artist.")
    if isinstance(duration, str) and duration.isascii() and duration.isdecimal() and len(duration) <= 8:
        duration = int(duration)
    if duration in (None, ""):
        duration = None
    elif type(duration) is not int or not 0 < duration <= 86400000:
        raise PlaylistInputError("Track duration must be a positive integer in milliseconds.")
    return {"title": title, "artist": artist, "durationMs": duration, "recordingMbid": recording}


def parse_jspf(body):
    try:
        playlist = json.loads(body)["playlist"]
        name = playlist.get("title", "")
        tracks = playlist["track"]
        if not isinstance(name, str) or not isinstance(tracks, list):
            raise PlaylistInputError("Invalid JSPF playlist.")
        if len(tracks) > MAX_PLAYLIST_ENTRIES:
            raise PlaylistInputError("A playlist can contain up to 500 entries.")
        entries = [
            playlist_entry(
                track.get("title", ""), track.get("creator", ""), track.get("duration"),
                recording_identifier(track.get("identifier")),
            )
            for track in tracks
        ]
    except (AttributeError, KeyError, TypeError, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise PlaylistInputError("Invalid JSPF playlist.") from exc
    return normalize_tag(name), entries


def parse_csv(body):
    reader = csv.DictReader(io.StringIO(body.decode("utf-8-sig"), newline=""), strict=True)
    fields = set(reader.fieldnames or ())
    if len(fields) != len(reader.fieldnames or ()) or not (
        "recording_mbid" in fields or {"title", "artist"} <= fields
    ):
        raise PlaylistInputError("CSV needs title and artist columns or a recording_mbid column.")
    entries = []
    for row in reader:
        if len(entries) >= MAX_PLAYLIST_ENTRIES:
            raise PlaylistInputError("A playlist can contain up to 500 entries.")
        if None in row or any(value is None for value in row.values()):
            raise PlaylistInputError("Invalid CSV row length.")
        value = row.get("recording_mbid", "").strip()
        identifier = canonical_mbid(value)
        if value and not identifier:
            raise PlaylistInputError("Invalid Recording MBID in CSV.")
        entries.append(playlist_entry(
            row.get("title", ""), row.get("artist", ""), row.get("duration_ms"), identifier,
        ))
    return entries


def read_playlist_file(file):
    if file is None:
        raise PlaylistInputError("A CSV or JSPF file is required.")
    body = file.read(MAX_PLAYLIST_SIZE + 1)
    if len(body) > MAX_PLAYLIST_SIZE:
        raise PlaylistInputError("The playlist file exceeds 1 MiB.")
    suffix = Path(file.name).suffix.lower()
    try:
        if suffix == ".csv":
            name, entries = "", parse_csv(body)
        elif suffix in {".json", ".jspf"}:
            name, entries = parse_jspf(body)
        else:
            raise PlaylistInputError("Upload a CSV or JSPF file.")
    except (UnicodeError, csv.Error) as exc:
        raise PlaylistInputError("Invalid UTF-8 CSV playlist.") from exc
    name = name or normalize_tag(Path(file.name).stem) or "Imported playlist"
    key = hashlib.sha256(suffix.encode() + b":" + body).hexdigest()
    return key, name, entries


def fetch_listenbrainz(playlist_id, token):
    if canonical_mbid(playlist_id) != playlist_id:
        raise PlaylistInputError("Enter a valid ListenBrainz playlist UUID.")
    if not isinstance(token, str) or (token and not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", token)):
        raise PlaylistInputError("Invalid ListenBrainz token format.")
    headers = {"Accept": "application/json", "User-Agent": "WaveBox/1.0"}
    if token:
        headers["Authorization"] = f"Token {token}"
    connection = http.client.HTTPSConnection("api.listenbrainz.org", timeout=4)
    deadline = time.monotonic() + 10
    try:
        connection.request("GET", f"/1/playlist/{playlist_id}", headers=headers)
        with connection.getresponse() as response:
            if response.status == 429:
                delay = response.getheader("Retry-After", "")
                raise PlaylistProviderError("ListenBrainz rate limit reached.", 429, delay if delay.isdigit() else None)
            if response.status in {401, 403, 404}:
                raise PlaylistProviderError("ListenBrainz playlist is unavailable. Check its UUID and access token.", 422)
            if response.status != 200:
                raise PlaylistProviderError("ListenBrainz is temporarily unavailable.")
            body = bytearray()
            while time.monotonic() < deadline and len(body) <= MAX_PLAYLIST_SIZE:
                chunk = response.read1(min(65536, MAX_PLAYLIST_SIZE + 1 - len(body)))
                if not chunk:
                    try:
                        name, entries = parse_jspf(body)
                    except PlaylistInputError as exc:
                        raise PlaylistProviderError(str(exc), 422) from exc
                    return name or "ListenBrainz playlist", entries
                body.extend(chunk)
            raise PlaylistProviderError("ListenBrainz response exceeded the size or time limit.")
    except (OSError, http.client.HTTPException) as exc:
        raise PlaylistProviderError("ListenBrainz is temporarily unavailable.") from exc
    finally:
        connection.close()
