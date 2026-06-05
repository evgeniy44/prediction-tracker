"""tz-aware timestamp columns

Revision ID: b7e2a4c1f9d3
Revises: cef3b9130690
Create Date: 2026-06-05

"""
from alembic import op
import sqlalchemy as sa


revision = 'b7e2a4c1f9d3'
down_revision = 'cef3b9130690'
branch_labels = None
depends_on = None


_COLS = [
    ("persons", "created_at"),
    ("raw_documents", "published_at"),
    ("raw_documents", "collected_at"),
    ("predictions", "verified_at"),
    ("predictions", "last_verify_error_at"),
]


def upgrade() -> None:
    for table, col in _COLS:
        op.alter_column(
            table, col,
            type_=sa.DateTime(timezone=True),
            postgresql_using=f"{col} AT TIME ZONE 'UTC'",
        )


def downgrade() -> None:
    for table, col in _COLS:
        op.alter_column(
            table, col,
            type_=sa.DateTime(timezone=False),
            postgresql_using=f"{col} AT TIME ZONE 'UTC'",
        )
