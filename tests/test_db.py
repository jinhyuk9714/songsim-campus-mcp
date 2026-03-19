from __future__ import annotations

from pathlib import Path

import songsim_campus.db as db_module
from songsim_campus.db import connection, get_connection, init_db


def test_get_connection_uses_configured_database_url(app_env):
    conn = get_connection()
    try:
        row = conn.execute("SELECT current_database() AS name").fetchone()
    finally:
        conn.close()

    assert row["name"].startswith("songsim_test_")


def test_init_db_creates_postgis_schema(app_env):
    init_db()

    with connection() as conn:
        extension = conn.execute(
            "SELECT extname FROM pg_extension WHERE extname = 'postgis'"
        ).fetchone()
        places_geom = conn.execute(
            """
            SELECT data_type
            FROM information_schema.columns
            WHERE table_name = 'places' AND column_name = 'geom'
            """
        ).fetchone()
        notices_labels = conn.execute(
            """
            SELECT data_type
            FROM information_schema.columns
            WHERE table_name = 'notices' AND column_name = 'labels_json'
            """
        ).fetchone()
        sync_started = conn.execute(
            """
            SELECT data_type
            FROM information_schema.columns
            WHERE table_name = 'sync_runs' AND column_name = 'started_at'
            """
        ).fetchone()
        sync_trigger = conn.execute(
            """
            SELECT data_type
            FROM information_schema.columns
            WHERE table_name = 'sync_runs' AND column_name = 'trigger'
            """
        ).fetchone()
        profile_department = conn.execute(
            """
            SELECT data_type
            FROM information_schema.columns
            WHERE table_name = 'profiles' AND column_name = 'department'
            """
        ).fetchone()
        profile_interests = conn.execute(
            """
            SELECT data_type
            FROM information_schema.columns
            WHERE table_name = 'profile_interests' AND column_name = 'tags_json'
            """
        ).fetchone()
        restaurant_hours = conn.execute(
            """
            SELECT data_type
            FROM information_schema.columns
            WHERE table_name = 'restaurant_hours_cache' AND column_name = 'opening_hours_json'
            """
        ).fetchone()
        restaurant_cache_place_id = conn.execute(
            """
            SELECT data_type
            FROM information_schema.columns
            WHERE table_name = 'restaurant_cache_items' AND column_name = 'kakao_place_id'
            """
        ).fetchone()
        library_seat_remaining = conn.execute(
            """
            SELECT data_type
            FROM information_schema.columns
            WHERE table_name = 'library_seat_status_cache' AND column_name = 'remaining_seats'
            """
        ).fetchone()
        library_seat_synced = conn.execute(
            """
            SELECT data_type
            FROM information_schema.columns
            WHERE table_name = 'library_seat_status_cache' AND column_name = 'last_synced_at'
            """
        ).fetchone()
        geom_index = conn.execute(
            """
            SELECT indexname
            FROM pg_indexes
            WHERE tablename = 'restaurants' AND indexname = 'idx_restaurants_geom'
            """
        ).fetchone()
        course_room_index = conn.execute(
            """
            SELECT indexname
            FROM pg_indexes
            WHERE tablename = 'courses' AND indexname = 'idx_courses_year_semester_room'
            """
        ).fetchone()

    assert extension["extname"] == "postgis"
    assert places_geom["data_type"] == "USER-DEFINED"
    assert notices_labels["data_type"] == "jsonb"
    assert sync_started["data_type"] == "timestamp with time zone"
    assert sync_trigger["data_type"] == "text"
    assert profile_department["data_type"] == "text"
    assert profile_interests["data_type"] == "jsonb"
    assert restaurant_hours["data_type"] == "jsonb"
    assert restaurant_cache_place_id["data_type"] == "text"
    assert library_seat_remaining["data_type"] == "integer"
    assert library_seat_synced["data_type"] == "timestamp with time zone"
    assert geom_index["indexname"] == "idx_restaurants_geom"
    assert course_room_index["indexname"] == "idx_courses_year_semester_room"


