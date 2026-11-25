import sqlalchemy as sa
from alembic import op


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("tracks", sa.Column("sha256", sa.String(64), nullable=True))
    op.add_column("tracks", sa.Column("codec", sa.String(32), nullable=True))
    op.add_column("tracks", sa.Column("channels", sa.Integer(), nullable=True))
    op.add_column("tracks", sa.Column("duration_ms", sa.Integer(), nullable=True))
    with op.batch_alter_table("tracks") as batch:
        batch.create_unique_constraint("uq_tracks_sha256", ["sha256"])


def downgrade():
    with op.batch_alter_table("tracks") as batch:
        batch.drop_constraint("uq_tracks_sha256", type_="unique")
        batch.drop_column("duration_ms")
        batch.drop_column("channels")
        batch.drop_column("codec")
        batch.drop_column("sha256")
