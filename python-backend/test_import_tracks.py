import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mutagen import MutagenError
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from import_tracks import MissingMetadataError, import_tracks
from models import Artist, Base, Track


class ImportTracksTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.audio_dir = root / "audio"
        self.covers_dir = root / "covers"
        self.audio_dir.mkdir()
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

    def tearDown(self):
        self.session.close()
        self.engine.dispose()
        self.temporary_directory.cleanup()

    def test_imports_track_with_cover_and_is_idempotent(self):
        audio_file = self.audio_dir / "song.mp3"
        audio_file.write_bytes(b"mp3")
        picture = type("Picture", (), {"mime": "image/jpeg", "data": b"cover"})()
        metadata = {
            "title": "Song",
            "artist_name": "Artist",
            "duration": "2:05",
            "pictures": [picture],
            "file_size": 3,
            "audio_format": "mp3",
            "bit_depth": None,
            "sample_rate": 44100,
            "bitrate": 192000,
        }

        with patch("import_tracks.read_metadata", return_value=metadata):
            first = import_tracks(self.session, self.audio_dir, self.covers_dir)
            second = import_tracks(self.session, self.audio_dir, self.covers_dir)

        self.assertEqual(first, (1, 0, 0))
        self.assertEqual(second, (0, 1, 0))
        track = self.session.scalar(select(Track))
        self.assertEqual(track.title, "Song")
        self.assertEqual(track.artist.name, "Artist")
        self.assertEqual(track.duration, "2:05")
        self.assertEqual(track.audio_path, "/audio/song.mp3")
        self.assertEqual(track.file_size, 3)
        self.assertEqual(track.audio_format, "mp3")
        self.assertIsNone(track.bit_depth)
        self.assertEqual(track.sample_rate, 44100)
        self.assertEqual(track.bitrate, 192000)
        self.assertEqual((self.covers_dir / Path(track.cover_path).name).read_bytes(), b"cover")
        self.assertEqual(self.session.scalar(select(func.count(Track.id))), 1)
        self.assertEqual(self.session.scalar(select(func.count(Artist.id))), 1)

    def test_skips_missing_metadata(self):
        (self.audio_dir / "untagged.mp3").write_bytes(b"mp3")

        with patch(
            "import_tracks.read_metadata",
            side_effect=MissingMetadataError("missing title, artist, or duration"),
        ):
            result = import_tracks(self.session, self.audio_dir, self.covers_dir)

        self.assertEqual(result, (0, 1, 0))
        self.assertEqual(self.session.scalar(select(func.count(Track.id))), 0)

    def test_continues_after_damaged_file(self):
        (self.audio_dir / "broken.mp3").write_bytes(b"broken")
        (self.audio_dir / "valid.mp3").write_bytes(b"mp3")
        metadata = {
            "title": "Valid",
            "artist_name": "Artist",
            "duration": "1:00",
            "pictures": [],
            "file_size": 3,
            "audio_format": "mp3",
            "bit_depth": None,
            "sample_rate": None,
            "bitrate": None,
        }

        with patch(
            "import_tracks.read_metadata",
            side_effect=[MutagenError("broken"), metadata],
        ):
            result = import_tracks(self.session, self.audio_dir, self.covers_dir)

        self.assertEqual(result, (1, 0, 1))
        self.assertEqual(self.session.scalar(select(func.count(Track.id))), 1)

    def test_imports_flac_with_picture_and_properties(self):
        audio_file = self.audio_dir / "lossless.flac"
        audio_file.write_bytes(b"f" * 450000)
        picture = type("Picture", (), {"mime": "image/png", "data": b"picture"})()
        metadata = {
            "title": "Lossless",
            "artist_name": "Artist",
            "duration": "3:00",
            "pictures": [picture],
            "file_size": 450000,
            "audio_format": "flac",
            "bit_depth": 24,
            "sample_rate": 96000,
            "bitrate": None,
        }

        with patch("import_tracks.read_metadata", return_value=metadata):
            first = import_tracks(self.session, self.audio_dir, self.covers_dir)
            second = import_tracks(self.session, self.audio_dir, self.covers_dir)

        self.assertEqual(first, (1, 0, 0))
        self.assertEqual(second, (0, 1, 0))
        track = self.session.scalar(select(Track))
        self.assertEqual(track.title, "Lossless")
        self.assertEqual(track.audio_format, "flac")
        self.assertEqual(track.bit_depth, 24)
        self.assertEqual(track.sample_rate, 96000)
        self.assertIsNone(track.bitrate)
        self.assertEqual((self.covers_dir / Path(track.cover_path).name).read_bytes(), b"picture")


if __name__ == "__main__":
    unittest.main()