def test_init_db_acquires_schema_lock_before_running_statements(monkeypatch, tmp_path):
    schema_path = tmp_path / "schema.sql"
    schema_path.write_text(
        "CREATE TABLE IF NOT EXISTS alpha (id integer);"
        "CREATE TABLE IF NOT EXISTS beta (id integer);",
        encoding="utf-8",
    )
    executed: list[str] = []

    class FakeResult:
        def __init__(self, row):
            self._row = row

        def fetchone(self):
            return self._row

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            self.close()
            return False

        def execute(self, statement, params=None):
            if statement == "SELECT pg_advisory_lock(%s)":
                executed.append(f"{statement}::{params!r}")
                return FakeResult((1,))
            if statement == "SELECT to_regclass(%s)":
                return FakeResult((None,))
            executed.append(statement if params is None else f"{statement}::{params!r}")
            return FakeResult(None)

        def commit(self):
            executed.append("COMMIT")

        def close(self):
            executed.append("CLOSE")

    fake_conn = FakeConnection()

    monkeypatch.setattr(db_module, "SCHEMA_PATH", Path(schema_path))
    monkeypatch.setattr(db_module, "get_connection", lambda: fake_conn)

    init_db()

    assert executed[0].startswith("SELECT pg_advisory_lock(")
    assert "CREATE TABLE IF NOT EXISTS alpha (id integer)" in executed[1]
    assert "CREATE TABLE IF NOT EXISTS beta (id integer)" in executed[2]
    assert executed[-2:] == ["COMMIT", "CLOSE"]


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _FakeConnection:
    def __init__(self) -> None:
        self.executed: list[str] = []
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, statement: str, params=None):
        if statement == "SELECT pg_advisory_lock(%s)":
            return _FakeResult((1,))
        if statement == "SELECT 1 FROM pg_extension WHERE extname = %s":
            return _FakeResult((1,))
        if statement == "SELECT to_regclass(%s)":
            relation_name = params[0]
            if relation_name in {
                "public.existing_table",
                "public.existing_idx",
            }:
                return _FakeResult((relation_name,))
            return _FakeResult((None,))
        if "FROM information_schema.columns" in statement:
            table_name, column_name = params
            if (table_name, column_name) == ("existing_table", "existing_column"):
                return _FakeResult((1,))
            return _FakeResult(None)
        self.executed.append(" ".join(statement.split()))
        return _FakeResult(None)

    def commit(self) -> None:
        self.committed = True


def test_init_db_executes_only_missing_schema_statements(
    monkeypatch,
    tmp_path: Path,
) -> None:
    schema_path = tmp_path / "schema.sql"
    schema_path.write_text(
        "\n".join(
            [
                "CREATE EXTENSION IF NOT EXISTS postgis;",
                "CREATE TABLE IF NOT EXISTS existing_table (id INTEGER PRIMARY KEY);",
                "CREATE TABLE IF NOT EXISTS missing_table (id INTEGER PRIMARY KEY);",
                "ALTER TABLE existing_table ADD COLUMN IF NOT EXISTS existing_column TEXT;",
                "ALTER TABLE existing_table ADD COLUMN IF NOT EXISTS missing_column TEXT;",
                "CREATE INDEX IF NOT EXISTS existing_idx ON existing_table(id);",
                "CREATE INDEX IF NOT EXISTS missing_idx ON missing_table(id);",
            ]
        ),
        encoding="utf-8",
    )
    fake_connection = _FakeConnection()

    monkeypatch.setattr(db_module, "SCHEMA_PATH", schema_path)
    monkeypatch.setattr(db_module, "get_connection", lambda: fake_connection)

    init_db()

    assert fake_connection.executed == [
        "CREATE TABLE IF NOT EXISTS missing_table (id INTEGER PRIMARY KEY)",
        "ALTER TABLE existing_table ADD COLUMN IF NOT EXISTS missing_column TEXT",
        "CREATE INDEX IF NOT EXISTS missing_idx ON missing_table(id)",
    ]
    assert fake_connection.committed is True
