from __future__ import annotations

from datetime import date, datetime
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

JSON_COLUMNS = {
    "places": {"aliases_json": "aliases", "opening_hours_json": "opening_hours"},
    "restaurants": {"tags_json": "tags"},
    "restaurant_cache_items": {"tags_json": "tags"},
    "restaurant_hours_cache": {
        "raw_payload_json": "raw_payload",
        "opening_hours_json": "opening_hours",
    },
    "notices": {"labels_json": "labels"},
    "transport_guides": {"steps_json": "steps"},
    "profile_notice_preferences": {
        "categories_json": "categories",
        "keywords_json": "keywords",
    },
    "profile_interests": {"tags_json": "tags"},
    "sync_runs": {
        "params_json": "params",
        "summary_json": "summary",
    },
}

JSON_DEFAULTS = {
    "aliases_json": [],
    "opening_hours_json": {},
    "tags_json": [],
    "raw_payload_json": {},
    "labels_json": [],
    "steps_json": [],
    "categories_json": [],
    "keywords_json": [],
    "params_json": {},
    "summary_json": {},
}


def _executemany(
    conn: psycopg.Connection,
    query: str,
    params_seq: list[tuple[Any, ...]],
) -> None:
    if not params_seq:
        return
    with conn.cursor() as cursor:
        cursor.executemany(query, params_seq)


def _normalize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    return value


def _normalize_record(data: dict[str, Any]) -> dict[str, Any]:
    return {key: _normalize_value(value) for key, value in data.items()}


def _row_to_dict(table: str, row: dict[str, Any]) -> dict[str, Any]:
    data = _normalize_record(dict(row))
    for db_key, public_key in JSON_COLUMNS.get(table, {}).items():
        data[public_key] = data.pop(db_key, JSON_DEFAULTS[db_key]) or JSON_DEFAULTS[db_key]
    return data


def count_rows(conn: psycopg.Connection, table: str) -> int:
    row = conn.execute(f"SELECT COUNT(*) AS value FROM {table}").fetchone()
    return int(row["value"] or 0)


