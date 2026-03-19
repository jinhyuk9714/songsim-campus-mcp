from __future__ import annotations

import songsim_campus.services as services_module
from songsim_campus.db import connection, init_db
from songsim_campus.services import (
    _is_restaurant_search_noise_candidate,
    _normalized_query_variants,
    _rank_restaurant_search_results,
    _resolve_restaurant_brand_query_token,
)


def _restaurant_row(
    *,
    row_id: int,
    slug: str,
    name: str,
    latitude: float,
    longitude: float,
    category: str = "cafe",
    tags: list[str] | None = None,
    description: str = "테스트 식당",
    source_tag: str = "test",
) -> dict[str, object]:
    return {
        "id": row_id,
        "slug": slug,
        "name": name,
        "category": category,
        "min_price": None,
        "max_price": None,
        "latitude": latitude,
        "longitude": longitude,
        "tags": tags or [],
        "description": description,
        "source_tag": source_tag,
        "last_synced_at": "2026-03-19T12:00:00+09:00",
    }


def _origin_place() -> dict[str, object]:
    return {
        "slug": "central-library",
        "latitude": 37.48643,
        "longitude": 126.80164,
    }


def test_resolve_restaurant_brand_query_token_normalizes_spacing_aliases():
    assert _resolve_restaurant_brand_query_token("매머드 커피") == "매머드익스프레스"
    assert _resolve_restaurant_brand_query_token("메가 커피") == "메가MGC커피"


def test_is_restaurant_search_noise_candidate_filters_parking_like_rows():
    parking_row = _restaurant_row(
        row_id=1,
        slug="starbucks-parking",
        name="스타벅스 역곡역DT점 주차장",
        latitude=37.48345,
        longitude=126.80935,
        tags=["교통시설"],
        description="역곡역DT점 주차장 안내",
    )
    cafe_row = _restaurant_row(
        row_id=2,
        slug="starbucks-dt",
        name="스타벅스 역곡역DT점",
        latitude=37.48354,
        longitude=126.80929,
        tags=["커피전문점", "스타벅스"],
        description="경기 부천시 소사구 경인로 485",
    )

    assert _is_restaurant_search_noise_candidate(parking_row) is True
    assert _is_restaurant_search_noise_candidate(cafe_row) is False


def test_resolve_restaurant_brand_query_token_handles_long_tail_aliases():
    assert _resolve_restaurant_brand_query_token("투썸") == "투썸플레이스"
    assert _resolve_restaurant_brand_query_token("coffee bean") == "커피빈"


def test_rank_restaurant_search_results_prefers_campus_adjacent_without_explicit_origin(
    app_env,
    monkeypatch,
):
    init_db()
    collapsed_query, compact_query = _normalized_query_variants("매머드 커피")
    assert collapsed_query is not None
    canonical_query = _resolve_restaurant_brand_query_token("매머드 커피")
    rows = [
        _restaurant_row(
            row_id=1,
            slug="mammoth-outer",
            name="매머드익스프레스 가상의외부점",
            latitude=37.48186,
            longitude=126.79612,
            tags=["커피전문점", "매머드익스프레스"],
        ),
        _restaurant_row(
            row_id=2,
            slug="mammoth-campus",
            name="매머드익스프레스 부천가톨릭대학교점",
            latitude=37.48556,
            longitude=126.80379,
            tags=["커피전문점", "매머드익스프레스"],
        ),
    ]
    walk_minutes_by_slug = {"mammoth-campus": 4, "mammoth-outer": 18}

    def fake_walk_minutes(conn, *, origin_place, restaurant_row):
        return walk_minutes_by_slug[str(restaurant_row["slug"])]

    monkeypatch.setattr(
        services_module,
        "_estimate_place_to_restaurant_walk_minutes",
        fake_walk_minutes,
    )

    with connection() as conn:
        items = _rank_restaurant_search_results(
            conn,
            rows,
            collapsed_query=collapsed_query,
            compact_query=compact_query,
            canonical_brand_query=canonical_query,
            ranking_origin_place=_origin_place(),
            origin_place=None,
            limit=5,
        )

    assert [item.slug for item in items[:2]] == ["mammoth-campus", "mammoth-outer"]
    assert all(item.distance_meters is None for item in items[:2])
    assert all(item.estimated_walk_minutes is None for item in items[:2])


def test_rank_restaurant_search_results_exposes_distance_only_with_explicit_origin(
    app_env,
    monkeypatch,
):
    init_db()
    collapsed_query, compact_query = _normalized_query_variants("매머드커피")
    assert collapsed_query is not None
    canonical_query = _resolve_restaurant_brand_query_token("매머드커피")
    row = _restaurant_row(
        row_id=1,
        slug="mammoth-campus",
        name="매머드익스프레스 부천가톨릭대학교점",
        latitude=37.48556,
        longitude=126.80379,
        tags=["커피전문점", "매머드익스프레스"],
    )
    origin_place = _origin_place()

    monkeypatch.setattr(
        services_module,
        "_estimate_place_to_restaurant_walk_minutes",
        lambda conn, *, origin_place, restaurant_row: 6,
    )

    with connection() as conn:
        hidden_only = _rank_restaurant_search_results(
            conn,
            [row],
            collapsed_query=collapsed_query,
            compact_query=compact_query,
            canonical_brand_query=canonical_query,
            ranking_origin_place=origin_place,
            origin_place=None,
            limit=5,
        )
        explicit_origin = _rank_restaurant_search_results(
            conn,
            [row],
            collapsed_query=collapsed_query,
            compact_query=compact_query,
            canonical_brand_query=canonical_query,
            ranking_origin_place=origin_place,
            origin_place=origin_place,
            limit=5,
        )

    assert hidden_only[0].distance_meters is None
    assert hidden_only[0].estimated_walk_minutes is None
    assert explicit_origin[0].distance_meters is not None
    assert explicit_origin[0].estimated_walk_minutes == 6
