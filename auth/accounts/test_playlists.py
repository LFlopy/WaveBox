import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from models import Artist, Base, Track, TrackEnrichment

from .models import ImportedPlaylist
from .playlist_sources import PlaylistProviderError, fetch_listenbrainz


PLAYLIST_ID = "ac2ca75c-0965-4695-9382-20dd3391c27c"
RECORDING_ID = "172b575d-1291-4c43-9cd7-cb66cbe4eac5"
ROOT = "/api/auth/playlists/imported"


class PlaylistImportTest(TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        database_url = f"sqlite:///{Path(directory.name) / 'catalog.db'}"
        settings = override_settings(MUSIC_DATABASE_URL=database_url)
        settings.enable()
        self.addCleanup(settings.disable)
        engine = create_engine(database_url)
        self.addCleanup(engine.dispose)
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            artist = Artist(name="Test Artist")
            session.add_all([
                Track(id=1, title="One", artist=artist, duration="2:00", duration_ms=120000,
                      cover_path="", audio_path="/audio/one.flac"),
                Track(id=2, title="Two", artist=artist, duration="2:00", duration_ms=120000,
                      cover_path="", audio_path="/audio/two.flac"),
                Track(id=3, title="Two", artist=artist, duration="2:01", duration_ms=121000,
                      cover_path="", audio_path="/audio/two.mp3"),
            ])
            session.commit()
            session.add_all([
                TrackEnrichment(track_id=track_id, recording_mbid=RECORDING_ID,
                                candidates=[RECORDING_ID], next_check=datetime.now(UTC))
                for track_id in (2, 3)
            ])
            session.commit()
        self.user = get_user_model().objects.create_user(username="playlist-owner")
        self.client.force_login(self.user)

    def post_json(self, path, data):
        return self.client.post(path, data, content_type="application/json")

    def import_file(self, content, path=ROOT, name="ordered.csv", **fields):
        return self.client.post(path, {"file": SimpleUploadedFile(name, content), **fields})

    def test_csv_preserves_order_and_repeated_entries_and_deduplicates_same_export(self):
        body = b"title,artist,duration_ms\nOne,Test Artist,120300\nMissing,Test Artist,90000\nOne,Test Artist,120000\n"
        first = self.import_file(body)
        second = self.import_file(body)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        playlist = first.json()
        self.assertEqual(second.json()["id"], playlist["id"])
        self.assertEqual([entry["trackId"] for entry in playlist["entries"]], [1, None, 1])
        self.assertEqual(playlist["counts"], {"matched": 2, "ambiguous": 0, "missing": 1})

    def test_jspf_mbid_chooses_user_version_and_retains_selection_after_refresh(self):
        body = json.dumps({"playlist": {"title": "By ID", "track": [
            {"identifier": [f"https://musicbrainz.org/recording/{RECORDING_ID}"]},
            {"identifier": [f"https://musicbrainz.org/recording/{RECORDING_ID}"]},
        ]}}).encode()
        playlist = self.import_file(body, name="playlist.jspf").json()
        self.assertEqual(playlist["counts"]["ambiguous"], 2)
        self.assertEqual(playlist["entries"][0]["candidateIds"], [2, 3])
        base = f"{ROOT}/{playlist['id']}"
        chosen = self.post_json(base + "/resolve", {"index": 1, "trackId": 3, "revision": 1})
        self.assertEqual(chosen.status_code, 200)
        self.assertEqual(chosen.json()["entries"][1]["status"], "manual")
        sync = self.post_json(base + "/sync", {"revision": 2})
        self.assertEqual([entry["trackId"] for entry in sync.json()["entries"]], [None, 3])
        self.assertEqual(self.post_json(base + "/sync", {"revision": 2}).status_code, 409)
        self.assertEqual(self.post_json(
            base + "/resolve", {"index": 0, "trackId": 1, "revision": 3},
        ).status_code, 400)

    def test_missing_duration_requires_confirmation(self):
        playlist = self.import_file(b"title,artist\nOne,Test Artist\n").json()
        self.assertEqual(playlist["entries"][0]["status"], "ambiguous")
        self.assertEqual(playlist["entries"][0]["candidateIds"], [1])

    def test_file_replacement_keeps_id_and_order(self):
        first = self.import_file(b"title,artist\nOne,Test Artist\n").json()
        body = b"title,artist,duration_ms\nNew,Test Artist,120000\nOne,Test Artist,120000\n"
        response = self.import_file(body, f"{ROOT}/{first['id']}/sync", revision="1")
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["id"], first["id"])
        self.assertEqual(result["revision"], 2)
        self.assertEqual([entry["title"] for entry in result["entries"]], ["New", "One"])
        self.assertEqual(self.import_file(body).json()["id"], first["id"])

    def test_owner_and_csrf_are_required(self):
        playlist = self.import_file(b"title,artist\nOne,Test Artist\n").json()
        base = f"{ROOT}/{playlist['id']}"
        guest = Client()
        self.assertEqual(guest.get(ROOT).status_code, 401)
        guest.force_login(get_user_model().objects.create_user(username="other-user"))
        self.assertEqual(guest.get(ROOT).json()["playlists"], [])
        self.assertEqual(guest.get(base).status_code, 404)
        self.assertEqual(guest.post(base + "/sync", {"revision": 1}).status_code, 404)
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.user)
        self.assertEqual(protected.post(base + "/sync", {"revision": 1}).status_code, 403)

    def test_remote_sync_failure_preserves_snapshot_and_token_is_not_stored(self):
        first_entry = {"title": "One", "artist": "Test Artist", "durationMs": 120000, "recordingMbid": None}
        with patch("accounts.playlists.fetch_listenbrainz", return_value=("Remote", [first_entry])) as fetch:
            first = self.post_json(ROOT, {"playlistId": PLAYLIST_ID, "token": "test-private-token"})
        self.assertEqual(first.status_code, 201)
        fetch.assert_called_once_with(PLAYLIST_ID, "test-private-token")
        playlist = first.json()
        base = f"{ROOT}/{playlist['id']}"
        with patch("accounts.playlists.fetch_listenbrainz", side_effect=PlaylistProviderError("Rate limit.", 429, "20")):
            failed = self.post_json(base + "/sync", {"revision": 1, "remote": True, "token": "test-private-token"})
        self.assertEqual(failed.status_code, 429)
        self.assertEqual(failed.headers["Retry-After"], "20")
        self.assertEqual(self.client.get(base).json(), playlist)
        with patch("accounts.playlists.fetch_listenbrainz", return_value=("Reordered", [first_entry, first_entry])):
            changed = self.post_json(base + "/sync", {"revision": 1, "remote": True})
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(changed.json()["counts"]["matched"], 2)
        self.assertNotIn("test-private-token", repr(ImportedPlaylist.objects.values().get()))

    def test_invalid_input_creates_no_snapshot(self):
        self.assertEqual(self.import_file(b"title,artist\nOne\n").status_code, 400)
        self.assertEqual(self.import_file(
            b"title,artist\n" + b"One,Test Artist\n" * 501,
        ).status_code, 400)
        self.assertEqual(self.post_json(ROOT, {"playlistId": "https://127.0.0.1/"}).status_code, 400)
        self.assertFalse(ImportedPlaylist.objects.exists())

    def test_listenbrainz_transport_uses_fixed_host_and_does_not_follow_redirects(self):
        with patch("accounts.playlist_sources.http.client.HTTPSConnection") as connect:
            client = connect.return_value
            response = client.getresponse.return_value.__enter__.return_value
            response.status = 302
            with self.assertRaises(PlaylistProviderError):
                fetch_listenbrainz(PLAYLIST_ID, "test-token")
            connect.assert_called_once_with("api.listenbrainz.org", timeout=4)
            self.assertEqual(client.request.call_args.args, ("GET", "/1/playlist/" + PLAYLIST_ID))
            self.assertEqual(client.request.call_args.kwargs["headers"]["Authorization"], "Token test-token")
            client.close.assert_called_once()
