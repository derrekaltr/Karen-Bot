"""Initial schema: all KarenBot tables from the ORM metadata.

Revision ID: 0001
Revises:
Create Date: 2026-10-14

The initial migration creates the schema directly from
karenbot.domain.models metadata so the ORM remains the single source of
truth for the baseline. Subsequent migrations must use explicit alembic ops.
"""

from alembic import op

from karenbot.db.base import Base
from karenbot.domain import models  # noqa: F401 - registers all tables

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
