import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class MusicImport(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    available_at = models.DateTimeField(default=timezone.now, db_index=True)
    suffix = models.CharField(max_length=5, blank=True)
    payload = models.JSONField(default=dict)
    attempts = models.PositiveSmallIntegerField(default=0)
    status_code = models.PositiveSmallIntegerField(null=True)
    result = models.JSONField(default=dict)


class ImportedPlaylist(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    source = models.CharField(max_length=16)
    source_key = models.CharField(max_length=64)
    name = models.CharField(max_length=255)
    entries = models.JSONField(default=list)
    revision = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("user", "source", "source_key"), name="unique_imported_playlist_source"),
        ]


class TelegramAccount(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    telegram_id = models.PositiveBigIntegerField(unique=True)


class TelegramLaunch(models.Model):
    digest = models.CharField(max_length=64, primary_key=True)
    expires_at = models.DateTimeField(db_index=True)
