import json
import hashlib
import logging
import os
import tempfile
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.core.validators import validate_email
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from mutagen import MutagenError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from import_tracks import import_file, read_metadata


User = get_user_model()
logger = logging.getLogger(__name__)


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
    if suffix not in {".mp3", ".flac"}:
        return JsonResponse({"error": "Only MP3 and FLAC files are supported"}, status=415)

    audio_dir = settings.MUSIC_AUDIO_DIR
    covers_dir = settings.MUSIC_COVERS_DIR
    temporary_dir = audio_dir.parent / ".uploads"
    audio_dir.mkdir(parents=True, exist_ok=True)
    covers_dir.mkdir(parents=True, exist_ok=True)
    temporary_dir.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    destination = None
    created_file = False
    import_succeeded = False

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

        metadata = read_metadata(temporary_path)
        if metadata["audio_format"] != suffix[1:]:
            return JsonResponse({"error": "File extension does not match its audio format"}, status=415)

        filename = f"{digest.hexdigest()}.{metadata['audio_format']}"
        destination = audio_dir / filename
        audio_path = f"/audio/{filename}"
        try:
            os.link(temporary_path, destination)
            created_file = True
        except FileExistsError:
            pass

        engine = create_engine(settings.MUSIC_DATABASE_URL)
        try:
            with Session(engine, expire_on_commit=False) as session:
                track, created_track = import_file(
                    session,
                    destination,
                    audio_path,
                    covers_dir,
                    metadata,
                )
                import_succeeded = True
                response = {
                    "id": track.id,
                    "title": track.title,
                    "artist": track.artist.name,
                    "duration": track.duration,
                    "cover": track.cover_path,
                    "audioUrl": track.audio_path,
                }
        finally:
            engine.dispose()

        return JsonResponse(
            {"track": response, "duplicate": not created_track},
            status=201 if created_track else 200,
        )
    except (MutagenError, ValueError) as exc:
        if created_file and not import_succeeded and destination is not None:
            destination.unlink(missing_ok=True)
        return JsonResponse({"error": str(exc)}, status=422)
    except Exception:
        if created_file and not import_succeeded and destination is not None:
            destination.unlink(missing_ok=True)
        logger.exception("music upload failed")
        return JsonResponse({"error": "Music upload failed"}, status=500)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
