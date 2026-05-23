"""rename context to situation

Revision ID: cef3b9130690
Revises: 2c09afbbdcdf
Create Date: 2026-05-14

"""
from alembic import op


revision = 'cef3b9130690'
down_revision = '2c09afbbdcdf'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("predictions", "context", new_column_name="situation")


def downgrade() -> None:
    op.alter_column("predictions", "situation", new_column_name="context")
