from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from .settings import get_settings

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
SCHEMA_INIT_LOCK_KEY = 608_489_971_338_014_235
DBConnection = psycopg.Connection

_CREATE_EXTENSION_RE = re.compile(
    r"^CREATE\s+EXTENSION\s+IF\s+NOT\s+EXISTS\s+([a-zA-Z_][a-zA-Z0-9_]*)$",
    re.IGNORECASE,
)
_CREATE_TABLE_RE = re.compile(
    r"^CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+([a-zA-Z_][a-zA-Z0-9_]*)\b",
    re.IGNORECASE,
)
_ALTER_TABLE_ADD_COLUMN_RE = re.compile(
    r"^ALTER\s+TABLE\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+ADD\s+COLUMN\s+IF\s+NOT\s+EXISTS\s+([a-zA-Z_][a-zA-Z0-9_]*)\b",
    re.IGNORECASE,
)
_CREATE_INDEX_RE = re.compile(
    r"^CREATE\s+INDEX\s+IF\s+NOT\s+EXISTS\s+([a-zA-Z_][a-zA-Z0-9_]*)\b",
    re.IGNORECASE,
)


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
            if _schema_statement_needs_execution(conn, statement):
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


def _schema_statement_needs_execution(conn: DBConnection, statement: str) -> bool:
    normalized = " ".join(statement.split())
    if match := _CREATE_EXTENSION_RE.match(normalized):
        return not _extension_exists(conn, match.group(1))
    if match := _CREATE_TABLE_RE.match(normalized):
        return not _relation_exists(conn, match.group(1))
    if match := _ALTER_TABLE_ADD_COLUMN_RE.match(normalized):
        table_name, column_name = match.groups()
        return not _column_exists(conn, table_name, column_name)
    if match := _CREATE_INDEX_RE.match(normalized):
        return not _relation_exists(conn, match.group(1))
    return True


def _extension_exists(conn: DBConnection, extension_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM pg_extension WHERE extname = %s",
        (extension_name,),
    ).fetchone()
    return row is not None


def _relation_exists(conn: DBConnection, relation_name: str) -> bool:
    row = conn.execute(
        "SELECT to_regclass(%s)",
        (f"public.{relation_name}",),
    ).fetchone()
    return _first_column_value(row) is not None


def _column_exists(conn: DBConnection, table_name: str, column_name: str) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
          AND column_name = %s
        """,
        (table_name, column_name),
    ).fetchone()
    return row is not None


def _first_column_value(row):
    if row is None:
        return None
    if isinstance(row, dict):
        return next(iter(row.values()), None)
    return row[0]
