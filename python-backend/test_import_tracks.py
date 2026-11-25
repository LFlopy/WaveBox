import subprocess
import tempfile
import unittest
from base64 import b64decode
from pathlib import Path
from unittest.mock import patch

from mutagen import MutagenError
from mutagen.flac import FLAC, Picture
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from import_tracks import MissingMetadataError, import_file, import_tracks, read_metadata
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
        cover = b"cover"
        metadata = {
            "title": "Song",
            "artist_name": "Artist",
            "duration": "2:05",
            "cover": (cover, ".jpg"),
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
        self.assertEqual((self.covers_dir / Path(track.cover_path).name).read_bytes(), cover)
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
        cover = b"picture"
        metadata = {
            "title": "Lossless",
            "artist_name": "Artist",
            "duration": "3:00",
            "cover": (cover, ".png"),
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
        self.assertEqual((self.covers_dir / Path(track.cover_path).name).read_bytes(), cover)

    def generate_audio(self, name, codec, *options):
        path = self.audio_dir / name
        subprocess.run([
            "ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=0.25",
            "-c:a", codec, *options, str(path),
        ], check=True, timeout=10)
        return path

    def test_probes_and_decodes_supported_formats(self):
        for suffix, codec, expected in (
            ("mp3", "libmp3lame", "mp3"), ("flac", "flac", "flac"),
            ("ogg", "libvorbis", "vorbis"), ("opus", "libopus", "opus"),
            ("aac", "aac", "aac"), ("m4a", "aac", "aac"), ("wav", "pcm_s16le", "pcm_s16le"),
        ):
            with self.subTest(suffix=suffix):
                path = self.generate_audio(f"tone.{suffix}", codec)
                metadata = read_metadata(path, fallback_title="  A   tone  ", fallback_artist="Test")
                self.assertEqual(metadata["codec"], expected)
                self.assertEqual(metadata["channels"], 1)
                self.assertEqual(metadata["title"], "A tone")
                self.assertGreater(metadata["duration_ms"], 0)

    def test_rejects_corruption_and_reports_missing_tags(self):
        path = self.generate_audio("untagged.flac", "flac")
        with self.assertRaises(MissingMetadataError):
            read_metadata(path)
        data = path.read_bytes()
        path.write_bytes(data[:-20])
        with self.assertRaisesRegex(ValueError, "damaged"):
            read_metadata(path, "Test", "Artist")

    def test_imports_embedded_cover_and_detects_identical_files(self):
        path = self.generate_audio("a.flac", "flac", "-metadata", "title=Tone", "-metadata", "artist=Test")
        audio = FLAC(path)
        picture = Picture()
        picture.type = 3
        picture.mime = "image/png"
        picture.data = b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a/04AAAAASUVORK5CYII="
        )
        audio.add_picture(picture)
        audio.save()
        (self.audio_dir / "b.flac").write_bytes(path.read_bytes())
        self.generate_audio("c.mp3", "libmp3lame", "-metadata", "title=Tone", "-metadata", "artist=Test")
        self.assertEqual(import_tracks(self.session, self.audio_dir, self.covers_dir), (2, 1, 0))
        track = self.session.scalar(select(Track).where(Track.audio_format == "flac"))
        self.assertEqual((self.covers_dir / Path(track.cover_path).name).read_bytes(), picture.data)
        self.assertEqual(len(track.sha256), 64)

    def test_rolls_back_database_and_cover_if_audio_publication_fails(self):
        staged = self.generate_audio("staged.flac", "flac")
        metadata = read_metadata(staged, "Tone", "Test")
        metadata["cover"] = (b"cover", ".png")
        destination = self.audio_dir / "published.flac"
        with patch("import_tracks.os.link", side_effect=OSError("write failed")):
            with self.assertRaisesRegex(OSError, "write failed"):
                import_file(
                    self.session, staged, "/audio/published.flac", self.covers_dir,
                    metadata, destination=destination,
                )
        self.assertTrue(staged.exists())
        self.assertFalse(destination.exists())
        self.assertEqual(list(self.covers_dir.iterdir()), [])
        self.assertEqual(self.session.scalar(select(func.count(Track.id))), 0)


if __name__ == "__main__":
    unittest.main()
