"""Database utilities for the E-Commerce Intelligence Platform.

Provides a reusable PostgreSQL connection layer for Supabase.
Credentials are loaded from environment variables.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError

load_dotenv()

logger = logging.getLogger(__name__)


def _get_required_env(name: str) -> str:
    """Return a required environment variable."""
    value = os.getenv(name)

    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            "Add it to your .env file."
        )

    return value


def get_database_url() -> URL:
    """Build the SQLAlchemy PostgreSQL connection URL for Supabase."""

    supabase_url = _get_required_env("SUPABASE_URL")
    database_password = _get_required_env("SUPABASE_DB_PASSWORD")

    # Remove protocol and trailing slash.
    project_host = (
        supabase_url
        .replace("https://", "")
        .replace("http://", "")
        .rstrip("/")
    )

    # Supabase project URL:
    # https://<project-ref>.supabase.co
    #
    # PostgreSQL host:
    # db.<project-ref>.supabase.co
    database_host = f"db.{project_host}"

    return URL.create(
        drivername="postgresql+psycopg2",
        username="postgres",
        password=database_password,
        host=database_host,
        port=5432,
        database="postgres",
    )


def get_engine() -> Engine:
    """Create and return a SQLAlchemy engine."""

    return create_engine(
        get_database_url(),
        pool_pre_ping=True,
        future=True,
    )


@contextmanager
def get_connection() -> Generator:
    """Provide a managed database connection."""

    engine = get_engine()

    try:
        with engine.connect() as connection:
            yield connection
    finally:
        engine.dispose()


def test_connection() -> bool:
    """Test the Supabase PostgreSQL connection."""

    try:
        with get_connection() as connection:
            result = connection.execute(text("SELECT 1"))
            result.fetchone()

        logger.info("Database connection successful.")
        return True

    except SQLAlchemyError as exc:
        logger.error("Database connection failed: %s", exc)
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    if test_connection():
        print("Database connection successful.")
    else:
        print("Database connection failed.")