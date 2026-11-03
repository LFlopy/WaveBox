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
- `JAMENDO_CLIENT_ID`: optional Jamendo developer client ID; without it Jamendo is returned as an external link only

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

The frontend proxies `/api/tracks`, `/api/external/`, `/audio/`, and `/covers/` to the Go API and `/api/auth/` to Django.

## External music search

The Go API can search one source with the original parameter:

```text
GET /api/external/search?source=muzsky&q=Ado
```

Multiple sources and a result limit can be selected without changing the endpoint:

```text
GET /api/external/search?sources=muzsky,internet_archive&q=Amazing%20Grace&limit=20
```

`source` may also be repeated. The default limit is 20 and the maximum is 50. Source requests run concurrently with separate 12-second deadlines. Successful results are returned when another source fails; failures appear in `errors`. Sources without a permitted catalog API appear in `externalLinks` instead of fabricated track results.

Each track includes `title`, `artist`, `duration`, `cover`, `source`, `pageUrl`, confirmed `format` and `quality` when available, `downloadAvailable`, and `downloadMethod`. The download method is `direct`, `external`, or `none`. Results with the same normalized title and artist and a duration within three seconds are grouped, while every acquisition option remains in `variants`.

Before returning results, the API compares both normalized title and artist with PostgreSQL library tracks and checks compatible durations when both are known. Matching results include `inLibrary: true` and `libraryTrackId`.

| Source | Server-side search | Acquisition behavior |
| --- | --- | --- |
| Muzsky | Enabled | Manual external-site MP3 download only; automated download is not used |
| Internet Archive | Enabled through the official Advanced Search API | Item page only; availability and rights must be checked per item |
| Jamendo | Enabled only with `JAMENDO_CLIENT_ID` | Direct MP3 URL only when the API returns `audiodownload_allowed: true`; otherwise none |
| Bandcamp | Not available through its partner/account API | External Bandcamp search link |
| Qobuz | Not enabled without Qobuz-issued application credentials and approved access | External Qobuz store link; purchases remain on Qobuz |
| Free Music Archive | Disabled because its public API was shut down and unapproved search proxying is forbidden | External FMA search link |

Muzsky's search form submits to `/search/`, which its `robots.txt` disallows for automated access. The adapter uses `/suggest.php` and permitted public track pages instead. Its download host disallows all automated access, so WaveBox exposes only the track page.

Direct downloads are not imported automatically in this stage. A permitted MP3 or FLAC can later be stored under `tracks/audio/` and passed to the existing Python importer, which remains the only owner of audio metadata extraction and database insertion.

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
