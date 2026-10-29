from django.urls import path
from .views import csrf, register, login, logout, me, upload


urlpatterns = [
    path("csrf", csrf, name="csrf"),
    path("register", register, name="register"),
    path("login", login, name="login"),
    path("logout", logout, name="logout"),
    path("me", me, name="me"),
    path("upload", upload, name="upload"),
]
