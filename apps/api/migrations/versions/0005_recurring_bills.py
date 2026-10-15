"""Recurring-bill discovery: bank connections, recurring charges, contact mode.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-15

Existence-checked because the 0001 baseline creates from live ORM metadata.
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def upgrade() -> None:
    inspector = _inspector()
    if not inspector.has_table("bank_connections"):
        op.create_table(
            "bank_connections",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("provider", sa.String(40), nullable=False),
            sa.Column("item_id", sa.String(200), nullable=False),
            sa.Column("institution_name", sa.String(200)),
            sa.Column("encrypted_access_token", sa.String(2000)),
            sa.Column("status", sa.String(40), nullable=False),
            sa.Column("revoked_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("user_id", "provider", "item_id"),
        )
    if not inspector.has_table("recurring_charges"):
        op.create_table(
            "recurring_charges",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column(
                "bank_connection_id",
                sa.Uuid(),
                sa.ForeignKey("bank_connections.id"),
                nullable=False,
            ),
            sa.Column("merchant_name", sa.String(200), nullable=False),
            sa.Column("normalized_merchant", sa.String(200), nullable=False),
            sa.Column("amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("currency", sa.String(3), nullable=False),
            sa.Column("cadence", sa.String(20), nullable=False),
            sa.Column("first_seen", sa.DateTime(timezone=True)),
            sa.Column("last_seen", sa.DateTime(timezone=True)),
            sa.Column("occurrences", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(30), nullable=False),
            sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id")),
            sa.Column("case_id", sa.Uuid(), sa.ForeignKey("cases.id")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint(
                "user_id", "normalized_merchant", "cadence", name="uq_recurring_user_merchant"
            ),
        )
    case_columns = {c["name"] for c in _inspector().get_columns("cases")}
    if "contact_mode" not in case_columns:
        op.add_column(
            "cases",
            sa.Column("contact_mode", sa.String(20), nullable=False, server_default="agent"),
        )


def downgrade() -> None:
    inspector = _inspector()
    if inspector.has_table("recurring_charges"):
        op.drop_table("recurring_charges")
    if inspector.has_table("bank_connections"):
        op.drop_table("bank_connections")
    if "contact_mode" in {c["name"] for c in _inspector().get_columns("cases")}:
        op.drop_column("cases", "contact_mode")
