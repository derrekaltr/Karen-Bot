"""Company generosity-intelligence column.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-19

Existence-checked (0001 baseline creates from live ORM metadata).
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def _has_column() -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(c["name"] == "intel" for c in inspector.get_columns("companies"))


def upgrade() -> None:
    if not _has_column():
        op.add_column(
            "companies",
            sa.Column("intel", sa.JSON(), nullable=False, server_default="{}"),
        )


def downgrade() -> None:
    if _has_column():
        op.drop_column("companies", "intel")
