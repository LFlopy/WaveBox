import hashlib
import os
import sys
from pathlib import Path
from urllib.parse import quote

from mutagen import File as MutagenFile
from mutagen import MutagenError
from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from sqlalchemy import create_engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from models import Artist, Track


class MissingMetadataError(ValueError):
    pass


def format_duration(seconds):
    total_seconds = round(seconds)
    return f"{total_seconds // 60}:{total_seconds % 60:02d}"


def cover_suffix(mime):
    return {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }.get(mime.lower(), ".bin")


def tag_value(tags, key):
    value = tags.get(key) if tags else None
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    return str(value or "").strip()


def pictures(audio):
    embedded = getattr(audio, "pictures", None)
    if embedded:
        return embedded
    return audio.tags.getall("APIC") if audio.tags and hasattr(audio.tags, "getall") else []


def read_metadata(audio_file):
    audio = MutagenFile(audio_file)
    if isinstance(audio, MP3):
        audio_format = "mp3"
        title_key, artist_key = "TIT2", "TPE1"
    elif isinstance(audio, FLAC):
        audio_format = "flac"
        title_key, artist_key = "title", "artist"
    else:
        raise ValueError("file is not a valid MP3 or FLAC")

    title = tag_value(audio.tags, title_key)
    artist_name = tag_value(audio.tags, artist_key)
    if not title or not artist_name or audio.info.length <= 0:
        raise MissingMetadataError("missing title, artist, or duration")

    bitrate = getattr(audio.info, "bitrate", None)
    return {
        "title": title,
        "artist_name": artist_name,
        "duration": format_duration(audio.info.length),
        "pictures": pictures(audio),
        "file_size": audio_file.stat().st_size,
        "audio_format": audio_format,
        "bit_depth": getattr(audio.info, "bits_per_sample", None),
        "sample_rate": getattr(audio.info, "sample_rate", None),
        "bitrate": round(bitrate) if bitrate else None,
    }


def import_file(session, audio_file, audio_path, covers_dir, metadata=None):
    covers_dir.mkdir(parents=True, exist_ok=True)
    existing = session.scalar(select(Track).where(Track.audio_path == audio_path))
    if existing is not None:
        return existing, False

    saved_cover = None
    try:
        metadata = metadata or read_metadata(audio_file)
        cover_path = ""
        if metadata["pictures"]:
            picture = metadata["pictures"][0]
            cover_name = hashlib.sha256(audio_path.encode()).hexdigest() + cover_suffix(picture.mime)
            saved_cover = covers_dir / cover_name
            saved_cover.write_bytes(picture.data)
            cover_path = f"/covers/{cover_name}"

        artist = session.scalar(select(Artist).where(Artist.name == metadata["artist_name"]))
        if artist is None:
            artist = Artist(name=metadata["artist_name"])
            session.add(artist)

        track = Track(
            title=metadata["title"],
            artist=artist,
            duration=metadata["duration"],
            cover_path=cover_path,
            audio_path=audio_path,
            file_size=metadata["file_size"],
            audio_format=metadata["audio_format"],
            bit_depth=metadata["bit_depth"],
            sample_rate=metadata["sample_rate"],
            bitrate=metadata["bitrate"],
        )
        session.add(track)
        session.commit()
        return track, True
    except Exception:
        session.rollback()
        if saved_cover is not None and saved_cover.exists():
            saved_cover.unlink()
        raise


def import_tracks(session, audio_dir, covers_dir):
    imported = 0
    skipped = 0
    failed = 0
    supported_suffixes = {".mp3", ".flac"}
    audio_files = sorted(
        path for path in audio_dir.rglob("*") if path.is_file() and path.suffix.lower() in supported_suffixes
    )
    for audio_file in audio_files:
        relative_path = audio_file.relative_to(audio_dir).as_posix()
        audio_path = f"/audio/{quote(relative_path)}"
        try:
            _, created = import_file(session, audio_file, audio_path, covers_dir)
            if not created:
                skipped += 1
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