def replace_places(conn: psycopg.Connection, rows: list[dict[str, Any]]) -> None:
    conn.execute("TRUNCATE TABLE places RESTART IDENTITY CASCADE")
    _executemany(
        conn,
        """
        INSERT INTO places (
            slug, name, category, aliases_json, description,
            latitude, longitude, opening_hours_json, source_tag, last_synced_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        [
            (
                row["slug"],
                row["name"],
                row["category"],
                Jsonb(row.get("aliases", [])),
                row.get("description", ""),
                row.get("latitude"),
                row.get("longitude"),
                Jsonb(row.get("opening_hours", {})),
                row.get("source_tag", "demo"),
                row["last_synced_at"],
            )
            for row in rows
        ],
    )


def replace_courses(conn: psycopg.Connection, rows: list[dict[str, Any]]) -> None:
    conn.execute("TRUNCATE TABLE courses RESTART IDENTITY CASCADE")
    _executemany(
        conn,
        """
        INSERT INTO courses (
            year, semester, code, title, professor, department, section,
            day_of_week, period_start, period_end, room, raw_schedule,
            source_tag, last_synced_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        [
            (
                row["year"],
                row["semester"],
                row["code"],
                row["title"],
                row.get("professor"),
                row.get("department"),
                row.get("section"),
                row.get("day_of_week"),
                row.get("period_start"),
                row.get("period_end"),
                row.get("room"),
                row.get("raw_schedule"),
                row.get("source_tag", "demo"),
                row["last_synced_at"],
            )
            for row in rows
        ],
    )


def replace_restaurants(conn: psycopg.Connection, rows: list[dict[str, Any]]) -> None:
    conn.execute("TRUNCATE TABLE restaurants RESTART IDENTITY CASCADE")
    _executemany(
        conn,
        """
        INSERT INTO restaurants (
            slug, name, category, min_price, max_price, latitude,
            longitude, tags_json, description, source_tag, last_synced_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        [
            (
                row["slug"],
                row["name"],
                row["category"],
                row.get("min_price"),
                row.get("max_price"),
                row.get("latitude"),
                row.get("longitude"),
                Jsonb(row.get("tags", [])),
                row.get("description", ""),
                row.get("source_tag", "demo"),
                row["last_synced_at"],
            )
            for row in rows
        ],
    )


def replace_notices(conn: psycopg.Connection, rows: list[dict[str, Any]]) -> None:
    conn.execute("TRUNCATE TABLE notices RESTART IDENTITY CASCADE")
    _executemany(
        conn,
        """
        INSERT INTO notices (
            title, category, published_at, summary, labels_json,
            source_url, source_tag, last_synced_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        [
            (
                row["title"],
                row["category"],
                row["published_at"],
                row.get("summary", ""),
                Jsonb(row.get("labels", [])),
                row.get("source_url"),
                row.get("source_tag", "demo"),
                row["last_synced_at"],
            )
            for row in rows
        ],
    )


def search_places(
    conn: psycopg.Connection,
    query: str = "",
    category: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    normalized = f"%{query.strip()}%"
    sql = """
        SELECT * FROM places
        WHERE (
            %s = '%%'
            OR name ILIKE %s
            OR aliases_json::text ILIKE %s
            OR description ILIKE %s
        )
    """
    params: list[Any] = [normalized, normalized, normalized, normalized]
    if category:
        sql += " AND category = %s"
        params.append(category)
    sql += " ORDER BY name LIMIT %s"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_dict("places", row) for row in rows]


def list_places(conn: psycopg.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM places ORDER BY name").fetchall()
    return [_row_to_dict("places", row) for row in rows]


def get_place_by_slug_or_name(
    conn: psycopg.Connection,
    identifier: str,
) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM places WHERE slug = %s OR name = %s",
        (identifier, identifier),
    ).fetchone()
    return _row_to_dict("places", row) if row else None


def get_place_by_slug(conn: psycopg.Connection, slug: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM places WHERE slug = %s",
        (slug,),
    ).fetchone()
    return _row_to_dict("places", row) if row else None


def list_places_by_exact_name(conn: psycopg.Connection, name: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM places WHERE name = %s ORDER BY name",
        (name,),
    ).fetchall()
    return [_row_to_dict("places", row) for row in rows]


def list_places_by_exact_alias(conn: psycopg.Connection, alias: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT *
        FROM places
        WHERE EXISTS (
            SELECT 1
            FROM jsonb_array_elements_text(aliases_json) AS alias_item(value)
            WHERE alias_item.value = %s
        )
        ORDER BY name
        """,
        (alias,),
    ).fetchall()
    return [_row_to_dict("places", row) for row in rows]


def update_place_opening_hours(
    conn: psycopg.Connection,
    slug: str,
    opening_hours: dict[str, str],
    *,
    last_synced_at: str,
) -> None:
    row = conn.execute(
        "SELECT opening_hours_json FROM places WHERE slug = %s",
        (slug,),
    ).fetchone()
    if not row:
        return
    merged = dict(row["opening_hours_json"] or {})
    merged.update(opening_hours)
    conn.execute(
        """
        UPDATE places
        SET opening_hours_json = %s, last_synced_at = %s
        WHERE slug = %s
        """,
        (Jsonb(merged), last_synced_at, slug),
    )


def search_courses(
    conn: psycopg.Connection,
    query: str = "",
    *,
    year: int | None = None,
    semester: int | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    normalized = f"%{query.strip()}%"
    sql = """
        SELECT * FROM courses
        WHERE (
            %s = '%%'
            OR title ILIKE %s
            OR code ILIKE %s
            OR COALESCE(professor, '') ILIKE %s
        )
    """
    params: list[Any] = [normalized, normalized, normalized, normalized]
    if year is not None:
        sql += " AND year = %s"
        params.append(year)
    if semester is not None:
        sql += " AND semester = %s"
        params.append(semester)
    sql += " ORDER BY year DESC, semester DESC, title LIMIT %s"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return [_normalize_record(dict(row)) for row in rows]


def list_courses_snapshot(
    conn: psycopg.Connection,
    *,
    year: int | None = None,
    semester: int | None = None,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM courses WHERE 1=1"
    params: list[Any] = []
    if year is not None:
        sql += " AND year = %s"
        params.append(year)
    if semester is not None:
        sql += " AND semester = %s"
        params.append(semester)
    sql += " ORDER BY year DESC, semester DESC, title, code, section"
    rows = conn.execute(sql, params).fetchall()
    return [_normalize_record(dict(row)) for row in rows]


def list_courses_with_rooms(
    conn: psycopg.Connection,
    *,
    year: int,
    semester: int,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT *
        FROM courses
        WHERE year = %s
          AND semester = %s
          AND room IS NOT NULL
          AND BTRIM(room) <> ''
        ORDER BY room, day_of_week, period_start, title, code, section
        """,
        (year, semester),
    ).fetchall()
    return [_normalize_record(dict(row)) for row in rows]


def list_restaurants(conn: psycopg.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM restaurants ORDER BY name").fetchall()
    return [_row_to_dict("restaurants", row) for row in rows]


def list_restaurants_nearby(
    conn: psycopg.Connection,
    *,
    latitude: float,
    longitude: float,
    radius_meters: int,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            *,
            CAST(
                ST_Distance(
                    geom,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
                ) AS INTEGER
            ) AS distance_meters
        FROM restaurants
        WHERE geom IS NOT NULL
          AND ST_DWithin(
                geom,
                ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                %s
            )
        ORDER BY distance_meters, name
        """,
        (longitude, latitude, longitude, latitude, radius_meters),
    ).fetchall()
    return [_row_to_dict("restaurants", row) for row in rows]


def replace_restaurant_cache_snapshot(
    conn: psycopg.Connection,
    *,
    origin_slug: str,
    kakao_query: str,
    radius_meters: int,
    fetched_at: str,
    rows: list[dict[str, Any]],
) -> int:
    snapshot_rows = conn.execute(
        """
        SELECT id FROM restaurant_cache_snapshots
        WHERE origin_slug = %s AND kakao_query = %s AND radius_meters = %s
        """,
        (origin_slug, kakao_query, radius_meters),
    ).fetchall()
    snapshot_ids = [row["id"] for row in snapshot_rows]
    if snapshot_ids:
        conn.execute(
            "DELETE FROM restaurant_cache_items WHERE snapshot_id = ANY(%s)",
            (snapshot_ids,),
        )
        conn.execute(
            "DELETE FROM restaurant_cache_snapshots WHERE id = ANY(%s)",
            (snapshot_ids,),
        )

    snapshot_row = conn.execute(
        """
        INSERT INTO restaurant_cache_snapshots (
            origin_slug, kakao_query, radius_meters, fetched_at, source_tag
        ) VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """,
        (origin_slug, kakao_query, radius_meters, fetched_at, "kakao_local_cache"),
    ).fetchone()
    snapshot_id = int(snapshot_row["id"])
    _executemany(
        conn,
        """
        INSERT INTO restaurant_cache_items (
            snapshot_id, item_order, restaurant_id, slug, name, category,
            min_price, max_price, latitude, longitude, kakao_place_id,
            source_url, tags_json, description, source_tag, last_synced_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        [
            (
                snapshot_id,
                index,
                row["id"],
                row["slug"],
                row["name"],
                row["category"],
                row.get("min_price"),
                row.get("max_price"),
                row.get("latitude"),
                row.get("longitude"),
                row.get("kakao_place_id"),
                row.get("source_url"),
                Jsonb(row.get("tags", [])),
                row.get("description", ""),
                row.get("source_tag", "kakao_local_cache"),
                row["last_synced_at"],
            )
            for index, row in enumerate(rows, start=1)
        ],
    )
    return snapshot_id


def get_restaurant_cache_snapshot(
    conn: psycopg.Connection,
    *,
    origin_slug: str,
    kakao_query: str,
    radius_meters: int,
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM restaurant_cache_snapshots
        WHERE origin_slug = %s AND kakao_query = %s AND radius_meters = %s
        ORDER BY id DESC
        LIMIT 1
        """,
        (origin_slug, kakao_query, radius_meters),
    ).fetchone()
    return _normalize_record(dict(row)) if row else None


def list_restaurant_cache_items(
    conn: psycopg.Connection,
    snapshot_id: int,
    *,
    latitude: float | None = None,
    longitude: float | None = None,
    radius_meters: int | None = None,
) -> list[dict[str, Any]]:
    if latitude is not None and longitude is not None and radius_meters is not None:
        rows = conn.execute(
            """
            SELECT
                restaurant_id AS id,
                slug,
                name,
                category,
                min_price,
                max_price,
                latitude,
                longitude,
                kakao_place_id,
                source_url,
                tags_json,
                description,
                source_tag,
                last_synced_at,
                CAST(
                    ST_Distance(
                        geom,
                        ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
                    ) AS INTEGER
                ) AS distance_meters
            FROM restaurant_cache_items
            WHERE snapshot_id = %s
              AND geom IS NOT NULL
              AND ST_DWithin(
                    geom,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                    %s
                )
            ORDER BY item_order
            """,
            (longitude, latitude, snapshot_id, longitude, latitude, radius_meters),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT
                restaurant_id AS id,
                slug,
                name,
                category,
                min_price,
                max_price,
                latitude,
                longitude,
                kakao_place_id,
                source_url,
                tags_json,
                description,
                source_tag,
                last_synced_at
            FROM restaurant_cache_items
            WHERE snapshot_id = %s
            ORDER BY item_order
            """,
            (snapshot_id,),
        ).fetchall()
    return [_row_to_dict("restaurant_cache_items", row) for row in rows]


def get_restaurant_hours_cache(
    conn: psycopg.Connection,
    *,
    kakao_place_id: str,
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM restaurant_hours_cache
        WHERE kakao_place_id = %s
        LIMIT 1
        """,
        (kakao_place_id,),
    ).fetchone()
    return _row_to_dict("restaurant_hours_cache", row) if row else None


def upsert_restaurant_hours_cache(
    conn: psycopg.Connection,
    *,
    kakao_place_id: str,
    source_url: str | None,
    raw_payload: dict[str, Any],
    opening_hours: dict[str, str],
    fetched_at: str,
    source_tag: str = "kakao_place_detail_cache",
) -> None:
    conn.execute(
        """
        INSERT INTO restaurant_hours_cache (
            kakao_place_id, source_url, raw_payload_json,
            opening_hours_json, fetched_at, source_tag
        ) VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (kakao_place_id) DO UPDATE SET
            source_url = EXCLUDED.source_url,
            raw_payload_json = EXCLUDED.raw_payload_json,
            opening_hours_json = EXCLUDED.opening_hours_json,
            fetched_at = EXCLUDED.fetched_at,
            source_tag = EXCLUDED.source_tag
        """,
        (
            kakao_place_id,
            source_url,
            Jsonb(raw_payload),
            Jsonb(opening_hours),
            fetched_at,
            source_tag,
        ),
    )


def list_notices(
    conn: psycopg.Connection,
    category: str | list[str] | tuple[str, ...] | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM notices"
    params: list[Any] = []
    if category:
        if isinstance(category, (list, tuple)):
            sql += " WHERE category = ANY(%s)"
            params.append(list(category))
        else:
            sql += " WHERE category = %s"
            params.append(category)
    sql += " ORDER BY published_at DESC, id DESC LIMIT %s"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_dict("notices", row) for row in rows]


def replace_transport_guides(conn: psycopg.Connection, rows: list[dict[str, Any]]) -> None:
    conn.execute("TRUNCATE TABLE transport_guides RESTART IDENTITY CASCADE")
    _executemany(
        conn,
        """
        INSERT INTO transport_guides (
            mode, title, summary, steps_json, source_url, source_tag, last_synced_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        [
            (
                row["mode"],
                row["title"],
                row.get("summary", ""),
                Jsonb(row.get("steps", [])),
                row.get("source_url"),
                row.get("source_tag", "demo"),
                row["last_synced_at"],
            )
            for row in rows
        ],
    )


def list_transport_guides(
    conn: psycopg.Connection,
    mode: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM transport_guides"
    params: list[Any] = []
    if mode:
        sql += " WHERE mode = %s"
        params.append(mode)
    sql += " ORDER BY mode, title LIMIT %s"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_dict("transport_guides", row) for row in rows]


def create_sync_run(
    conn: psycopg.Connection,
    *,
    target: str,
    status: str,
    trigger: str = "manual",
    params: dict[str, Any],
    summary: dict[str, Any],
    error_text: str | None,
    started_at: str,
    finished_at: str | None = None,
) -> int:
    row = conn.execute(
        """
        INSERT INTO sync_runs (
            target, trigger, status, params_json, summary_json, error_text, started_at, finished_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            target,
            trigger,
            status,
            Jsonb(params),
            Jsonb(summary),
            error_text,
            started_at,
            finished_at,
        ),
    ).fetchone()
    return int(row["id"])


def update_sync_run(
    conn: psycopg.Connection,
    run_id: int,
    *,
    status: str,
    summary: dict[str, Any],
    error_text: str | None,
    finished_at: str | None,
) -> None:
    conn.execute(
        """
        UPDATE sync_runs
        SET status = %s, summary_json = %s, error_text = %s, finished_at = %s
        WHERE id = %s
        """,
        (status, Jsonb(summary), error_text, finished_at, run_id),
    )


def get_sync_run(conn: psycopg.Connection, run_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM sync_runs WHERE id = %s", (run_id,)).fetchone()
    return _row_to_dict("sync_runs", row) if row else None


def list_sync_runs(conn: psycopg.Connection, limit: int = 20) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM sync_runs
        ORDER BY started_at DESC, id DESC
        LIMIT %s
        """,
        (limit,),
    ).fetchall()
    return [_row_to_dict("sync_runs", row) for row in rows]


def find_sync_runs(
    conn: psycopg.Connection,
    *,
    target: str | None = None,
    trigger: str | None = None,
    status: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM sync_runs"
    params: list[Any] = []
    clauses: list[str] = []
    if target is not None:
        clauses.append("target = %s")
        params.append(target)
    if trigger is not None:
        clauses.append("trigger = %s")
        params.append(trigger)
    if status is not None:
        clauses.append("status = %s")
        params.append(status)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY started_at DESC, id DESC LIMIT %s"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_dict("sync_runs", row) for row in rows]


def get_latest_sync_run(
    conn: psycopg.Connection,
    *,
    target: str,
    trigger: str,
    status: str | None = None,
) -> dict[str, Any] | None:
    rows = find_sync_runs(conn, target=target, trigger=trigger, status=status, limit=1)
    return rows[0] if rows else None


def get_dataset_sync_state(conn: psycopg.Connection, table: str) -> dict[str, Any]:
    allowed = {"places", "courses", "notices", "transport_guides"}
    if table not in allowed:
        raise ValueError(f"Unsupported dataset table: {table}")
    row = conn.execute(
        f"SELECT COUNT(*) AS row_count, MAX(last_synced_at) AS last_synced_at FROM {table}"
    ).fetchone()
    data = _normalize_record(dict(row))
    return {
        "name": table,
        "row_count": int(data["row_count"] or 0),
        "last_synced_at": data["last_synced_at"],
    }


def try_advisory_lock(conn: psycopg.Connection, key: int) -> bool:
    row = conn.execute("SELECT pg_try_advisory_lock(%s) AS locked", (key,)).fetchone()
    return bool(row["locked"])


def release_advisory_lock(conn: psycopg.Connection, key: int) -> bool:
    row = conn.execute("SELECT pg_advisory_unlock(%s) AS unlocked", (key,)).fetchone()
    return bool(row["unlocked"])


def delete_stale_restaurant_cache_snapshots(
    conn: psycopg.Connection,
    *,
    older_than: str,
) -> dict[str, int]:
    rows = conn.execute(
        """
        SELECT id FROM restaurant_cache_snapshots
        WHERE fetched_at < %s
        """,
        (older_than,),
    ).fetchall()
    snapshot_ids = [int(row["id"]) for row in rows]
    if not snapshot_ids:
        return {
            "restaurant_cache_snapshots_deleted": 0,
            "restaurant_cache_items_deleted": 0,
        }
    item_row = conn.execute(
        """
        SELECT COUNT(*) AS value
        FROM restaurant_cache_items
        WHERE snapshot_id = ANY(%s)
        """,
        (snapshot_ids,),
    ).fetchone()
    conn.execute(
        "DELETE FROM restaurant_cache_snapshots WHERE id = ANY(%s)",
        (snapshot_ids,),
    )
    return {
        "restaurant_cache_snapshots_deleted": len(snapshot_ids),
        "restaurant_cache_items_deleted": int(item_row["value"] or 0),
    }


def delete_stale_restaurant_hours_cache(
    conn: psycopg.Connection,
    *,
    older_than: str,
) -> int:
    row = conn.execute(
        """
        WITH deleted AS (
            DELETE FROM restaurant_hours_cache
            WHERE fetched_at < %s
            RETURNING 1
        )
        SELECT COUNT(*) AS value FROM deleted
        """,
        (older_than,),
    ).fetchone()
    return int(row["value"] or 0)


def create_profile(
    conn: psycopg.Connection,
    *,
    profile_id: str,
    display_name: str,
    created_at: str,
    updated_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO profiles (id, display_name, created_at, updated_at)
        VALUES (%s, %s, %s, %s)
        """,
        (profile_id, display_name, created_at, updated_at),
    )


def get_profile(conn: psycopg.Connection, profile_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM profiles WHERE id = %s", (profile_id,)).fetchone()
    return _normalize_record(dict(row)) if row else None


def update_profile(
    conn: psycopg.Connection,
    profile_id: str,
    *,
    display_name: str | None = None,
    department: str | None = None,
    student_year: int | None = None,
    admission_type: str | None = None,
    updated_at: str,
    fields: set[str],
) -> None:
    assignments: list[str] = []
    params: list[Any] = []
    values = {
        "display_name": display_name,
        "department": department,
        "student_year": student_year,
        "admission_type": admission_type,
    }
    for field in ("display_name", "department", "student_year", "admission_type"):
        if field not in fields:
            continue
        assignments.append(f"{field} = %s")
        params.append(values[field])
    if not assignments:
        return
    assignments.append("updated_at = %s")
    params.extend([updated_at, profile_id])
    conn.execute(
        f"UPDATE profiles SET {', '.join(assignments)} WHERE id = %s",
        params,
    )


def replace_profile_courses(
    conn: psycopg.Connection,
    profile_id: str,
    rows: list[dict[str, Any]],
    *,
    updated_at: str,
) -> None:
    conn.execute("DELETE FROM profile_courses WHERE profile_id = %s", (profile_id,))
    _executemany(
        conn,
        """
        INSERT INTO profile_courses (
            profile_id, year, semester, code, section, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s)
        """,
        [
            (
                profile_id,
                row["year"],
                row["semester"],
                row["code"],
                row["section"],
                row.get("created_at", updated_at),
            )
            for row in rows
        ],
    )
    conn.execute(
        "UPDATE profiles SET updated_at = %s WHERE id = %s",
        (updated_at, profile_id),
    )


def list_profile_courses(
    conn: psycopg.Connection,
    profile_id: str,
    *,
    year: int | None = None,
    semester: int | None = None,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM profile_courses WHERE profile_id = %s"
    params: list[Any] = [profile_id]
    if year is not None:
        sql += " AND year = %s"
        params.append(year)
    if semester is not None:
        sql += " AND semester = %s"
        params.append(semester)
    sql += " ORDER BY year DESC, semester DESC, code, section"
    rows = conn.execute(sql, params).fetchall()
    return [_normalize_record(dict(row)) for row in rows]


def get_course_by_key(
    conn: psycopg.Connection,
    *,
    year: int,
    semester: int,
    code: str,
    section: str,
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM courses
        WHERE year = %s AND semester = %s AND code = %s AND COALESCE(section, '') = %s
        """,
        (year, semester, code, section),
    ).fetchone()
    return _normalize_record(dict(row)) if row else None


def save_profile_notice_preferences(
    conn: psycopg.Connection,
    profile_id: str,
    *,
    categories: list[str],
    keywords: list[str],
    updated_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO profile_notice_preferences (
            profile_id, categories_json, keywords_json, updated_at
        ) VALUES (%s, %s, %s, %s)
        ON CONFLICT(profile_id) DO UPDATE SET
            categories_json = EXCLUDED.categories_json,
            keywords_json = EXCLUDED.keywords_json,
            updated_at = EXCLUDED.updated_at
        """,
        (profile_id, Jsonb(categories), Jsonb(keywords), updated_at),
    )
    conn.execute(
        "UPDATE profiles SET updated_at = %s WHERE id = %s",
        (updated_at, profile_id),
    )


def get_profile_notice_preferences(
    conn: psycopg.Connection,
    profile_id: str,
) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM profile_notice_preferences WHERE profile_id = %s",
        (profile_id,),
    ).fetchone()
    return _row_to_dict("profile_notice_preferences", row) if row else None


def save_profile_interests(
    conn: psycopg.Connection,
    profile_id: str,
    *,
    tags: list[str],
    updated_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO profile_interests (profile_id, tags_json, updated_at)
        VALUES (%s, %s, %s)
        ON CONFLICT(profile_id) DO UPDATE SET
            tags_json = EXCLUDED.tags_json,
            updated_at = EXCLUDED.updated_at
        """,
        (profile_id, Jsonb(tags), updated_at),
    )
    conn.execute(
        "UPDATE profiles SET updated_at = %s WHERE id = %s",
        (updated_at, profile_id),
    )


def get_profile_interests(
    conn: psycopg.Connection,
    profile_id: str,
) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM profile_interests WHERE profile_id = %s",
        (profile_id,),
    ).fetchone()
    return _row_to_dict("profile_interests", row) if row else None
