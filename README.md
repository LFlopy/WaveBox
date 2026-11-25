# WaveBox

WaveBox is a self-hosted music player for a library stored on your own machine. It provides browser-based playback, user authentication, track browsing and search, and browser-local liked songs and playlists.

Music metadata is stored in PostgreSQL. Audio and cover files remain on the filesystem under `tracks/audio/` and `tracks/covers/`. Authenticated users can upload MP3, FLAC, Ogg, Opus, AAC, M4A, and PCM WAV files. Playback depends on browser codec support.

## Stack and services

- `frontend/`: React, Vite, and Tailwind CSS user interface
- `backend/`: Go HTTP API for the music library and media files
- `auth/`: Django authentication service
- `python-backend/`: SQLAlchemy models and Alembic database migrations
- `db`: PostgreSQL 17 for authentication data and track metadata

Docker Compose starts the frontend, API, authentication service, PostgreSQL, a background import worker, and a one-shot migration service. The migration service creates or updates the music-library schema before the Go API starts.

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

## Media playback

The Go API serves original audio and cover files from the media directories.
Audio supports HTTP HEAD, byte ranges for seeking, and Last-Modified
revalidation. Paths are confined to the corresponding audio or covers
directory. Directory listings and unsupported file extensions return 404.

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
| Internet Archive | Enabled through the official Advanced Search API | Authenticated imports for eligible MP3/FLAC files; availability and rights are checked per item |
| Jamendo | Enabled only with `JAMENDO_CLIENT_ID` | Direct MP3 URL only when the API returns `audiodownload_allowed: true`; otherwise none |
| Bandcamp | Not available through its partner/account API | External Bandcamp search link |
| Qobuz | Not enabled without Qobuz-issued application credentials and approved access | External Qobuz store link; purchases remain on Qobuz |
| Free Music Archive | Disabled because its public API was shut down and unapproved search proxying is forbidden | External FMA search link |

Muzsky's search form submits to `/search/`, which its `robots.txt` disallows for automated access. The adapter uses `/suggest.php` and permitted public track pages instead. Its download host disallows all automated access, so WaveBox exposes only the track page.

The upload and Internet Archive import endpoints accept `Prefer: respond-async`.
They return HTTP 202 with an `importId`, and the authenticated owner can poll
`GET /api/auth/imports/{id}` for the result. The frontend uses this flow for uploads.

Import or backfill local audio files with the shared Python importer:

```bash
docker compose --profile tools run --rm importer
```

The importer preserves original audio files and detects identical content by SHA-256.
See [architecture](docs/ARCHITECTURE.md), [research](docs/OPEN_SOURCE_RESEARCH.md), and [roadmap](ROADMAP.md).

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

## MusicBrainz enrichment

Set `MUSICBRAINZ_CONTACT` in `.env` to an email address or HTTPS contact page.
Set `MUSICBRAINZ_FETCH_COVERS=1` if you want public front thumbnails from
Cover Art Archive. The cover option is off by default. MusicBrainz receives
title and artist, while WaveBox compares duration locally.

Run a batch after importing or backfilling tracks:

```bash
docker compose --profile tools run --rm importer python enrich_tracks.py --limit 25
```

Run the same command periodically to pick up new tracks and retry provider
failures. Tracks need a title, an artist, and a measured duration. WaveBox
records ambiguous matches as candidates and leaves existing tags and media
in place. The command also works on existing catalog entries with technical
metadata already backfilled.

## Imported playlists

Open **your playlists** and use **Imported playlists** to upload a UTF-8 CSV
or JSPF export, or enter a ListenBrainz playlist UUID. Private ListenBrainz
playlists require their owner's token on each remote request. WaveBox does
not retain the token.

CSV supports `title`, `artist`, optional `duration_ms`, and optional
`recording_mbid`. Each row needs a Recording MBID or both title and artist.
JSPF uses the `playlist.track` array and recognizes MusicBrainz recording
identifiers. Imports are limited to 500 entries and 1 MiB.

```csv
title,artist,duration_ms
Example track,Example artist,180000
```

Use **Recheck library** after new audio is imported. Use **Replace export file**
to refresh a file snapshot or **Sync ListenBrainz** to pull the current remote
order. Review ambiguous matches and choose the local version for each position.
Missing entries can be searched on Internet Archive and Jamendo. Eligible Archive
files can be imported through WaveBox, and Jamendo offers its authorized download
link when available. Playback follows the playlist order of matched tracks,
including repeated tracks.

The Django migration runs on startup after `docker compose up -d --build`.

## OpenSubsonic preview

Set `OPENSUBSONIC_API_KEY` in `.env` to a separate random key of at least
32 characters. For example, generate one with `openssl rand -hex 32`.
Start or recreate the API with `docker compose up -d --build api frontend`.
Rotate the key in `.env` and recreate the API to revoke the previous key.
An empty value disables the adapter.

Connect to the WaveBox base URL. The adapter serves `/rest/` through the
same origin as the frontend. It implements `getOpenSubsonicExtensions`,
`ping`, `tokenInfo`, song search with `search3`, `getSong`, `getCoverArt`,
and original audio via `stream`. Both bare names and `.view` work. Use
the `apiKey` query parameter and the optional `f=json` response format.
The extension discovery endpoint is public and returns JSON.

The key grants read access to the shared catalog. Use HTTPS outside
localhost and omit query strings from access logs that cover `/rest/`.
Clients that require password authentication, album or artist browsing,
playlist management, or transcoding need a broader implementation.

## Telegram Mini App

Set your bot's token in the server-only `TELEGRAM_BOT_TOKEN` variable in
`.env`. Set `DJANGO_ALLOWED_HOSTS` to your public domain,
`DJANGO_CSRF_TRUSTED_ORIGINS` to its HTTPS origin, `DJANGO_DEBUG=0`, and
`DJANGO_SECURE_COOKIES=1` for the HTTPS deployment.

Serve the built frontend over HTTPS and route `/api/auth/` to Django and
`/api/tracks`, `/api/external/`, `/audio/`, `/covers/`, and optional
`/rest/` to Go under the same origin. Configure the HTTPS URL as your
bot's Mini App in BotFather. Rebuild and restart Django to apply the
account-link migration.

On the first launch sign in with your WaveBox credentials and choose
**Link Telegram** on Home. On later launches choose **Sign in with
Telegram**. To unlink the account, use **Unlink Telegram** on Home.
After signing out or using an expired launch, reopen the Mini App to
obtain fresh launch data. Browser Telegram clients may require third-party
cookies for the embedded session.

[Telegram Mini Apps documentation](https://core.telegram.org/bots/webapps)
