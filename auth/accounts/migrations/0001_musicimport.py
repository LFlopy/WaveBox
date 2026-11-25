import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="MusicImport",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("available_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("suffix", models.CharField(blank=True, max_length=5)),
                ("payload", models.JSONField(default=dict)),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("status_code", models.PositiveSmallIntegerField(null=True)),
                ("result", models.JSONField(default=dict)),
                ("user", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
