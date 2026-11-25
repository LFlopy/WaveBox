import json
import hashlib
import logging
import os
import tempfile
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET
from django.core.validators import validate_email
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from mutagen import MutagenError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from .models import MusicImport

from .external_download import (
    ExternalDownloadError,
    ExternalFileTooLarge,
    UnsafeRemoteAddress,
    archive_download_url,
    fetch_archive_item,
    stream_archive_file,
)
from import_tracks import AUDIO_FORMATS, import_file, read_metadata


User = get_user_model()
logger = logging.getLogger(__name__)


def import_temporary_audio(temporary_path, digest, metadata):
    audio_dir = settings.MUSIC_AUDIO_DIR
    covers_dir = settings.MUSIC_COVERS_DIR
    audio_dir.mkdir(parents=True, exist_ok=True)
    covers_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{digest}.{metadata['audio_format']}"
    destination = audio_dir / filename
    audio_path = f"/audio/{filename}"
    engine = create_engine(settings.MUSIC_DATABASE_URL)
    try:
        with Session(engine, expire_on_commit=False) as session:
            track, created_track = import_file(
                session, temporary_path, audio_path, covers_dir, metadata,
                digest=digest, destination=destination,
            )
            return {
                "id": track.id,
                "title": track.title,
                "artist": track.artist.name,
                "duration": track.duration,
                "cover": track.cover_path,
                "audioUrl": track.audio_path,
            }, created_track
    finally:
        engine.dispose()


@require_GET
@ensure_csrf_cookie
def csrf(request):
    return JsonResponse({"message": "CSRF cookies set"})


@require_POST
def register(request):
    try:
        data = json.loads(request.body)

    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if not isinstance(data, dict):
        return JsonResponse(
            {"error": "Expected JSON object"},
            status=400,
        )

    username = data.get("username", "")
    email = data.get("email", "")
    password = data.get("password", "")

    if not all(isinstance(value, str) for value in (username, email, password)):
        return JsonResponse({"error": "Invalid field types"}, status=400)

    username = username.strip()
    email = email.strip()

    if not username or not email or not password:
        return JsonResponse({"error": "All field are required"}, status=400)

    if User.objects.filter(username__iexact=username).exists():
        return JsonResponse({"error": "User already exists"}, status=409)

    if User.objects.filter(email__iexact=email).exists():
        return JsonResponse({"error": "This email is already taken"}, status=409)

    try:
        validate_password(password)
    except ValidationError as exc:
        return JsonResponse({"error": exc.messages}, status=400)

    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({"error": "Invalid email adress"}, status=400)

    user = User.objects.create_user(
        username=username,
        password=password,
        email=email,
    )

    return JsonResponse(
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
        },
        status=201,
    )


@require_POST
def login(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid json"}, status=400)
    if not isinstance(data, dict):
        return JsonResponse({"error": "Expected JSON object"}, status=400)
    username = data.get("username")
    password = data.get("password")

    if not isinstance(username, str) or not isinstance(password, str):
        return JsonResponse({"error": "Invalid credentials"}, status=400)

    user = authenticate(
        request,
        username=username,
        password=password,
    )

    if user is None:
        return JsonResponse({"error": "Invalid username or password"}, status=401)

    auth_login(request, user)

    return JsonResponse(
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
        }
    )


