"""User company profile: which companies a user does business with.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-30

Existence-checked because the 0001 baseline creates from live ORM metadata.
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def upgrade() -> None:
    if not _inspector().has_table("user_companies"):
        op.create_table(
            "user_companies",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id")),
            sa.Column("company_name", sa.String(200), nullable=False),
            sa.Column("source", sa.String(20), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("user_id", "company_name", name="uq_user_company_name"),
        )


def downgrade() -> None:
    if _inspector().has_table("user_companies"):
        op.drop_table("user_companies")
