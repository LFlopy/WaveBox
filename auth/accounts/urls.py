from django.urls import path
from .playlists import imported_playlist, imported_playlists, resolve_playlist_entry, sync_imported_playlist
from .views import csrf, download_internet_archive, register, login, logout, me, music_import_status, upload


urlpatterns = [
    path("playlists/imported", imported_playlists, name="imported-playlists"),
    path("playlists/imported/<uuid:playlist_id>", imported_playlist, name="imported-playlist"),
    path("playlists/imported/<uuid:playlist_id>/sync", sync_imported_playlist, name="sync-imported-playlist"),
    path("playlists/imported/<uuid:playlist_id>/resolve", resolve_playlist_entry, name="resolve-playlist-entry"),
    path("csrf", csrf, name="csrf"),
    path("register", register, name="register"),
    path("login", login, name="login"),
    path("logout", logout, name="logout"),
    path("me", me, name="me"),
    path("imports/<uuid:import_id>", music_import_status, name="music-import-status"),
    path("upload", upload, name="upload"),
    path("external/internet-archive/download", download_internet_archive, name="download-internet-archive"),
]
