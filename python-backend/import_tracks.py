import binascii
import hashlib
import json
import math
import os
import subprocess
import sys
import unicodedata
from base64 import b64decode
from types import SimpleNamespace
from pathlib import Path
from urllib.parse import quote

from mutagen import File as MutagenFile
from mutagen import MutagenError
from mutagen.flac import Picture
from mutagen.id3 import ID3
from mutagen.mp4 import MP4Tags
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from models import Artist, Track


class MissingMetadataError(ValueError):
    pass


def format_duration(seconds):
    total_seconds = round(seconds)
    return f"{total_seconds // 60}:{total_seconds % 60:02d}"


AUDIO_FORMATS = {
    ".mp3": ("mp3", {"mp3"}),
    ".flac": ("flac", {"flac"}),
    ".ogg": ("ogg", {"vorbis", "opus", "flac"}),
    ".opus": ("ogg", {"opus"}),
    ".aac": ("aac", {"aac"}),
    ".m4a": ("mov", {"aac", "alac"}),
    ".wav": ("wav", None),
}
MAX_LIBRARY_FILE_SIZE = 100 * 1024 * 1024


def sha256_file(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def normalize_tag(value):
    value = "".join(char for char in str(value or "") if char.isprintable() or char.isspace())
    return " ".join(unicodedata.normalize("NFC", value).split())[:255]


def tag_value(tags, key):
    value = tags.get(key) if tags else None
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    return normalize_tag(value)


def embedded_cover(audio):
    if audio is None:
        return None
    tags = audio.tags or {}
    candidates = list(getattr(audio, "pictures", []))
    if hasattr(tags, "getall"):
        candidates.extend(tags.getall("APIC"))
    candidates.extend(SimpleNamespace(data=data, type=3) for data in tags.get("covr", []))
    for encoded in tags.get("metadata_block_picture", [])[:16]:
        if len(encoded) > 12 * 1024 * 1024:
            continue
        try:
            candidates.append(Picture(b64decode(encoded, validate=True)))
        except (ValueError, MutagenError, binascii.Error):
            continue
    for picture in sorted(candidates, key=lambda picture: picture.type != 3):
        data = picture.data
        if len(data) > 8 * 1024 * 1024:
            continue
        suffix = image_suffix(data)
        if suffix:
            return data, suffix
    return None


def image_suffix(data):
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    return None


def run_media_tool(command, timeout):
    try:
        return subprocess.run(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, timeout=timeout, check=True,
        ).stdout
    except subprocess.TimeoutExpired as exc:
        raise ValueError("Audio validation timed out") from exc
    except subprocess.CalledProcessError as exc:
        raise ValueError("Invalid or damaged audio file") from exc


def positive_int(value):
    return int(value) if str(value).isascii() and str(value).isdigit() and int(value) else None


def read_metadata(audio_file, fallback_title="", fallback_artist=""):
    file_size = audio_file.stat().st_size
    if file_size <= 0:
        raise ValueError("Empty audio file")
    suffix = audio_file.suffix.lower()
    if suffix not in AUDIO_FORMATS:
        raise ValueError("Unsupported audio format")
    demuxer, codecs = AUDIO_FORMATS[suffix]
    media_input = [
        "-max_alloc", "33554432", "-protocol_whitelist", "file",
        "-probesize", "5000000", "-f", demuxer,
    ]
    if demuxer == "mov":
        media_input += ["-enable_drefs", "0"]
    media_input += ["-i", str(audio_file.resolve())]
    probe = json.loads(run_media_tool([
        "ffprobe", "-v", "error", *media_input, "-select_streams", "a:0",
        "-show_entries",
        "stream=codec_name,duration,sample_rate,channels,bit_rate,bits_per_raw_sample,bits_per_sample:"
        "stream_tags=title,artist:format=duration,bit_rate:format_tags=title,artist",
        "-of", "json",
    ], timeout=10))
    streams = probe.get("streams", [])
    if not streams:
        raise ValueError("File does not contain an audio stream")
    stream = streams[0]
    container = probe.get("format", {})
    codec = stream.get("codec_name", "")
    if (codecs is not None and codec not in codecs) or (demuxer == "wav" and not codec.startswith("pcm_")):
        raise ValueError("File extension does not match its audio format")
    seconds = float(stream.get("duration") or container.get("duration") or 0)
    channels = positive_int(stream.get("channels"))
    sample_rate = positive_int(stream.get("sample_rate"))
    if not math.isfinite(seconds) or not 0 < seconds <= 86400 or not channels or channels > 32 or not sample_rate:
        raise ValueError("Invalid audio duration or stream properties")
    run_media_tool([
        "ffmpeg", "-v", "error", "-xerror", "-threads", "1", "-err_detect", "explode",
        *media_input, "-map", "0:a:0", "-vn", "-sn", "-dn", "-abort_on", "empty_output", "-f", "null", "-",
    ], timeout=45)

    audio = MutagenFile(audio_file)
    tags = audio.tags if audio is not None else {}
    probe_tags = {**container.get("tags", {}), **stream.get("tags", {})}
    title_key, artist_key = "title", "artist"
    if isinstance(tags, ID3):
        title_key, artist_key = "TIT2", "TPE1"
    elif isinstance(tags, MP4Tags):
        title_key, artist_key = "©nam", "©ART"
    title = tag_value(tags, title_key) or tag_value(probe_tags, "title") or normalize_tag(fallback_title)
    artist_name = tag_value(tags, artist_key) or tag_value(probe_tags, "artist") or normalize_tag(fallback_artist)
    if not title or not artist_name:
        raise MissingMetadataError("missing title or artist")

    return {
        "title": title,
        "artist_name": artist_name,
        "duration": format_duration(seconds),
        "duration_ms": round(seconds * 1000),
        "cover": embedded_cover(audio),
        "file_size": file_size,
        "audio_format": suffix[1:],
        "codec": codec,
        "channels": channels,
        "bit_depth": positive_int(stream.get("bits_per_raw_sample")) or positive_int(stream.get("bits_per_sample")),
        "sample_rate": sample_rate,
        "bitrate": positive_int(stream.get("bit_rate")) or positive_int(container.get("bit_rate")),
    }


def import_file(session, audio_file, audio_path, covers_dir, metadata=None, *, digest=None, destination=None):
    digest = digest or sha256_file(audio_file)
    saved_cover = None
    published_audio = False
    committing = False
    try:
        existing = session.scalar(select(Track).where(Track.audio_path == audio_path))
        if existing is None:
            existing = session.scalar(select(Track).where(Track.sha256 == digest))
        if existing is not None and (existing.audio_path != audio_path or existing.sha256 is not None):
            return existing, False
        metadata = metadata or read_metadata(audio_file)
        if session.get_bind().dialect.name == "postgresql":
            session.execute(text("SELECT pg_advisory_xact_lock(811429, 1)"))
        path_track = session.scalar(select(Track).where(Track.audio_path == audio_path))
        duplicate = session.scalar(select(Track).where(Track.sha256 == digest))
        if path_track is not None:
            if path_track.sha256 is None:
                if duplicate is None:
                    path_track.sha256 = digest
                path_track.codec = metadata.get("codec")
                path_track.channels = metadata.get("channels")
                path_track.duration_ms = metadata.get("duration_ms")
                session.commit()
            return path_track, False
        if duplicate is not None:
            return duplicate, False

        cover_path = ""
        cover = metadata.get("cover")
        if cover:
            cover_data, suffix = cover
            cover_name = hashlib.sha256(audio_path.encode()).hexdigest() + suffix
            cover_path = f"/covers/{cover_name}"

        artist = session.scalar(select(Artist).where(Artist.name == metadata["artist_name"]))
        if artist is None:
            artist = Artist(name=metadata["artist_name"])
            session.add(artist)

        track = Track(
            title=metadata["title"],
            artist=artist,
            duration=metadata["duration"],
            duration_ms=metadata.get("duration_ms"),
            cover_path=cover_path,
            audio_path=audio_path,
            sha256=digest,
            file_size=metadata["file_size"],
            audio_format=metadata["audio_format"],
            codec=metadata.get("codec"),
            channels=metadata.get("channels"),
            bit_depth=metadata["bit_depth"],
            sample_rate=metadata["sample_rate"],
            bitrate=metadata["bitrate"],
        )
        session.add(track)
        session.flush()

        if cover:
            covers_dir.mkdir(parents=True, exist_ok=True)
            saved_cover = covers_dir / cover_name
            saved_cover.write_bytes(cover_data)
        if destination is not None:
            destination.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.link(audio_file, destination)
                published_audio = True
            except FileExistsError:
                if destination.is_symlink() or sha256_file(destination) != digest:
                    raise ValueError("Audio storage path is already occupied")

        committing = True
        session.commit()
        return track, True
    except Exception:
        try:
            if published_audio and not committing:
                destination.unlink(missing_ok=True)
            if saved_cover is not None and not committing:
                saved_cover.unlink(missing_ok=True)
        finally:
            session.rollback()
        raise


def import_tracks(session, audio_dir, covers_dir):
    imported = 0
    skipped = 0
    failed = 0
    audio_files = sorted(
        path for path in audio_dir.rglob("*")
        if path.suffix.lower() in AUDIO_FORMATS and not path.is_symlink() and path.is_file()
    )
    for audio_file in audio_files:
        relative_path = audio_file.relative_to(audio_dir).as_posix()
        audio_path = f"/audio/{quote(relative_path)}"
        try:
            if audio_file.stat().st_size > MAX_LIBRARY_FILE_SIZE:
                raise ValueError("File exceeds the library import size limit")
            _, created = import_file(session, audio_file, audio_path, covers_dir)
            if not created:
                skipped += 1
                session.rollback()
                continue
            imported += 1
        except MissingMetadataError as exc:
            print(f"Skipped {audio_file}: {exc}", file=sys.stderr)
            skipped += 1
        except (MutagenError, OSError, SQLAlchemyError, ValueError) as exc:
            print(f"Failed {audio_file}: {exc}", file=sys.stderr)
            failed += 1

    return imported, skipped, failed


def main():
    audio_dir = Path(os.getenv("AUDIO_DIR", "/app/tracks/audio"))
    covers_dir = Path(os.getenv("COVERS_DIR", "/app/tracks/covers"))
    if not audio_dir.is_dir():
        raise SystemExit(f"Audio directory does not exist: {audio_dir}")

    engine = create_engine(os.environ["DATABASE_URL"])
    with Session(engine) as session:
        imported, skipped, failed = import_tracks(session, audio_dir, covers_dir)
    print(f"Imported: {imported}, skipped: {skipped}, failed: {failed}")


if __name__ == "__main__":
    main()
