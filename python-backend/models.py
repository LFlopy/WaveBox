from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Artist(Base):
    __tablename__ = "artists"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    tracks: Mapped[list["Track"]] = relationship(back_populates="artist")


class Track(Base):
    __tablename__ = "tracks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    artist_id: Mapped[int] = mapped_column(ForeignKey("artists.id"))
    duration: Mapped[str] = mapped_column(String(16))
    cover_path: Mapped[str] = mapped_column(String(1024))
    audio_path: Mapped[str] = mapped_column(String(1024), unique=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    audio_format: Mapped[str | None] = mapped_column(String(16), nullable=True)
    bit_depth: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sample_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bitrate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), unique=True)
    codec: Mapped[str | None] = mapped_column(String(32))
    channels: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    artist: Mapped[Artist] = relationship(back_populates="tracks")


class TrackEnrichment(Base):
    __tablename__ = "track_enrichment"

    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True)
    recording_mbid: Mapped[str | None] = mapped_column(String(36), index=True)
    release_mbid: Mapped[str | None] = mapped_column(String(36))
    candidates: Mapped[list[str]] = mapped_column(JSON)
    next_check: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class MetadataCache(Base):
    __tablename__ = "metadata_cache"

    key: Mapped[str] = mapped_column(String(96), primary_key=True)
    status: Mapped[int] = mapped_column(Integer)
    body: Mapped[bytes] = mapped_column(LargeBinary)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
