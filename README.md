# WaveBox

WaveBox is a self-hosted music player for a library stored on your own machine. It provides browser-based playback, user authentication, track browsing and search, and browser-local liked songs and playlists.

Music metadata is stored in PostgreSQL. MP3, FLAC, and cover files remain on the filesystem under `tracks/audio/` and `tracks/covers/`. Authenticated users can upload MP3 and FLAC files from the web interface.

## Stack and services

- `frontend/`: React, Vite, and Tailwind CSS user interface
- `backend/`: Go HTTP API for the music library and media files
- `auth/`: Django authentication service
- `python-backend/`: SQLAlchemy models and Alembic database migrations
- `db`: PostgreSQL 17 for authentication data and track metadata

Docker Compose starts the frontend, API, authentication service, PostgreSQL, and a one-shot migration service. The migration service creates or updates the music-library schema before the Go API starts.

## Configuration

Copy the example environment file:

```bash
cp .env.example .env
```

Configure these values in `.env`:

- `POSTGRES_PASSWORD`: password used by PostgreSQL, Django, migrations, and the Go API
- `DJANGO_SECRET_KEY`: secret key used by Django
- `MAX_MUSIC_UPLOAD_SIZE`: optional maximum upload size in bytes; defaults to `104857600`

Use development secrets only for local environments. Do not commit `.env`.

## Start the project

Ensure the media directories exist and place library files in them:

```text
tracks/
├── audio/
└── covers/
```

Build and start all services:

```bash
docker compose up -d --build
```

Open the application at [http://127.0.0.1:5173](http://127.0.0.1:5173).

## Service addresses

| Service | Address |
| --- | --- |
| Frontend | `http://127.0.0.1:5173` |
| Go API | `http://127.0.0.1:8080` |
| API health check | `http://127.0.0.1:8080/health` |
| Track list | `http://127.0.0.1:8080/api/tracks` |
| External search | `http://127.0.0.1:8080/api/external/search?source=muzsky&q=Ado` |
| Django auth | `http://127.0.0.1:8000` |
| PostgreSQL | `127.0.0.1:5433` |

The frontend proxies `/api/tracks`, `/audio/`, and `/covers/` to the Go API and `/api/auth/` to Django.

## External music search

The Go API can search Muzsky without adding results to the local library:

```text
GET /api/external/search?source=muzsky&q=Ado
```

The response contains the source name and track results with `title`, `artist`, `duration`, `cover`, and `pageUrl`. The adapter uses Muzsky's same-origin suggestion endpoint and public track pages, applies request timeouts, limits response size, restricts redirects to `muzsky.net` and its subdomains, and spaces requests by 500 milliseconds. An unavailable source or an unrecognized response returns HTTP 502; an empty search returns an empty `results` array.

Muzsky's search form submits to `/search/`, which its `robots.txt` disallows for automated access. The adapter therefore uses `/suggest.php`, which powers the site's interactive suggestions and is not disallowed for ordinary user agents, followed by permitted public track pages for duration metadata.

WaveBox does not download audio from Muzsky. Although track pages expose a manual download control, the download host disallows all automated access in its `robots.txt`, and no documented public download API or programmatic-use permission was found. If explicit permission becomes available later, downloaded MP3 files can be placed under `tracks/audio/` and processed by the existing importer; FLAC availability was not confirmed.

## Common commands

Start or rebuild the project:

```bash
docker compose up -d --build
```

View logs:

```bash
docker compose logs -f
```

View logs for one service:

```bash
docker compose logs -f api
```

Stop the project without deleting persisted data:

```bash
docker compose down
```

Check service status:

```bash
docker compose ps
```

PostgreSQL data is stored in the `postgres_data` Docker volume. Do not use `docker compose down -v` if you want to preserve it.

## Go checks

Run the API tests and build locally:

```bash
cd backend
go test ./...
go build ./cmd/api
```
