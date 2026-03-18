from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from .settings import get_settings

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
SCHEMA_INIT_LOCK_KEY = 608_489_971_338_014_235
DBConnection = psycopg.Connection


def get_connection() -> DBConnection:
    settings = get_settings()
    return psycopg.connect(
        settings.database_url,
        row_factory=dict_row,
    )


def init_db() -> None:
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    statements = [item.strip() for item in schema.split(";") if item.strip()]
    with get_connection() as conn:
        # Serialize schema bootstrap so API/MCP cold starts don't race on CREATE TABLE.
        conn.execute("SELECT pg_advisory_lock(%s)", (SCHEMA_INIT_LOCK_KEY,))
        for statement in statements:
            conn.execute(statement)
        conn.commit()


@contextmanager
def connection() -> Iterator[DBConnection]:
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
