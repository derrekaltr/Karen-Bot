"""Moral code: company size classification for targeting policy.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-14

Adds companies.size_class (default 'unclassified' = not targetable).
Existence-checked because the 0001 baseline creates tables from live ORM
metadata, which already includes this column on fresh databases.
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _has_column() -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(c["name"] == "size_class" for c in inspector.get_columns("companies"))


def upgrade() -> None:
    if not _has_column():
        op.add_column(
            "companies",
            sa.Column(
                "size_class", sa.String(40), nullable=False, server_default="unclassified"
            ),
        )


def downgrade() -> None:
    if _has_column():
        op.drop_column("companies", "size_class")
