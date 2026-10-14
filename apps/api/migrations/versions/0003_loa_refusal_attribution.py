"""Legal backbone: LOA capture, third-party-refusal flag, fee attribution.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-14

Existence-checked (the 0001 baseline creates from live ORM metadata, which
already includes these columns on fresh databases).
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

COLUMNS: list[tuple[str, sa.Column]] = [
    ("case_authorizations", sa.Column("loa_text", sa.Text(), nullable=True)),
    ("case_authorizations", sa.Column("signed_name", sa.String(200), nullable=True)),
    ("case_authorizations", sa.Column("signature_ip", sa.String(64), nullable=True)),
    ("case_authorizations", sa.Column("signature_user_agent", sa.String(400), nullable=True)),
    (
        "companies",
        sa.Column(
            "refuses_third_party", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    ),
    (
        "recovery_outcomes",
        sa.Column(
            "attribution", sa.String(40), nullable=False, server_default="karenbot_outreach"
        ),
    ),
]


def _existing(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    for table, column in COLUMNS:
        if column.name not in _existing(table):
            op.add_column(table, column)


def downgrade() -> None:
    for table, column in COLUMNS:
        if column.name in _existing(table):
            op.drop_column(table, column.name)
