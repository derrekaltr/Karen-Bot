"""Ops Council: team members, reviewable items, comments.

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-01

Existence-checked because the 0001 baseline creates from live ORM metadata.
"""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def upgrade() -> None:
    inspector = _inspector()
    if not inspector.has_table("ops_members"):
        op.create_table(
            "ops_members",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("email", sa.String(320), nullable=False, unique=True),
            sa.Column("display_name", sa.String(200), nullable=False),
            sa.Column("role", sa.String(20), nullable=False),
            sa.Column("added_by", sa.String(320)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
    if not inspector.has_table("ops_items"):
        op.create_table(
            "ops_items",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("kind", sa.String(30), nullable=False),
            sa.Column("title", sa.String(300), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("status", sa.String(30), nullable=False),
            sa.Column("created_by_email", sa.String(320), nullable=False),
            sa.Column("reviewer_email", sa.String(320)),
            sa.Column("recommendation", sa.Text()),
            sa.Column("source_urls", sa.JSON(), nullable=False),
            sa.Column("decided_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
    if not inspector.has_table("ops_comments"):
        op.create_table(
            "ops_comments",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("item_id", sa.Uuid(), sa.ForeignKey("ops_items.id"), nullable=False),
            sa.Column("author_email", sa.String(320), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )


def downgrade() -> None:
    inspector = _inspector()
    for table in ("ops_comments", "ops_items", "ops_members"):
        if inspector.has_table(table):
            op.drop_table(table)
