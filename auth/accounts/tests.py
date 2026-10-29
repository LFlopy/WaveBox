import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from models import Base, Track


class UploadTest(TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.audio_dir = root / "audio"
        self.covers_dir = root / "covers"
        self.database_url = f"sqlite:///{root / 'music.db'}"
        self.settings_override = override_settings(
            MUSIC_DATABASE_URL=self.database_url,
            MUSIC_AUDIO_DIR=self.audio_dir,
            MUSIC_COVERS_DIR=self.covers_dir,
            MAX_MUSIC_UPLOAD_SIZE=1024,
        )
        self.settings_override.enable()
        self.engine = create_engine(self.database_url)
        Base.metadata.create_all(self.engine)
        self.user = get_user_model().objects.create_user(username="listener", password="password")

    def tearDown(self):
        self.engine.dispose()
        self.settings_override.disable()
        self.temporary_directory.cleanup()

    def metadata(self, audio_format):
        return {
            "title": f"Uploaded {audio_format.upper()}",
            "artist_name": "WaveBox Artist",
            "duration": "1:00",
            "pictures": [],
            "file_size": 5,
            "audio_format": audio_format,
            "bit_depth": 24 if audio_format == "flac" else None,
            "sample_rate": 44100,
            "bitrate": 192000 if audio_format == "mp3" else None,
        }

    def count_tracks(self):
        with Session(self.engine) as session:
            return session.scalar(select(func.count(Track.id)))

    def test_requires_authentication(self):
        response = self.client.post(
            "/api/auth/upload",
            {"file": SimpleUploadedFile("song.mp3", b"audio")},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.count_tracks(), 0)

    def test_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.post(
            "/api/auth/upload",
            {"file": SimpleUploadedFile("song.mp3", b"audio")},
        )

        self.assertEqual(response.status_code, 403)
        client.get("/api/auth/csrf")
        token = client.cookies["csrftoken"].value
        with patch("accounts.views.read_metadata", return_value=self.metadata("mp3")):
            response = client.post(
                "/api/auth/upload",
                {"file": SimpleUploadedFile("song.mp3", b"audio")},
                HTTP_X_CSRFTOKEN=token,
            )
        self.assertEqual(response.status_code, 201)

    def test_uploads_mp3_and_flac(self):
        self.client.force_login(self.user)
        for audio_format in ("mp3", "flac"):
            with self.subTest(audio_format=audio_format):
                with patch("accounts.views.read_metadata", return_value=self.metadata(audio_format)):
                    response = self.client.post(
                        "/api/auth/upload",
                        {"file": SimpleUploadedFile(f"song.{audio_format}", audio_format.encode())},
                    )

                self.assertEqual(response.status_code, 201)
                data = response.json()
                self.assertFalse(data["duplicate"])
                audio_path = data["track"]["audioUrl"]
                self.assertTrue((self.audio_dir / Path(audio_path).name).is_file())

        self.assertEqual(self.count_tracks(), 2)
        with Session(self.engine) as session:
            tracks = session.scalars(select(Track).order_by(Track.audio_format)).all()
            self.assertEqual([track.title for track in tracks], ["Uploaded FLAC", "Uploaded MP3"])
            self.assertEqual([track.audio_format for track in tracks], ["flac", "mp3"])

    def test_rejects_invalid_format(self):
        self.client.force_login(self.user)
        response = self.client.post(
            "/api/auth/upload",
            {"file": SimpleUploadedFile("song.wav", b"audio")},
        )
        self.assertEqual(response.status_code, 415)

        with patch("accounts.views.read_metadata", side_effect=ValueError("file is not a valid MP3 or FLAC")):
            response = self.client.post(
                "/api/auth/upload",
                {"file": SimpleUploadedFile("song.mp3", b"invalid")},
            )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(list(self.audio_dir.glob("*")), [])

    def test_rejects_oversized_file(self):
        self.client.force_login(self.user)
        with override_settings(MAX_MUSIC_UPLOAD_SIZE=4):
            response = self.client.post(
                "/api/auth/upload",
                {"file": SimpleUploadedFile("song.mp3", b"audio")},
            )

        self.assertEqual(response.status_code, 413)
        self.assertEqual(self.count_tracks(), 0)

    def test_repeated_upload_is_idempotent(self):
        self.client.force_login(self.user)
        with patch("accounts.views.read_metadata", return_value=self.metadata("mp3")):
            first = self.client.post(
                "/api/auth/upload",
                {"file": SimpleUploadedFile("song.mp3", b"audio")},
            )
            second = self.client.post(
                "/api/auth/upload",
                {"file": SimpleUploadedFile("song.mp3", b"audio")},
            )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json()["duplicate"])
        self.assertEqual(self.count_tracks(), 1)
        self.assertEqual(len(list(self.audio_dir.glob("*.mp3"))), 1)

    def test_removes_file_after_import_error(self):
        self.client.force_login(self.user)
        with (
            patch("accounts.views.read_metadata", return_value=self.metadata("mp3")),
            patch("accounts.views.import_file", side_effect=SQLAlchemyError("failed")),
        ):
            response = self.client.post(
                "/api/auth/upload",
                {"file": SimpleUploadedFile("song.mp3", b"audio")},
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(list(self.audio_dir.glob("*")), [])
        self.assertEqual(self.count_tracks(), 0)
