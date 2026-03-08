"""Add portfolio_json column to users table

Revision ID: 002
Revises: 001
Create Date: 2024-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('portfolio_json', sa.Text(), nullable=True),
        schema='public',
    )


def downgrade() -> None:
    op.drop_column('users', 'portfolio_json', schema='public')
