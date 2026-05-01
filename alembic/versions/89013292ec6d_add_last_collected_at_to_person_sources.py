"""add last_collected_at to person_sources

Revision ID: 89013292ec6d
Revises: None
Create Date: 2026-05-01 23:08:56.314918

"""
from alembic import op
import sqlalchemy as sa


revision = '89013292ec6d'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "person_sources",
        sa.Column(
            "last_collected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_column("person_sources", "last_collected_at")
