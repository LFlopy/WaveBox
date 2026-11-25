FROM python:3.14-slim-trixie

ARG FFMPEG_VERSION=7:7.1.5-0+deb13u1
RUN apt-get update \
    && apt-get install -y --no-install-recommends "ffmpeg=${FFMPEG_VERSION}" \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["alembic", "upgrade", "head"]
