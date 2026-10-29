import hashlib
import os
import sys
from pathlib import Path
from urllib.parse import quote

from mutagen import MutagenError
from mutagen.mp3 import MP3
from sqlalchemy import create_engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from models import Artist, Track


def format_duration(seconds):
    total_seconds = round(seconds)
    return f"{total_seconds // 60}:{total_seconds % 60:02d}"


def cover_suffix(mime):
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }.get(mime.lower(), ".bin")


def import_tracks(session, audio_dir, covers_dir):
    imported = 0
    skipped = 0
    failed = 0
    covers_dir.mkdir(parents=True, exist_ok=True)

    audio_files = sorted(path for path in audio_dir.rglob("*") if path.is_file() and path.suffix.lower() == ".mp3")
    for audio_file in audio_files:
        relative_path = audio_file.relative_to(audio_dir).as_posix()
        audio_path = f"/audio/{quote(relative_path)}"
        if session.scalar(select(Track.id).where(Track.audio_path == audio_path)):
            skipped += 1
            continue

        saved_cover = None
        try:
            audio = MP3(audio_file)
            title = str(audio.tags.get("TIT2", "")).strip() if audio.tags else ""
            artist_name = str(audio.tags.get("TPE1", "")).strip() if audio.tags else ""
            if not title or not artist_name or audio.info.length <= 0:
                print(f"Skipped {audio_file}: missing title, artist, or duration", file=sys.stderr)
                skipped += 1
                continue

            cover_path = ""
            pictures = audio.tags.getall("APIC") if audio.tags else []
            if pictures:
                picture = pictures[0]
                cover_name = hashlib.sha256(audio_path.encode()).hexdigest() + cover_suffix(picture.mime)
                saved_cover = covers_dir / cover_name
                saved_cover.write_bytes(picture.data)
                cover_path = f"/covers/{cover_name}"

            artist = session.scalar(select(Artist).where(Artist.name == artist_name))
            if artist is None:
                artist = Artist(name=artist_name)
                session.add(artist)

            session.add(
                Track(
                    title=title,
                    artist=artist,
                    duration=format_duration(audio.info.length),
                    cover_path=cover_path,
                    audio_path=audio_path,
                )
            )
            session.commit()
            imported += 1
        except (MutagenError, OSError, SQLAlchemyError, ValueError) as exc:
            session.rollback()
            if saved_cover is not None and saved_cover.exists():
                saved_cover.unlink()
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
