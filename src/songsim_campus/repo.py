from __future__ import annotations

import json
import sqlite3
from typing import Any

JSON_COLUMNS = {
    "places": {"aliases_json": "aliases", "opening_hours_json": "opening_hours"},
    "restaurants": {"tags_json": "tags"},
    "notices": {"labels_json": "labels"},
    "transport_guides": {"steps_json": "steps"},
    "profile_notice_preferences": {
        "categories_json": "categories",
        "keywords_json": "keywords",
    },
}


def _row_to_dict(table: str, row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    for db_key, public_key in JSON_COLUMNS.get(table, {}).items():
        data[public_key] = json.loads(data.pop(db_key) or "[]")
    return data


def count_rows(conn: sqlite3.Connection, table: str) -> int:
    value = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    return int(value)


def replace_places(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> None:
    conn.execute("DELETE FROM places")
    conn.executemany(
        """
        INSERT INTO places (
            slug, name, category, aliases_json, description,
            latitude, longitude, opening_hours_json, source_tag, last_synced_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                row["slug"],
                row["name"],
                row["category"],
                json.dumps(row.get("aliases", []), ensure_ascii=False),
                row.get("description", ""),
                row.get("latitude"),
                row.get("longitude"),
                json.dumps(row.get("opening_hours", {}), ensure_ascii=False),
                row.get("source_tag", "demo"),
                row["last_synced_at"],
            )
            for row in rows
        ],
    )


def replace_courses(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> None:
    conn.execute("DELETE FROM courses")
    conn.executemany(
        """
        INSERT INTO courses (
            year, semester, code, title, professor, department, section,
            day_of_week, period_start, period_end, room, raw_schedule,
            source_tag, last_synced_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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


def replace_restaurants(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> None:
    conn.execute("DELETE FROM restaurants")
    conn.executemany(
        """
        INSERT INTO restaurants (
            slug, name, category, min_price, max_price, latitude,
            longitude, tags_json, description, source_tag, last_synced_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                json.dumps(row.get("tags", []), ensure_ascii=False),
                row.get("description", ""),
                row.get("source_tag", "demo"),
                row["last_synced_at"],
            )
            for row in rows
        ],
    )


def replace_notices(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> None:
    conn.execute("DELETE FROM notices")
    conn.executemany(
        """
        INSERT INTO notices (
            title, category, published_at, summary, labels_json,
            source_url, source_tag, last_synced_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                row["title"],
                row["category"],
                row["published_at"],
                row.get("summary", ""),
                json.dumps(row.get("labels", []), ensure_ascii=False),
                row.get("source_url"),
                row.get("source_tag", "demo"),
                row["last_synced_at"],
            )
            for row in rows
        ],
    )


def search_places(
    conn: sqlite3.Connection,
    query: str = "",
    category: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    normalized = f"%{query.strip().lower()}%"
    sql = """
        SELECT * FROM places
        WHERE (
            ? = '%%'
            OR lower(name) LIKE ?
            OR lower(aliases_json) LIKE ?
            OR lower(description) LIKE ?
        )
    """
    params: list[Any] = [normalized, normalized, normalized, normalized]
    if category:
        sql += " AND category = ?"
        params.append(category)
    sql += " ORDER BY name LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_dict("places", row) for row in rows]


def list_places(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM places ORDER BY name").fetchall()
    return [_row_to_dict("places", row) for row in rows]


def get_place_by_slug_or_name(conn: sqlite3.Connection, identifier: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM places WHERE slug = ? OR name = ?",
        (identifier, identifier),
    ).fetchone()
    return _row_to_dict("places", row) if row else None


def update_place_opening_hours(
    conn: sqlite3.Connection,
    slug: str,
    opening_hours: dict[str, str],
    *,
    last_synced_at: str,
) -> None:
    row = conn.execute("SELECT opening_hours_json FROM places WHERE slug = ?", (slug,)).fetchone()
    if not row:
        return
    merged = json.loads(row["opening_hours_json"] or "{}")
    merged.update(opening_hours)
    conn.execute(
        """
        UPDATE places
        SET opening_hours_json = ?, last_synced_at = ?
        WHERE slug = ?
        """,
        (json.dumps(merged, ensure_ascii=False), last_synced_at, slug),
    )


def search_courses(
    conn: sqlite3.Connection,
    query: str = "",
    *,
    year: int | None = None,
    semester: int | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    normalized = f"%{query.strip().lower()}%"
    sql = """
        SELECT * FROM courses
        WHERE (
            ? = '%%'
            OR lower(title) LIKE ?
            OR lower(code) LIKE ?
            OR lower(ifnull(professor, '')) LIKE ?
        )
    """
    params: list[Any] = [normalized, normalized, normalized, normalized]
    if year is not None:
        sql += " AND year = ?"
        params.append(year)
    if semester is not None:
        sql += " AND semester = ?"
        params.append(semester)
    sql += " ORDER BY year DESC, semester DESC, title LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def list_restaurants(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM restaurants ORDER BY name").fetchall()
    return [_row_to_dict("restaurants", row) for row in rows]


def list_notices(
    conn: sqlite3.Connection,
    category: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM notices"
    params: list[Any] = []
    if category:
        sql += " WHERE category = ?"
        params.append(category)
    sql += " ORDER BY published_at DESC, id DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_dict("notices", row) for row in rows]


def replace_transport_guides(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> None:
    conn.execute("DELETE FROM transport_guides")
    conn.executemany(
        """
        INSERT INTO transport_guides (
            mode, title, summary, steps_json, source_url, source_tag, last_synced_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                row["mode"],
                row["title"],
                row.get("summary", ""),
                json.dumps(row.get("steps", []), ensure_ascii=False),
                row.get("source_url"),
                row.get("source_tag", "demo"),
                row["last_synced_at"],
            )
            for row in rows
        ],
    )


def list_transport_guides(
    conn: sqlite3.Connection,
    mode: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM transport_guides"
    params: list[Any] = []
    if mode:
        sql += " WHERE mode = ?"
        params.append(mode)
    sql += " ORDER BY mode, title LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_dict("transport_guides", row) for row in rows]


def create_profile(
    conn: sqlite3.Connection,
    *,
    profile_id: str,
    display_name: str,
    created_at: str,
    updated_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO profiles (id, display_name, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        (profile_id, display_name, created_at, updated_at),
    )


def get_profile(conn: sqlite3.Connection, profile_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
    return dict(row) if row else None


def replace_profile_courses(
    conn: sqlite3.Connection,
    profile_id: str,
    rows: list[dict[str, Any]],
    *,
    updated_at: str,
) -> None:
    conn.execute("DELETE FROM profile_courses WHERE profile_id = ?", (profile_id,))
    conn.executemany(
        """
        INSERT INTO profile_courses (
            profile_id, year, semester, code, section, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
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
        "UPDATE profiles SET updated_at = ? WHERE id = ?",
        (updated_at, profile_id),
    )


def list_profile_courses(
    conn: sqlite3.Connection,
    profile_id: str,
    *,
    year: int | None = None,
    semester: int | None = None,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM profile_courses WHERE profile_id = ?"
    params: list[Any] = [profile_id]
    if year is not None:
        sql += " AND year = ?"
        params.append(year)
    if semester is not None:
        sql += " AND semester = ?"
        params.append(semester)
    sql += " ORDER BY year DESC, semester DESC, code, section"
    rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def get_course_by_key(
    conn: sqlite3.Connection,
    *,
    year: int,
    semester: int,
    code: str,
    section: str,
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM courses
        WHERE year = ? AND semester = ? AND code = ? AND ifnull(section, '') = ?
        """,
        (year, semester, code, section),
    ).fetchone()
    return dict(row) if row else None


def save_profile_notice_preferences(
    conn: sqlite3.Connection,
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
        ) VALUES (?, ?, ?, ?)
        ON CONFLICT(profile_id) DO UPDATE SET
            categories_json = excluded.categories_json,
            keywords_json = excluded.keywords_json,
            updated_at = excluded.updated_at
        """,
        (
            profile_id,
            json.dumps(categories, ensure_ascii=False),
            json.dumps(keywords, ensure_ascii=False),
            updated_at,
        ),
    )
    conn.execute(
        "UPDATE profiles SET updated_at = ? WHERE id = ?",
        (updated_at, profile_id),
    )


def get_profile_notice_preferences(
    conn: sqlite3.Connection,
    profile_id: str,
) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM profile_notice_preferences WHERE profile_id = ?",
        (profile_id,),
    ).fetchone()
    return _row_to_dict("profile_notice_preferences", row) if row else None
