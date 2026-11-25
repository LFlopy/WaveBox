import sqlalchemy as sa
from alembic import op


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "track_enrichment",
        sa.Column("track_id", sa.Integer(), sa.ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("recording_mbid", sa.String(36)),
        sa.Column("release_mbid", sa.String(36)),
        sa.Column("candidates", sa.JSON(), nullable=False),
        sa.Column("next_check", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_track_enrichment_recording_mbid", "track_enrichment", ["recording_mbid"])
    op.create_index("ix_track_enrichment_next_check", "track_enrichment", ["next_check"])
    op.create_table(
        "metadata_cache",
        sa.Column("key", sa.String(96), primary_key=True),
        sa.Column("status", sa.Integer(), nullable=False),
        sa.Column("body", sa.LargeBinary(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_metadata_cache_expires_at", "metadata_cache", ["expires_at"])


def downgrade():
    op.drop_table("metadata_cache")
    op.drop_table("track_enrichment")
