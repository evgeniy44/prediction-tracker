"""add verification metadata v2

Revision ID: 30fd925789cb
Revises: edb2e385f26b
Create Date: 2026-05-11 19:28:20.366565

"""
from alembic import op
import sqlalchemy as sa


revision = '30fd925789cb'
down_revision = 'edb2e385f26b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "predictions",
        sa.Column("prediction_strength", sa.String(length=10), nullable=True),
    )
    op.add_column(
        "predictions",
        sa.Column("max_horizon", sa.Date(), nullable=True),
    )
    op.add_column(
        "predictions",
        sa.Column("next_check_at", sa.Date(), nullable=True),
    )
    op.add_column(
        "predictions",
        sa.Column(
            "verify_attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "predictions",
        sa.Column("last_verify_error", sa.Text(), nullable=True),
    )
    op.add_column(
        "predictions",
        sa.Column("last_verify_error_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "idx_predictions_eligible",
        "predictions",
        ["verified_at", "next_check_at", "max_horizon"],
    )


def downgrade() -> None:
    op.drop_index("idx_predictions_eligible", table_name="predictions")
    op.drop_column("predictions", "last_verify_error_at")
    op.drop_column("predictions", "last_verify_error")
    op.drop_column("predictions", "verify_attempts")
    op.drop_column("predictions", "next_check_at")
    op.drop_column("predictions", "max_horizon")
    op.drop_column("predictions", "prediction_strength")
