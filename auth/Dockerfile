FROM python:3.14-slim-trixie

ARG FFMPEG_VERSION=7:7.1.5-0+deb13u1
RUN apt-get update \
    && apt-get install -y --no-install-recommends "ffmpeg=${FFMPEG_VERSION}" \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY auth/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY auth/ .
COPY python-backend/import_tracks.py python-backend/models.py /python-backend/

EXPOSE 8000
