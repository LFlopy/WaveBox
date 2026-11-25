import hashlib
import hmac
import json
from datetime import timedelta
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from .models import TelegramAccount, TelegramLaunch


TOKEN = "12345:synthetic-test-bot-token"
ACCOUNT = "/api/auth/telegram/account"
LOGIN = "/api/auth/telegram/login"
TELEGRAM_ID = 2**41 + 123


def signed_launch(query_id="launch-1", user_id=TELEGRAM_ID, stamp=None, token=TOKEN):
    fields = {
        "query_id": query_id,
        "auth_date": int(timezone.now().timestamp()) if stamp is None else stamp,
        "signature": "fixture-signature",
        "user": json.dumps({"id": user_id, "first_name": "Test + Мелодия"}, ensure_ascii=False),
    }
    message = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, message.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


@override_settings(TELEGRAM_BOT_TOKEN=TOKEN)
class TelegramAuthTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="listener", password="test-password")
        self.other = get_user_model().objects.create_user(username="other")
        self.client = Client(enforce_csrf_checks=True)

    def send(self, endpoint, launch):
        self.client.get("/api/auth/csrf")
        return self.client.post(
            endpoint, {"initData": launch}, content_type="application/json",
            HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value,
        )

    def test_link_sign_in_unlink_and_prevent_replay(self):
        first = signed_launch()
        self.assertEqual(self.send(LOGIN, first).status_code, 403)
        self.assertEqual(self.send(ACCOUNT, first).status_code, 401)
        self.assertFalse(TelegramLaunch.objects.exists())
        self.client.force_login(self.user)
        self.assertEqual(self.send(ACCOUNT, first).json(), {"linked": True})
        self.assertEqual(self.client.get(ACCOUNT).json(), {"linked": True})
        self.assertEqual(self.send(LOGIN, signed_launch("switch")).status_code, 409)
        self.client.logout()
        self.assertEqual(self.send(LOGIN, first).status_code, 409)

        fresh = signed_launch("fresh")
        self.assertEqual(self.send(LOGIN, fresh).json()["username"], "listener")
        self.assertEqual(self.client.get("/api/auth/me").json()["username"], "listener")
        self.client.logout()
        self.assertEqual(self.send(LOGIN, fresh).status_code, 409)

        self.client.force_login(self.user)
        self.assertEqual(self.client.delete(ACCOUNT).status_code, 403)
        self.client.get("/api/auth/csrf")
        self.assertEqual(self.client.delete(
            ACCOUNT, HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value,
        ).json(), {"linked": False})
        self.client.logout()
        self.assertEqual(self.send(LOGIN, signed_launch("after-unlink")).status_code, 403)

    def test_invalid_launches_are_rejected_without_storing_data(self):
        self.client.force_login(self.user)
        now = timezone.now()
        for data in (
            signed_launch().replace("launch-1", "tampered"),
            signed_launch(token="wrong-bot"),
            signed_launch() + "&query_id=duplicate",
            signed_launch().replace("launch-1", chr(0xD800)),
            signed_launch(stamp=int((now - timedelta(minutes=6)).timestamp())),
            signed_launch(stamp=int((now + timedelta(minutes=1)).timestamp())),
            signed_launch(user_id=True),
            signed_launch(user_id=2**52),
        ):
            with self.subTest(data_length=len(data)):
                self.assertEqual(self.send(ACCOUNT, data).status_code, 401)
        self.assertFalse(TelegramAccount.objects.exists())
        self.assertFalse(TelegramLaunch.objects.exists())

    def test_link_cannot_move_between_users_or_replace_existing_identity(self):
        self.client.force_login(self.user)
        self.assertEqual(self.send(ACCOUNT, signed_launch()).status_code, 200)
        self.assertEqual(self.send(ACCOUNT, signed_launch("other-id", user_id=987)).status_code, 409)
        self.client.force_login(self.other)
        self.assertEqual(self.send(ACCOUNT, signed_launch("same-id")).status_code, 409)
        self.assertEqual(TelegramAccount.objects.get().user, self.user)

    def test_inactive_account_cannot_sign_in(self):
        TelegramAccount.objects.create(user=self.user, telegram_id=TELEGRAM_ID)
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        self.assertEqual(self.send(LOGIN, signed_launch()).status_code, 403)

    def test_csrf_is_required_and_feature_is_optional(self):
        self.assertEqual(self.client.post(LOGIN, {"initData": signed_launch()}, content_type="application/json").status_code, 403)
        with override_settings(TELEGRAM_BOT_TOKEN=""):
            self.assertEqual(self.send(LOGIN, signed_launch()).status_code, 404)
