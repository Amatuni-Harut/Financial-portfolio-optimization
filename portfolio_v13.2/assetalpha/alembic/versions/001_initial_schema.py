"""001_initial_schema

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00

Начальная схема БД: таблицы users и prices.
"""
from alembic import op
import sqlalchemy as sa


revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Таблица пользователей
    op.create_table(
        "users",
        sa.Column("id",               sa.Integer(),     nullable=False),
        sa.Column("username",         sa.String(50),    nullable=False),
        sa.Column("email",            sa.String(255),   nullable=True),
        sa.Column("hashed_password",  sa.Text(),        nullable=False),
        sa.Column("knowledge_level",  sa.String(20),    nullable=False, server_default="beginner"),
        sa.Column("created_at",       sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
        schema="public",
    )

    # Таблица исторических цен
    op.create_table(
        "prices",
        sa.Column("Ticker", sa.String(20),          nullable=False),
        sa.Column("Date",   sa.DateTime(),           nullable=False),
        sa.Column("Open",   sa.Float(),              nullable=True),
        sa.Column("High",   sa.Float(),              nullable=True),
        sa.Column("Low",    sa.Float(),              nullable=True),
        sa.Column("Close",  sa.Float(),              nullable=True),
        sa.PrimaryKeyConstraint("Ticker", "Date"),
        schema="public",
    )
    op.create_index("idx_ticker", "prices", ["Ticker"], schema="public")
    op.create_index("idx_date",   "prices", ["Date"],   schema="public")


def downgrade() -> None:
    op.drop_table("prices", schema="public")
    op.drop_table("users",  schema="public")
