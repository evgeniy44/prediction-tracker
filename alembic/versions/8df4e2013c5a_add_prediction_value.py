"""add prediction_value

Revision ID: 8df4e2013c5a
Revises: 30fd925789cb
Create Date: 2026-05-13

"""
from alembic import op
import sqlalchemy as sa


revision = '8df4e2013c5a'
down_revision = '30fd925789cb'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "predictions",
        sa.Column("prediction_value", sa.String(length=10), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("predictions", "prediction_value")