@require_GET
def me(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Not authenticated"}, status=401)
    return JsonResponse(
        {
            "id": request.user.id,
            "username": request.user.username,
            "email": request.user.email,
        }
    )


@require_POST
def logout(request):
    auth_logout(request)

    return JsonResponse({"message": "Logged out successfully"})


def queued_audio_path(job):
    return settings.MUSIC_AUDIO_DIR.parent / ".uploads" / f"{job.pk}{job.suffix}"


def finish_upload(temporary_path, digest, suffix):
    metadata = read_metadata(temporary_path)
    if metadata["audio_format"] != suffix[1:]:
        return JsonResponse({"error": "File extension does not match its audio format"}, status=415)
    response, created_track = import_temporary_audio(temporary_path, digest, metadata)
    return JsonResponse(
        {"track": response, "duplicate": not created_track},
        status=201 if created_track else 200,
    )


def queue_response(job):
    return JsonResponse({"importId": str(job.pk), "status": "pending"}, status=202)


@require_GET
def music_import_status(request, import_id):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Not authenticated"}, status=401)
    job = MusicImport.objects.filter(pk=import_id, user=request.user).first()
    if job is None:
        return JsonResponse({"error": "Import not found"}, status=404)
    if job.status_code is None:
        return queue_response(job)
    return JsonResponse(job.result, status=job.status_code)


@transaction.atomic
def process_next_music_import():
    job = (
        MusicImport.objects.select_for_update(skip_locked=True)
        .filter(status_code__isnull=True, available_at__lte=timezone.now())
        .order_by("created_at", "id").first()
    )
    if job is None:
        return False
    path = queued_audio_path(job) if job.suffix else None
    try:
        if path is None:
            response = import_archive_item(job.payload["identifier"], job.payload["fileName"])
        else:
            response = finish_upload(path, job.payload["digest"], job.suffix)
    except (MutagenError, ValueError) as exc:
        response = JsonResponse({"error": str(exc)}, status=422)
    except Exception:
        logger.exception("queued music import failed")
        response = JsonResponse({"error": "Music import failed"}, status=500)
    job.attempts += 1
    if response.status_code < 500 or job.attempts >= 3:
        job.status_code = response.status_code
        job.result = json.loads(response.content)
        if path is not None:
            transaction.on_commit(lambda: path.unlink(missing_ok=True), robust=True)
    else:
        job.available_at = timezone.now() + timedelta(seconds=5 * job.attempts)
    job.save(update_fields=["attempts", "available_at", "status_code", "result"])
    return True


@require_POST
def upload(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Not authenticated"}, status=401)

    uploaded_file = request.FILES.get("file")
    if uploaded_file is None:
        return JsonResponse({"error": "Music file is required"}, status=400)
    if uploaded_file.size > settings.MAX_MUSIC_UPLOAD_SIZE:
        return JsonResponse({"error": "File exceeds the upload size limit"}, status=413)

    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix not in AUDIO_FORMATS:
        return JsonResponse({"error": "Unsupported audio format"}, status=415)

    audio_dir = settings.MUSIC_AUDIO_DIR
    temporary_dir = audio_dir.parent / ".uploads"
    audio_dir.mkdir(parents=True, exist_ok=True)
    temporary_dir.mkdir(parents=True, exist_ok=True)
    temporary_path = None

    try:
        digest = hashlib.sha256()
        size = 0
        with tempfile.NamedTemporaryFile(dir=temporary_dir, suffix=suffix, delete=False) as temporary_file:
            temporary_path = Path(temporary_file.name)
            for chunk in uploaded_file.chunks():
                size += len(chunk)
                if size > settings.MAX_MUSIC_UPLOAD_SIZE:
                    return JsonResponse({"error": "File exceeds the upload size limit"}, status=413)
                digest.update(chunk)
                temporary_file.write(chunk)

        if request.headers.get("Prefer") == "respond-async":
            job = MusicImport(user=request.user, suffix=suffix, payload={"digest": digest.hexdigest()})
            queued_path = queued_audio_path(job)
            os.replace(temporary_path, queued_path)
            try:
                job.save(force_insert=True)
            except Exception:
                queued_path.unlink(missing_ok=True)
                raise
            return queue_response(job)
        return finish_upload(temporary_path, digest.hexdigest(), suffix)
    except (MutagenError, ValueError) as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    except Exception:
        logger.exception("music upload failed")
        return JsonResponse({"error": "Music upload failed"}, status=500)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


@require_POST
def download_internet_archive(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Not authenticated"}, status=401)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    if not isinstance(data, dict):
        return JsonResponse({"error": "Expected JSON object"}, status=400)
    identifier = data.get("identifier")
    file_name = data.get("fileName")
    if (
        not isinstance(identifier, str) or not 0 < len(identifier) <= 255
        or not isinstance(file_name, str) or not 0 < len(file_name) <= 1024
    ):
        return JsonResponse({"error": "identifier and fileName are required"}, status=400)

    if request.headers.get("Prefer") == "respond-async":
        job = MusicImport.objects.create(
            user=request.user, payload={"identifier": identifier, "fileName": file_name},
        )
        return queue_response(job)
    return import_archive_item(identifier, file_name)


def import_archive_item(identifier, file_name):
    temporary_path = None
    try:
        item = fetch_archive_item(identifier)
        if item.get("identifier") != identifier:
            raise ExternalDownloadError("Internet Archive metadata identifier mismatch")
        selected = next((file for file in item["files"] if file.get("fileName") == file_name), None)
        if selected is None:
            return JsonResponse({"error": "Internet Archive file not found"}, status=404)
        if selected.get("downloadAvailable") is not True:
            return JsonResponse(
                {"error": selected.get("unavailableReason") or "Internet Archive file is not available"},
                status=403,
            )
        audio_format = selected.get("format")
        if audio_format not in {"mp3", "flac"}:
            return JsonResponse({"error": "Only MP3 and FLAC files are supported"}, status=415)
        size = selected.get("size")
        if not isinstance(size, int) or size <= 0:
            raise ExternalDownloadError("Internet Archive file size is invalid")
        if size > settings.MAX_EXTERNAL_DOWNLOAD_SIZE:
            return JsonResponse({"error": "File exceeds the download size limit"}, status=413)

        temporary_dir = settings.MUSIC_AUDIO_DIR.parent / ".downloads"
        temporary_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=temporary_dir, suffix=f".{audio_format}", delete=False) as file:
            temporary_path = Path(file.name)
        target = archive_download_url(identifier, file_name)
        digest, downloaded_size = stream_archive_file(
            target,
            temporary_path,
            settings.MAX_EXTERNAL_DOWNLOAD_SIZE,
        )
        if downloaded_size != size:
            raise ExternalDownloadError("downloaded file size does not match Internet Archive metadata")
        metadata = read_metadata(
            temporary_path,
            fallback_title=selected.get("title", ""),
            fallback_artist=selected.get("artist", ""),
        )
        if metadata["audio_format"] != audio_format:
            return JsonResponse({"error": "Downloaded file does not match the selected audio format"}, status=415)
        response, created_track = import_temporary_audio(temporary_path, digest, metadata)
        return JsonResponse(
            {
                "track": response,
                "duplicate": not created_track,
                "source": "internet_archive",
                "identifier": identifier,
                "fileName": file_name,
            },
            status=201 if created_track else 200,
        )
    except ExternalFileTooLarge as exc:
        return JsonResponse({"error": str(exc)}, status=413)
    except UnsafeRemoteAddress as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except ExternalDownloadError as exc:
        return JsonResponse({"error": str(exc)}, status=502)
    except (MutagenError, ValueError) as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    except Exception:
        logger.exception("Internet Archive import failed")
        return JsonResponse({"error": "Internet Archive import failed"}, status=500)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
