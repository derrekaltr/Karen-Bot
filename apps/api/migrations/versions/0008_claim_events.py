"""Claimable-events feed: public incidents with policy-backed entitlements.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-30

Existence-checked because the 0001 baseline creates from live ORM metadata.
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def upgrade() -> None:
    inspector = _inspector()
    if not inspector.has_table("claim_events"):
        op.create_table(
            "claim_events",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id")),
            sa.Column("company_name", sa.String(200), nullable=False),
            sa.Column("title", sa.String(300), nullable=False),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("event_date", sa.Date(), nullable=False),
            sa.Column("region", sa.String(120)),
            sa.Column("entitlement", sa.Text(), nullable=False),
            sa.Column("eligibility", sa.Text(), nullable=False),
            sa.Column("how_to_claim", sa.Text(), nullable=False),
            sa.Column("claim_deadline", sa.Date()),
            sa.Column("category", sa.String(80), nullable=False),
            sa.Column("policy_id", sa.Uuid(), sa.ForeignKey("company_policies.id")),
            sa.Column("source_urls", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("created_by", sa.String(40), nullable=False),
            sa.Column("research_notes", sa.Text()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )


def downgrade() -> None:
    if _inspector().has_table("claim_events"):
        op.drop_table("claim_events")
