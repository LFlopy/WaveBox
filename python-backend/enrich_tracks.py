import argparse
import hashlib
import http.client
import ipaddress
import json
import logging
import os
import re
import socket
import tempfile
import time
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlsplit
from uuid import UUID

from sqlalchemy import create_engine, delete, or_, select, text
from sqlalchemy.orm import Session

from import_tracks import image_suffix, normalize_tag
from models import Artist, MetadataCache, Track, TrackEnrichment


logger = logging.getLogger(__name__)
MAX_RESPONSE_SIZE = 1024 * 1024
RETRY_STATUSES = {429, 500, 502, 503, 504}


class MetadataUnavailable(Exception):
    pass


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def connect(self):
        addresses = socket.getaddrinfo(self.host, self.port, type=socket.SOCK_STREAM)
        public = []
        for record in addresses:
            address = ipaddress.ip_address(record[4][0])
            if address.is_global and not address.is_multicast:
                public.append(str(address))
        if not public:
            raise MetadataUnavailable("Provider resolved to a non-public address")
        self.sock = socket.create_connection((public[0], self.port), self.timeout)
        self.sock = self._context.wrap_socket(self.sock, server_hostname=self.host)


def fetch(url, user_agent, provider):
    deadline = time.monotonic() + 12
    for _ in range(5):
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        allowed = host == "musicbrainz.org" if provider == "mb" else (
            host in {"coverartarchive.org", "archive.org"} or host.endswith(".archive.org")
        )
        if parsed.scheme != "https" or not allowed or parsed.port not in (None, 443) or parsed.username is not None:
            raise MetadataUnavailable("Unexpected provider redirect")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise MetadataUnavailable("Provider request timed out")
        connection = PinnedHTTPSConnection(host, timeout=min(4, remaining))
        try:
            target = parsed.path + ("?" + parsed.query if parsed.query else "")
            accept = "application/json" if provider == "mb" else "image/*"
            connection.request("GET", target, headers={"User-Agent": user_agent, "Accept": accept})
            with connection.getresponse() as response:
                if provider == "caa" and response.status in {301, 302, 303, 307, 308} and response.getheader("Location"):
                    url = urljoin(url, response.getheader("Location"))
                    url = re.sub(r"^http://(?=[^/]*\barchive\.org(?:/|$))", "https://", url)
                    continue
                if response.status != 200:
                    return response.status, b"", response.getheader("Retry-After")
                body = bytearray()
                while len(body) <= MAX_RESPONSE_SIZE and time.monotonic() < deadline:
                    chunk = response.read1(min(65536, MAX_RESPONSE_SIZE + 1 - len(body)))
                    if not chunk:
                        return 200, bytes(body), None
                    body.extend(chunk)
                raise MetadataUnavailable("Provider response exceeded size or time limit")
        except (OSError, http.client.HTTPException, ValueError) as exc:
            raise MetadataUnavailable("Provider request failed") from exc
        finally:
            connection.close()
    raise MetadataUnavailable("Too many provider redirects")


def retry_delay(value, now):
    if value:
        try:
            if value.isascii() and value.isdecimal() and len(value) < 8:
                return max(5, min(604800, int(value)))
            return max(5, min(604800, (parsedate_to_datetime(value) - now).total_seconds()))
        except (TypeError, ValueError, OverflowError):
            pass
    return 60


def utc_time(value):
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def recording_payload(body):
    data = json.loads(body)
    recordings = data["recordings"]
    if type(data["count"]) is not int or not isinstance(recordings, list):
        raise ValueError("Invalid recording search response")
    return json.dumps({
        "count": data["count"],
        "recordings": [
            {
                "id": entry.get("id"),
                "title": entry.get("title"),
                "length": entry.get("length"),
                "disambiguation": entry.get("disambiguation"),
                "artist-credit": [
                    {
                        "name": credit.get("name") or credit.get("artist", {}).get("name"),
                        "joinphrase": credit.get("joinphrase") or "",
                    }
                    for credit in entry.get("artist-credit", [])
                ],
                "releases": [{"id": release.get("id")} for release in entry.get("releases", [])],
            }
            for entry in recordings
        ],
    }, separators=(",", ":")).encode()


def cached_request(session, provider, url, user_agent):
    key = provider + ":" + hashlib.sha256(url.encode()).hexdigest()
    now = datetime.now(UTC)
    row = session.get(MetadataCache, key)
    if row and utc_time(row.expires_at) > now:
        if row.status in RETRY_STATUSES:
            raise MetadataUnavailable("Provider retry is scheduled")
        return row.body if row.status == 200 else None

    gate_key = provider + ":rate"
    gate = session.get(MetadataCache, gate_key)
    if gate:
        delay = (utc_time(gate.expires_at) - now).total_seconds()
        if delay > 2:
            raise MetadataUnavailable("Provider requested backoff")
        if delay > 0:
            time.sleep(delay)
    try:
        status, body, retry_after = fetch(url, user_agent, provider)
        if status == 200 and provider == "mb":
            body = recording_payload(body)
        if status == 200 and provider == "caa" and not image_suffix(body):
            raise MetadataUnavailable("Unexpected cover response")
    except (MetadataUnavailable, ValueError, KeyError, TypeError, AttributeError):
        status, body, retry_after = 503, b"", None

    now = datetime.now(UTC)
    if status not in {200, 404} and status not in RETRY_STATUSES:
        status = 503
    delay = retry_delay(retry_after, now) if status in RETRY_STATUSES else 1
    session.merge(MetadataCache(key=gate_key, status=status, body=b"", expires_at=now + timedelta(seconds=delay)))
    ttl = timedelta(days=(30 if provider == "caa" else 7) if status == 200 else 1) if status in {200, 404} else timedelta(seconds=delay)
    session.merge(MetadataCache(key=key, status=status, body=body, expires_at=now + ttl))
    session.commit()
    if status in RETRY_STATUSES:
        raise MetadataUnavailable(f"Provider returned HTTP {status}")
    return body if status == 200 else None


