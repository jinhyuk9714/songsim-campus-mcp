from __future__ import annotations

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
        geom_index = conn.execute(
            """
            SELECT indexname
            FROM pg_indexes
            WHERE tablename = 'restaurants' AND indexname = 'idx_restaurants_geom'
            """
        ).fetchone()

    assert extension["extname"] == "postgis"
    assert places_geom["data_type"] == "USER-DEFINED"
    assert notices_labels["data_type"] == "jsonb"
    assert sync_started["data_type"] == "timestamp with time zone"
    assert profile_department["data_type"] == "text"
    assert profile_interests["data_type"] == "jsonb"
    assert geom_index["indexname"] == "idx_restaurants_geom"
