from alembic import op
import sqlalchemy as sa


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "artists",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "tracks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("artist_id", sa.Integer(), nullable=False),
        sa.Column("duration", sa.String(length=16), nullable=False),
        sa.Column("cover_path", sa.String(length=1024), nullable=False),
        sa.Column("audio_path", sa.String(length=1024), nullable=False),
        sa.ForeignKeyConstraint(["artist_id"], ["artists.id"]),
        sa.UniqueConstraint("audio_path"),
    )
    op.execute(
        """
        INSERT INTO artists (name) VALUES ('Ado')
        ON CONFLICT (name) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO tracks (title, artist_id, duration, cover_path, audio_path)
        SELECT seed.title, artists.id, seed.duration, seed.cover_path, seed.audio_path
        FROM artists
        CROSS JOIN (VALUES
            ('Show', '3:10', '/covers/ado-show.JPG', '/audio/ado-show.mp3'),
            ('Usseewa', '3:25', '/covers/ado-usseewa.JPG', '/audio/ado-usseewa.mp3')
        ) AS seed(title, duration, cover_path, audio_path)
        WHERE artists.name = 'Ado'
        ON CONFLICT (audio_path) DO NOTHING
        """
    )


def downgrade():
    op.drop_table("tracks")
    op.drop_table("artists")