def mbid(value):
    try:
        return str(UUID(value))
    except (AttributeError, TypeError, ValueError):
        return None


def recording_match(recordings, title, artist, duration_ms):
    candidates = {}
    for recording in recordings:
        identifier = mbid(recording.get("id"))
        credit = "".join(
            (entry.get("name") or entry.get("artist", {}).get("name") or "") + entry.get("joinphrase", "")
            for entry in recording.get("artist-credit", [])
        )
        length = recording.get("length")
        if (
            identifier and type(length) is int and abs(duration_ms - length) <= 2000
            and normalize_tag(recording.get("title")).casefold() == normalize_tag(title).casefold()
            and normalize_tag(credit).casefold() == normalize_tag(artist).casefold()
        ):
            candidates[identifier] = recording
    if len(candidates) != 1:
        return list(candidates), None, None
    identifier, recording = next(iter(candidates.items()))
    if recording.get("disambiguation"):
        return [identifier], None, None
    releases = {mbid(release.get("id")) for release in recording.get("releases", [])}
    return [identifier], identifier, next(iter(releases)) if len(releases) == 1 else None


def quoted_term(value):
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def enrich(session, track, artist, covers_dir, user_agent, fetch_cover):
    row = session.get(TrackEnrichment, track.id)
    candidates = row.candidates if row else []
    recording = row.recording_mbid if row else None
    release = row.release_mbid if row else None
    next_check = datetime.now(UTC) + timedelta(days=30)
    try:
        if recording is None:
            query = f"recording:{quoted_term(track.title)} AND artist:{quoted_term(artist)}"
            url = "https://musicbrainz.org/ws/2/recording?" + urlencode({"query": query, "fmt": "json", "limit": 25})
            body = cached_request(session, "mb", url, user_agent)
            if body:
                data = json.loads(body)
                recordings = data["recordings"]
                candidates, matched_recording, matched_release = recording_match(
                    recordings, track.title, artist, track.duration_ms,
                )
                if data["count"] > len(recordings):
                    matched_recording, matched_release = None, None
                recording, release = matched_recording, matched_release
        if fetch_cover and release and not track.cover_path:
            body = cached_request(
                session, "caa", f"https://coverartarchive.org/release/{release}/front-250", user_agent,
            )
            suffix = image_suffix(body) if body else None
            if suffix:
                covers_dir.mkdir(parents=True, exist_ok=True)
                name = "caa-" + release + suffix
                with tempfile.NamedTemporaryFile(dir=covers_dir, prefix=".caa-", delete=False) as output:
                    temporary = Path(output.name)
                    try:
                        output.write(body)
                        output.close()
                        os.chmod(temporary, 0o644)
                        temporary.replace(covers_dir / name)
                    finally:
                        temporary.unlink(missing_ok=True)
                track.cover_path = "/covers/" + name
    except (MetadataUnavailable, ValueError, KeyError, TypeError, AttributeError, OSError) as exc:
        logger.warning("Enrichment deferred for track %s (%s)", track.id, type(exc).__name__)
        next_check = datetime.now(UTC) + timedelta(minutes=15)
    session.merge(TrackEnrichment(
        track_id=track.id, recording_mbid=recording, release_mbid=release,
        candidates=candidates, next_check=next_check,
    ))
    session.commit()
    return recording is not None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=25)
    args = parser.parse_args()
    contact = os.getenv("MUSICBRAINZ_CONTACT", "").strip()
    if not re.fullmatch(r"(?:https://[^\s()]+|[^\s()@]+@[^\s()@]+)", contact) or not contact.isascii():
        parser.error("Set MUSICBRAINZ_CONTACT to an email address or HTTPS contact URL")
    if not 1 <= args.limit <= 250:
        parser.error("--limit must be between 1 and 250")
    user_agent = f"WaveBox/1.0 ({contact})"
    covers_dir = Path(os.getenv("COVERS_DIR", "/app/tracks/covers"))
    fetch_cover = os.getenv("MUSICBRAINZ_FETCH_COVERS") == "1"
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.connect() as connection, Session(connection) as session:
        if not session.scalar(text("SELECT pg_try_advisory_lock(811429, 2)")):
            raise SystemExit("Catalog enrichment is already running")
        try:
            now = datetime.now(UTC)
            session.execute(delete(MetadataCache).where(MetadataCache.expires_at < now))
            tracks = session.execute(
                select(Track, Artist.name).join(Track.artist).outerjoin(TrackEnrichment)
                .where(Track.duration_ms > 0, or_(
                    TrackEnrichment.track_id.is_(None), TrackEnrichment.next_check <= now,
                ))
                .order_by(TrackEnrichment.next_check.asc().nulls_first(), Track.id).limit(args.limit)
            ).all()
            matched = sum(enrich(session, track, artist, covers_dir, user_agent, fetch_cover) for track, artist in tracks)
            print(f"Checked: {len(tracks)}, recording matches: {matched}")
            session.commit()
        finally:
            session.rollback()
            session.execute(text("SELECT pg_advisory_unlock(811429, 2)"))
            session.commit()


if __name__ == "__main__":
    main()
