"""Encrypted token column to Text (Google token bundles exceed 500 chars).

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-15
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # batch_alter_table for SQLite compatibility (table-rebuild there;
    # plain ALTER on Postgres).
    with op.batch_alter_table("connected_accounts") as batch:
        batch.alter_column(
            "encrypted_token_reference",
            type_=sa.Text(),
            existing_type=sa.String(500),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("connected_accounts") as batch:
        batch.alter_column(
            "encrypted_token_reference",
            type_=sa.String(500),
            existing_type=sa.Text(),
            existing_nullable=True,
        )
