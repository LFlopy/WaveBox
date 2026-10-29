from sqlalchemy import ForeignKey, String
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
    artist: Mapped[Artist] = relationship(back_populates="tracks")
