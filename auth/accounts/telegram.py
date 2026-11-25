import hashlib
import hmac
import json
import re
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl

from django.conf import settings
from django.contrib.auth import login
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_variables
from django.views.decorators.http import require_http_methods, require_POST

from .models import TelegramAccount, TelegramLaunch


INIT_DATA_MAX_AGE = timedelta(minutes=5)
CLOCK_SKEW = timedelta(seconds=30)
BODY_LIMIT = 32 * 1024


class TelegramDataError(ValueError):
    pass


@sensitive_variables()
def validate_init_data(raw, token, now):
    if not isinstance(raw, str) or not 0 < len(raw) <= BODY_LIMIT:
        raise TelegramDataError("Invalid Telegram launch data.")
    try:
        pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=True, errors="strict", max_num_fields=32)
    except (ValueError, UnicodeError) as exc:
        raise TelegramDataError("Invalid Telegram launch data.") from exc
    fields = dict(pairs)
    supplied_hash = fields.pop("hash", "")
    if len(fields) + 1 != len(pairs) or not re.fullmatch(r"[0-9a-f]{64}", supplied_hash):
        raise TelegramDataError("Invalid Telegram launch data.")
    if any(not re.fullmatch(r"[a-z_][a-z_0-9]*", key) or "\n" in value or "\r" in value for key, value in fields.items()):
        raise TelegramDataError("Invalid Telegram launch data.")

    try:
        message = "\n".join(f"{key}={value}" for key, value in sorted(fields.items())).encode()
    except UnicodeEncodeError as exc:
        raise TelegramDataError("Invalid Telegram launch data.") from exc
    secret = hmac.digest(b"WebAppData", token.encode(), hashlib.sha256)
    if not hmac.compare_digest(hmac.digest(secret, message, hashlib.sha256).hex(), supplied_hash):
        raise TelegramDataError("Invalid Telegram launch signature.")

    try:
        stamp = fields["auth_date"]
        if not re.fullmatch(r"[0-9]{1,12}", stamp):
            raise ValueError
        launched_at = datetime.fromtimestamp(int(stamp), tz=UTC)
        user_id = json.loads(fields["user"])["id"]
    except (KeyError, ValueError, TypeError, OverflowError, OSError, RecursionError) as exc:
        raise TelegramDataError("Invalid Telegram launch data.") from exc
    if type(user_id) is not int or not 0 < user_id < 2**52:
        raise TelegramDataError("Invalid Telegram user ID.")
    if launched_at > now + CLOCK_SKEW or launched_at + INIT_DATA_MAX_AGE <= now:
        raise TelegramDataError("Reopen the Mini App to refresh the Telegram launch.")
    return user_id, supplied_hash, launched_at + INIT_DATA_MAX_AGE


@sensitive_variables()
def telegram_launch(request):
    body = request.read(BODY_LIMIT + 1)
    if len(body) > BODY_LIMIT:
        raise TelegramDataError("Invalid Telegram launch data.")
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise TelegramDataError("Invalid Telegram launch data.") from exc
    raw = payload.get("initData") if isinstance(payload, dict) else None
    return validate_init_data(raw, settings.TELEGRAM_BOT_TOKEN, timezone.now())


def consume_launch(digest, expires_at):
    now = timezone.now()
    if expires_at <= now:
        return False
    TelegramLaunch.objects.filter(expires_at__lte=now).delete()
    _, created = TelegramLaunch.objects.get_or_create(digest=digest, defaults={"expires_at": expires_at})
    return created


@never_cache
@require_http_methods(["GET", "POST", "DELETE"])
def telegram_account(request):
    if not settings.TELEGRAM_BOT_TOKEN:
        return JsonResponse({"error": "Telegram sign-in is disabled."}, status=404)
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Not authenticated."}, status=401)

    links = TelegramAccount.objects.filter(user=request.user)
    if request.method == "GET":
        return JsonResponse({"linked": links.exists()})
    if request.method == "DELETE":
        links.delete()
        return JsonResponse({"linked": False})

    try:
        telegram_id, digest, expires_at = telegram_launch(request)
    except TelegramDataError as exc:
        return JsonResponse({"error": str(exc)}, status=401)

    try:
        with transaction.atomic():
            link, _ = TelegramAccount.objects.get_or_create(telegram_id=telegram_id, defaults={"user": request.user})
            if link.user_id != request.user.pk:
                return JsonResponse({"error": "This Telegram account is already linked."}, status=409)
            if not consume_launch(digest, expires_at):
                transaction.set_rollback(True)
                return JsonResponse({"error": "Reopen the Mini App before linking."}, status=409)
    except IntegrityError:
        if not links.exists():
            raise
        return JsonResponse({"error": "Unlink the current Telegram account before linking another."}, status=409)
    return JsonResponse({"linked": True})


@never_cache
@require_POST
def telegram_login(request):
    if not settings.TELEGRAM_BOT_TOKEN:
        return JsonResponse({"error": "Telegram sign-in is disabled."}, status=404)
    if request.user.is_authenticated:
        return JsonResponse({"error": "Log out before switching accounts."}, status=409)
    try:
        telegram_id, digest, expires_at = telegram_launch(request)
    except TelegramDataError as exc:
        return JsonResponse({"error": str(exc)}, status=401)

    with transaction.atomic():
        link = (
            TelegramAccount.objects.select_for_update().select_related("user")
            .filter(telegram_id=telegram_id, user__is_active=True).first()
        )
        if link is None:
            return JsonResponse({"error": "Sign in to WaveBox first, then link Telegram in the Mini App."}, status=403)
        if not consume_launch(digest, expires_at):
            return JsonResponse({"error": "Reopen the Mini App before signing in again."}, status=409)
        login(request, link.user, backend="django.contrib.auth.backends.ModelBackend")

    return JsonResponse({"id": link.user_id, "username": link.user.username, "email": link.user.email})
