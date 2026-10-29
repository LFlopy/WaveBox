from alembic import op
import sqlalchemy as sa


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("tracks", sa.Column("file_size", sa.BigInteger(), nullable=True))
    op.add_column("tracks", sa.Column("audio_format", sa.String(length=16), nullable=True))
    op.add_column("tracks", sa.Column("bit_depth", sa.Integer(), nullable=True))
    op.add_column("tracks", sa.Column("sample_rate", sa.Integer(), nullable=True))
    op.add_column("tracks", sa.Column("bitrate", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("tracks", "bitrate")
    op.drop_column("tracks", "sample_rate")
    op.drop_column("tracks", "bit_depth")
    op.drop_column("tracks", "audio_format")
    op.drop_column("tracks", "file_size")
