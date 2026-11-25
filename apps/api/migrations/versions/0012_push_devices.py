"""Push devices: Expo push tokens per user for case notifications.

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-25

Existence-checked because the 0001 baseline creates from live ORM metadata.
"""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("push_devices"):
        op.create_table(
            "push_devices",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("token", sa.String(255), nullable=False, unique=True),
            sa.Column("platform", sa.String(20), nullable=False),
            sa.Column("disabled_at", sa.DateTime(timezone=True)),
            sa.Column("disabled_reason", sa.String(80)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_push_devices_user_id", "push_devices", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_push_devices_user_id", table_name="push_devices")
    op.drop_table("push_devices")
