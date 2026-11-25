import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from enrich_tracks import MetadataUnavailable, cached_request, enrich, fetch, recording_match
from models import Artist, Base, Track, TrackEnrichment


RECORDING = "ac2ca75c-0965-4695-9382-20dd3391c27c"
RELEASE = "a57ea237-eecc-4a44-abca-89f941e2db05"
OTHER = "172b575d-1291-4c43-9cd7-cb66cbe4eac5"


def recording(**overrides):
    return {
        "id": RECORDING, "title": "Synthetic Track", "length": 120000,
        "artist-credit": [{"name": "Test Artist"}], "releases": [{"id": RELEASE}],
        **overrides,
    }


class EnrichmentTest(unittest.TestCase):
    def test_keeps_ambiguous_and_versioned_recordings_as_candidates(self):
        for records, expected in (
            ([recording(), recording(id=OTHER)], [RECORDING, OTHER]),
            ([recording(disambiguation="live at a different venue")], [RECORDING]),
            ([recording(title="Synthetic Track (remix)")], []),
            ([recording(length=126000)], []),
        ):
            self.assertEqual(
                recording_match(records, "Synthetic Track", "Test Artist", 120000),
                (expected, None, None),
            )

    def test_recording_can_be_clear_with_no_unique_release(self):
        self.assertEqual(
            recording_match(
                [recording(releases=[{"id": RELEASE}, {"id": OTHER}])],
                "synthetic   track", "TEST ARTIST", 120300,
            ),
            ([RECORDING], RECORDING, None),
        )

    def test_cache_reuses_success_and_404_and_backs_off_after_429_or_503(self):
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            for status in (200, 404, 429, 503):
                provider = f"test{status}"
                url = "https://musicbrainz.org/ws/2/recording"
                with patch("enrich_tracks.fetch", return_value=(status, b"{}", "60")) as fetch:
                    for _ in range(2):
                        if status in {429, 503}:
                            with self.assertRaises(MetadataUnavailable):
                                cached_request(session, provider, url, "WaveBox/1 (test@example.test)")
                        else:
                            result = cached_request(session, provider, url, "WaveBox/1 (test@example.test)")
                            self.assertEqual(result, b"{}" if status == 200 else None)
                    if status in {429, 503}:
                        with self.assertRaises(MetadataUnavailable):
                            cached_request(session, provider, url + "?second", "WaveBox/1 (test@example.test)")
                    fetch.assert_called_once()
        engine.dispose()

    def test_rejects_unexpected_hosts_before_any_connection(self):
        for url in (
            "https://127.0.0.1/image",
            "https://archive.org.example.test/image",
            "https://user@archive.org/image",
            "https://archive.org:444/image",
        ):
            with self.subTest(url=url), patch("enrich_tracks.PinnedHTTPSConnection") as connection:
                with self.assertRaises(MetadataUnavailable):
                    fetch(url, "WaveBox/1 (test@example.test)", "caa")
                connection.assert_not_called()

    def test_malformed_success_uses_retry_cache(self):
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            with patch("enrich_tracks.fetch", return_value=(200, b"not json", None)) as fetch_response:
                for _ in range(2):
                    with self.assertRaises(MetadataUnavailable):
                        cached_request(session, "mb", "https://musicbrainz.org/ws/2/recording", "test")
                fetch_response.assert_called_once()
        engine.dispose()

    def test_enrichment_preserves_versions_and_uses_release_cover(self):
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        with tempfile.TemporaryDirectory() as directory, Session(engine) as session:
            artist = Artist(name="Test Artist")
            tracks = [
                Track(title="Synthetic Track", artist=artist, duration="2:00", duration_ms=120000,
                      audio_path=f"/audio/test.{suffix}", cover_path="")
                for suffix in ("flac", "mp3")
            ]
            session.add_all(tracks)
            session.commit()
            cover = b"\xff\xd8\xffimage"
            payload = json.dumps({"recordings": [recording()], "count": 1}).encode()
            with patch("enrich_tracks.fetch", side_effect=[(200, payload, None), (200, cover, None)]) as fetch:
                for track in tracks:
                    self.assertTrue(enrich(session, track, artist.name, Path(directory), "WaveBox/1 (test@example.test)", True))
                self.assertEqual(fetch.call_count, 2)
                self.assertTrue(fetch.call_args.args[0].endswith(f"/{RELEASE}/front-250"))
            self.assertEqual(session.scalar(select(func.count(Track.id))), 2)
            self.assertEqual(session.scalars(select(TrackEnrichment.recording_mbid)).all(), [RECORDING, RECORDING])
            self.assertEqual((Path(directory) / f"caa-{RELEASE}.jpg").read_bytes(), cover)
        engine.dispose()
