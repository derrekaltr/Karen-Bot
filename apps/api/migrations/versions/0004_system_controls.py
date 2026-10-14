"""System controls table (global kill switch etc.).

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-14

Existence-checked because the 0001 baseline creates from live ORM metadata.
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _has_table() -> bool:
    return sa.inspect(op.get_bind()).has_table("system_controls")


def upgrade() -> None:
    if not _has_table():
        op.create_table(
            "system_controls",
            sa.Column("key", sa.String(80), primary_key=True),
            sa.Column("value", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )


def downgrade() -> None:
    if _has_table():
        op.drop_table("system_controls")
