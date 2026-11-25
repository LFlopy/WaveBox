import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections

from accounts.views import process_next_music_import


class Command(BaseCommand):
    def handle(self, *args, **options):
        while True:
            close_old_connections()
            if not process_next_music_import():
                time.sleep(1)
