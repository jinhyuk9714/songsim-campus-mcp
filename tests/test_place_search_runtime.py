from __future__ import annotations

from datetime import datetime

from songsim_campus.db import connection, init_db
from songsim_campus.repo import replace_campus_facilities, replace_places, replace_restaurants
from songsim_campus.services import list_estimated_empty_classrooms


def _place_row(
    *,
    slug: str,
    name: str,
    category: str = "building",
    aliases: list[str] | None = None,
    latitude: float | None = 37.4863,
    longitude: float | None = 126.8012,
) -> dict:
    return {
        "slug": slug,
        "name": name,
        "category": category,
        "aliases": aliases or [],
        "description": "",
        "latitude": latitude,
        "longitude": longitude,
        "opening_hours": {},
        "source_tag": "test",
        "last_synced_at": "2026-03-18T10:00:00+09:00",
    }


def _restaurant_row(*, slug: str, name: str, latitude: float, longitude: float) -> dict:
    return {
        "slug": slug,
        "name": name,
        "category": "cafe",
        "min_price": None,
        "max_price": None,
        "latitude": latitude,
        "longitude": longitude,
        "tags": [],
        "description": "",
        "source_tag": "test",
        "last_synced_at": "2026-03-18T10:00:00+09:00",
    }


def test_place_search_runtime_preserves_facility_parent_display_and_origin_resolution(app_env):
    from songsim_campus import place_search_runtime

    init_db()
    with connection() as conn:
        replace_places(
            conn,
            [
                _place_row(
                    slug="sophie-barat-hall",
                    name="학생미래인재관",
                    aliases=["학생회관", "학생센터", "학생식당"],
                    latitude=37.486466,
                    longitude=126.801297,
                ),
                _place_row(
                    slug="nicholls-hall",
                    name="니콜스관",
                    aliases=["니콜스", "N관"],
                    latitude=37.48612,
                    longitude=126.80211,
                ),
            ],
        )
        replace_campus_facilities(
            conn,
            [
                {
                    "facility_name": "CU",
                    "category": "편의점",
                    "phone": "032-343-3424",
                    "location_text": "학생회관 1층",
                    "hours_text": "평일 08:00~21:30",
                    "place_slug": "sophie-barat-hall",
                    "source_url": "https://www.catholic.ac.kr/ko/campuslife/restaurant.do",
                    "source_tag": "cuk_facilities",
                    "last_synced_at": "2026-03-18T10:00:00+09:00",
                }
            ],
        )
        replace_restaurants(
            conn,
            [
                _restaurant_row(
                    slug="student-center-cafe",
                    name="학생회관카페",
                    latitude=37.48649,
                    longitude=126.80131,
                )
            ],
        )

        places = place_search_runtime.search_places(conn, query="CU 어디야?", limit=1)
        composite_places = [
            place_search_runtime.search_places(conn, query=query, limit=1)
            for query in ("학생회관 1층 편의점", "학생회관 1층 24시간 편의점")
        ]
        origin_place = place_search_runtime.resolve_origin_place(conn, "학생식당")
        building = place_search_runtime.resolve_building_place(conn, "니콜스")
        classroom_payload = list_estimated_empty_classrooms(
            conn,
            building="니콜스",
            at=datetime.fromisoformat("2026-03-16T10:15:00+09:00"),
        )

    assert places[0].slug == "sophie-barat-hall"
    assert places[0].name == "학생회관"
    assert places[0].canonical_name == "학생미래인재관"
    assert places[0].matched_facility is not None
    assert places[0].matched_facility.name == "CU"
    assert places[0].matched_facility.location_hint == "학생회관 1층"
    assert all(result[0].slug == "sophie-barat-hall" for result in composite_places)
    assert all(result[0].name == "학생회관" for result in composite_places)
    assert all(result[0].canonical_name == "학생미래인재관" for result in composite_places)
    assert all(result[0].matched_facility is not None for result in composite_places)
    assert all(result[0].matched_facility.name == "CU" for result in composite_places)
    expected_location_hint = "학생회관 1층"
    assert all(
        result[0].matched_facility.location_hint == expected_location_hint
        for result in composite_places
    )
    assert origin_place["slug"] == "sophie-barat-hall"
    assert building.slug == "nicholls-hall"
    assert classroom_payload.building.slug == "nicholls-hall"
