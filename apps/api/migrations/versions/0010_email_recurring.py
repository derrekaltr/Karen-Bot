"""Email-receipt subscription detection: bank connection becomes optional.

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-30

Existence-checked because the 0001 baseline creates from live ORM metadata.
Batch mode for SQLite ALTER compatibility.
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def _columns() -> dict[str, dict]:
    inspector = sa.inspect(op.get_bind())
    return {c["name"]: c for c in inspector.get_columns("recurring_charges")}


def upgrade() -> None:
    columns = _columns()
    with op.batch_alter_table("recurring_charges") as batch:
        if columns.get("bank_connection_id", {}).get("nullable") is False:
            batch.alter_column(
                "bank_connection_id", existing_type=sa.Uuid(), nullable=True
            )
        if "source" not in columns:
            batch.add_column(
                sa.Column("source", sa.String(20), nullable=False, server_default="plaid")
            )


def downgrade() -> None:
    columns = _columns()
    with op.batch_alter_table("recurring_charges") as batch:
        if "source" in columns:
            batch.drop_column("source")
