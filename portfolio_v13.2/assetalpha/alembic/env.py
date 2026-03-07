"""
alembic/env.py — Конфигурация Alembic для async SQLAlchemy.
"""
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# Читаем URL из переменных окружения
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import get_settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# URL из .env
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.db_url)

target_metadata = None  # Добавьте свои Base.metadata если используете ORM


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(settings.db_url, poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
