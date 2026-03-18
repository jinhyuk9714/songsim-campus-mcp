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

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            self.close()
            return False

        def execute(self, statement, params=None):
            executed.append(statement if params is None else f"{statement}::{params!r}")
            return self

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
