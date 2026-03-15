from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import httpx
import pytest

from songsim_campus import repo
from songsim_campus.db import connection, init_db
from songsim_campus.ingest.kakao_places import KakaoPlace
from songsim_campus.repo import replace_places, replace_restaurants, update_place_opening_hours
from songsim_campus.seed import seed_demo
from songsim_campus.services import (
    InvalidRequestError,
    NotFoundError,
    _load_place_alias_overrides,
    _load_restaurant_search_aliases,
    _parse_campus_walk_graph,
    find_nearby_restaurants,
    get_class_periods,
    get_place,
    investigate_course_query_coverage,
    list_estimated_empty_classrooms,
    list_latest_notices,
    list_transport_guides,
    refresh_courses_from_subject_search,
    refresh_facility_hours_from_facilities_page,
    refresh_library_hours_from_library_page,
    refresh_notices_from_notice_board,
    refresh_places_from_campus_map,
    refresh_transport_guides_from_location_page,
    search_courses,
    search_places,
    search_restaurants,
    sync_official_snapshot,
)

FIXTURES_DIR = Path(__file__).with_name("fixtures")


def _fixture_json(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def _restaurant_row(
    *,
    slug: str,
    name: str,
    latitude: float,
    longitude: float,
    category: str = "korean",
    source_tag: str = "test",
) -> dict:
    return {
        "slug": slug,
        "name": name,
        "category": category,
        "min_price": 7000,
        "max_price": 9000,
        "latitude": latitude,
        "longitude": longitude,
        "tags": ["한식"],
        "description": "테스트 식당",
        "source_tag": source_tag,
        "last_synced_at": "2026-03-13T09:00:00+09:00",
    }


def test_get_class_periods_returns_ten_periods(app_env):
    init_db()
    seed_demo(force=True)
    periods = get_class_periods()
    assert len(periods) == 10
    assert periods[0].start == '09:00'
    assert periods[-1].end == '18:50'


def test_search_places_matches_alias(app_env):
    init_db()
    seed_demo(force=True)
    with connection() as conn:
        places = search_places(conn, query='중도')
    assert any(item.name == '중앙도서관' for item in places)


def test_search_places_prioritizes_exact_short_match_over_partial_noise(app_env):
    init_db()
    with connection() as conn:
        replace_places(
            conn,
            [
                {
                    "slug": "main-gate",
                    "name": "정문",
                    "category": "gate",
                    "aliases": ["학교 정문"],
                    "description": "성심교정의 정문",
                    "latitude": 37.4855,
                    "longitude": 126.8018,
                    "opening_hours": {},
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
                {
                    "slug": "startup-incubator",
                    "name": "창업보육센터",
                    "category": "building",
                    "aliases": [],
                    "description": "정문 옆 창업 지원 공간",
                    "latitude": 37.4857,
                    "longitude": 126.8020,
                    "opening_hours": {},
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
            ],
        )
        places = search_places(conn, query="정문", limit=10)

    assert [place.slug for place in places] == ["main-gate", "startup-incubator"]


@pytest.mark.parametrize(
    ("query", "expected_slug"),
    [
        ("중앙 도서관", "central-library"),
        ("니콜스 관", "nichols-hall"),
    ],
)
def test_search_places_normalizes_spacing_variants(app_env, query, expected_slug):
    init_db()
    seed_demo(force=True)
    with connection() as conn:
        places = search_places(conn, query=query, limit=5)

    assert places
    assert places[0].slug == expected_slug


def test_search_courses_normalizes_spacing_variants(app_env):
    init_db()
    seed_demo(force=True)
    with connection() as conn:
        courses = search_courses(conn, query="객체 지향", year=2026, semester=1, limit=5)

    assert courses
    assert courses[0].title == "객체지향프로그래밍설계"


def test_load_place_alias_overrides_contract():
    overrides = _load_place_alias_overrides()

    assert overrides["central-library"]["aliases"] == ["중도"]
    assert "학생식당" in overrides["sophie-barat-hall"]["aliases"]
    assert "트러스트짐" in overrides["sophie-barat-hall"]["aliases"]
    assert "카페 보나" in overrides["sophie-barat-hall"]["aliases"]
    assert "부온 프란조" in overrides["sophie-barat-hall"]["aliases"]
    assert "학생센터" in overrides["student-center"]["aliases"]
    assert overrides["nicholls-hall"]["aliases"] == ["니콜스"]
    assert overrides["kim-sou-hwan-hall"]["category"] == "building"


def test_load_restaurant_search_aliases_contract():
    aliases = _load_restaurant_search_aliases()

    assert aliases["매머드익스프레스"] == ["매머드커피", "매머드 커피", "매머드"]
    assert "메가커피" in aliases["메가MGC커피"]
    assert "이디야" in aliases["이디야커피"]


def test_search_places_matches_facility_tenant_alias_from_override_taxonomy(app_env):
    init_db()
    seed_demo(force=True)
    with connection() as conn:
        places = search_places(conn, query="트러스트짐", limit=3)

    assert places
    assert places[0].slug == "student-center"
    assert places[0].name == "학생회관"


def test_search_places_matches_building_synonym_from_override_taxonomy(app_env):
    init_db()
    seed_demo(force=True)
    with connection() as conn:
        places = search_places(conn, query="학생센터", limit=3)

    assert places
    assert places[0].slug == "student-center"
    assert places[0].name == "학생회관"


def test_search_restaurants_matches_brand_alias_with_spacing_normalization(app_env):
    init_db()
    with connection() as conn:
        replace_restaurants(
            conn,
            [
                _restaurant_row(
                    slug="mammoth",
                    name="매머드익스프레스 부천가톨릭대학교점",
                    category="cafe",
                    latitude=37.48556,
                    longitude=126.80379,
                ),
                _restaurant_row(
                    slug="mega",
                    name="메가MGC커피 부천가톨릭대점",
                    category="cafe",
                    latitude=37.48637,
                    longitude=126.80495,
                ),
                _restaurant_row(
                    slug="ediya",
                    name="이디야커피 가톨릭대점",
                    category="cafe",
                    latitude=37.48611,
                    longitude=126.80503,
                ),
            ],
        )
        items = search_restaurants(conn, query="매머드 커피", limit=3)

    assert [item.slug for item in items] == ["mammoth"]
    assert items[0].name == "매머드익스프레스 부천가톨릭대학교점"


def test_search_restaurants_matches_brand_alias_against_snapshot_name_variants(app_env):
    init_db()
    with connection() as conn:
        replace_restaurants(
            conn,
            [
                _restaurant_row(
                    slug="mammoth",
                    name="매머드익스프레스 부천가톨릭대학교점",
                    category="cafe",
                    latitude=37.48556,
                    longitude=126.80379,
                ),
                _restaurant_row(
                    slug="mega",
                    name="메가MGC커피 부천가톨릭대점",
                    category="cafe",
                    latitude=37.48637,
                    longitude=126.80495,
                ),
                _restaurant_row(
                    slug="ediya",
                    name="이디야커피 가톨릭대점",
                    category="cafe",
                    latitude=37.48611,
                    longitude=126.80503,
                ),
            ],
        )
        mega_items = search_restaurants(conn, query="메가커피", limit=3)
        ediya_items = search_restaurants(conn, query="이디야", limit=3)

    assert [item.slug for item in mega_items] == ["mega"]
    assert [item.slug for item in ediya_items] == ["ediya"]


def test_search_restaurants_snapshot_hit_skips_live_fetch(app_env):
    init_db()
    with connection() as conn:
        replace_restaurants(
            conn,
            [
                _restaurant_row(
                    slug="mammoth",
                    name="매머드익스프레스 부천가톨릭대학교점",
                    category="cafe",
                    latitude=37.48556,
                    longitude=126.80379,
                )
            ],
        )
        items = search_restaurants(
            conn,
            query="매머드커피",
            limit=5,
            kakao_client=ExplodingKakaoClient(),
        )

    assert [item.slug for item in items] == ["mammoth"]
    assert items[0].distance_meters is None
    assert items[0].estimated_walk_minutes is None


def test_search_restaurants_can_use_kakao_live_results_without_origin(app_env):
    init_db()
    seed_demo(force=True)

    class BrandKakaoClient:
        def __init__(self):
            self.calls: list[tuple[str, float | None, float | None, int]] = []

        def search_sync(self, query: str, *, x=None, y=None, radius: int = 1000):
            self.calls.append((query, x, y, radius))
            return [
                KakaoPlace(
                    name="매머드익스프레스 부천가톨릭대학교점",
                    category="음식점 > 카페 > 커피전문점",
                    address="경기 부천시 원미구 지봉로 43",
                    latitude=37.48556,
                    longitude=126.80379,
                    place_id="101",
                    place_url="https://place.map.kakao.com/101",
                )
            ]

    client = BrandKakaoClient()
    with connection() as conn:
        library = get_place(conn, "central-library")
        items = search_restaurants(
            conn,
            query="매머드커피",
            category="cafe",
            limit=5,
            kakao_client=client,
        )

    assert client.calls == [("매머드익스프레스", library.longitude, library.latitude, 15 * 75)]
    assert [item.name for item in items] == ["매머드익스프레스 부천가톨릭대학교점"]
    assert items[0].source_tag == "kakao_local"
    assert items[0].distance_meters is None
    assert items[0].estimated_walk_minutes is None


def test_search_restaurants_with_origin_returns_distance_fields_on_live_fallback(app_env):
    init_db()
    seed_demo(force=True)

    class OriginAwareBrandClient:
        def search_sync(self, query: str, *, x=None, y=None, radius: int = 1000):
            assert query == "매머드익스프레스"
            assert x is not None and y is not None
            assert radius == 15 * 75
            return [
                KakaoPlace(
                    name="매머드익스프레스 부천가톨릭대학교점",
                    category="음식점 > 카페 > 커피전문점",
                    address="경기 부천시 원미구 지봉로 43",
                    latitude=37.48556,
                    longitude=126.80379,
                    place_id="101",
                    place_url="https://place.map.kakao.com/101",
                )
            ]

    with connection() as conn:
        items = search_restaurants(
            conn,
            query="매머드커피",
            origin="중도",
            limit=5,
            kakao_client=OriginAwareBrandClient(),
        )

    assert [item.name for item in items] == ["매머드익스프레스 부천가톨릭대학교점"]
    assert items[0].distance_meters is not None
    assert items[0].estimated_walk_minutes is not None


def test_search_restaurants_uses_stale_cache_when_live_fetch_fails(app_env, monkeypatch):
    init_db()
    seed_demo(force=True)
    old_now = datetime.fromisoformat("2026-03-14T12:00:00+09:00")
    stale_now = datetime.fromisoformat("2026-03-14T20:30:00+09:00")

    class BrandKakaoClient:
        calls = 0

        def search_sync(self, query: str, *, x=None, y=None, radius: int = 1000):
            type(self).calls += 1
            assert query == "매머드익스프레스"
            return [
                KakaoPlace(
                    name="매머드익스프레스 부천가톨릭대학교점",
                    category="음식점 > 카페 > 커피전문점",
                    address="경기 부천시 원미구 지봉로 43",
                    latitude=37.48556,
                    longitude=126.80379,
                    place_id="101",
                    place_url="https://place.map.kakao.com/101",
                )
            ]

    monkeypatch.setattr("songsim_campus.services._now", lambda: old_now)
    with connection() as conn:
        first = search_restaurants(
            conn,
            query="매머드커피",
            limit=5,
            kakao_client=BrandKakaoClient(),
        )

    monkeypatch.setattr("songsim_campus.services._now", lambda: stale_now)
    with connection() as conn:
        second = search_restaurants(
            conn,
            query="매머드커피",
            limit=5,
            kakao_client=ExplodingKakaoClient(),
        )

    assert BrandKakaoClient.calls == 1
    assert [item.name for item in first] == [item.name for item in second]
    assert first[0].source_tag == "kakao_local"
    assert second[0].source_tag == "kakao_local_cache"
    assert second[0].distance_meters is None
    assert second[0].estimated_walk_minutes is None


def test_search_restaurants_live_fallback_applies_category_filter(app_env):
    init_db()
    seed_demo(force=True)

    class BrandKakaoClient:
        def search_sync(self, query: str, *, x=None, y=None, radius: int = 1000):
            return [
                KakaoPlace(
                    name="매머드익스프레스 부천가톨릭대학교점",
                    category="음식점 > 카페 > 커피전문점",
                    address="경기 부천시 원미구 지봉로 43",
                    latitude=37.48556,
                    longitude=126.80379,
                    place_id="101",
                    place_url="https://place.map.kakao.com/101",
                )
            ]

    with connection() as conn:
        items = search_restaurants(
            conn,
            query="매머드커피",
            category="korean",
            limit=5,
            kakao_client=BrandKakaoClient(),
        )

    assert items == []


def test_find_nearby_restaurants_sorted(app_env):
    init_db()
    seed_demo(force=True)
    with connection() as conn:
        items = find_nearby_restaurants(conn, origin='central-library', walk_minutes=20)
    assert items
    walk_minutes = [item.estimated_walk_minutes for item in items]
    assert walk_minutes == sorted(walk_minutes)


def test_find_nearby_restaurants_accepts_origin_alias(app_env):
    init_db()
    seed_demo(force=True)
    with connection() as conn:
        slug_items = find_nearby_restaurants(
            conn,
            origin="central-library",
            walk_minutes=15,
            limit=3,
        )
        alias_items = find_nearby_restaurants(conn, origin="중도", walk_minutes=15, limit=3)

    assert [item.name for item in alias_items] == [item.name for item in slug_items]
    assert all(item.origin == "central-library" for item in alias_items)


def test_find_nearby_restaurants_accepts_facility_alias_as_origin(app_env):
    init_db()
    seed_demo(force=True)
    with connection() as conn:
        slug_items = find_nearby_restaurants(
            conn,
            origin="student-center",
            walk_minutes=15,
            limit=3,
        )
        alias_items = find_nearby_restaurants(conn, origin="학생식당", walk_minutes=15, limit=3)

    assert [item.name for item in alias_items] == [item.name for item in slug_items]
    assert all(item.origin == "student-center" for item in alias_items)


def test_list_estimated_empty_classrooms_resolves_building_alias_and_sorts_available_rooms(app_env):
    init_db()
    seed_demo(force=True)
    with connection() as conn:
        repo.replace_courses(
            conn,
            [
                {
                    "year": 2026,
                    "semester": 1,
                    "code": "CSE110",
                    "title": "컴퓨팅사고",
                    "professor": "테스트교수",
                    "department": "컴퓨터정보공학부",
                    "section": "01",
                    "day_of_week": "월",
                    "period_start": 2,
                    "period_end": 3,
                    "room": "N101",
                    "raw_schedule": "월2~3(N101)",
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
                {
                    "year": 2026,
                    "semester": 1,
                    "code": "CSE332",
                    "title": "데이터베이스",
                    "professor": "김가톨",
                    "department": "컴퓨터정보공학부",
                    "section": "01",
                    "day_of_week": "월",
                    "period_start": 5,
                    "period_end": 6,
                    "room": "N201",
                    "raw_schedule": "월5~6(N201)",
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
                {
                    "year": 2026,
                    "semester": 1,
                    "code": "CSE210",
                    "title": "알고리즘",
                    "professor": "박성심",
                    "department": "컴퓨터정보공학부",
                    "section": "01",
                    "day_of_week": "화",
                    "period_start": 1,
                    "period_end": 2,
                    "room": "N301",
                    "raw_schedule": "화1~2(N301)",
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
            ],
        )
        evaluated_at = datetime.fromisoformat("2026-03-16T10:15:00+09:00")
        by_name = list_estimated_empty_classrooms(conn, building="니콜스관", at=evaluated_at)
        by_alias = list_estimated_empty_classrooms(conn, building="N관", at=evaluated_at)

    assert by_name.building.slug == "nichols-hall"
    assert by_alias.building.slug == "nichols-hall"
    assert by_name.evaluated_at == "2026-03-16T10:15:00+09:00"
    assert by_name.estimate_note.startswith("공식 시간표 기준 예상 공실입니다.")
    assert [item.room for item in by_name.items] == ["N301", "N201"]
    assert [item.room for item in by_alias.items] == ["N301", "N201"]
    assert all(item.available_now is True for item in by_name.items)
    assert by_name.items[0].next_occupied_at is None
    assert by_name.items[0].next_course_summary is None
    assert by_name.items[1].next_occupied_at == "2026-03-16T13:00:00+09:00"
    assert "데이터베이스" in (by_name.items[1].next_course_summary or "")
    assert "월5~6(N201)" in (by_name.items[1].next_course_summary or "")


def test_list_estimated_empty_classrooms_returns_empty_with_note_when_building_has_no_room_data(
    app_env,
):
    init_db()
    seed_demo(force=True)
    with connection() as conn:
        repo.replace_courses(
            conn,
            [
                {
                    "year": 2026,
                    "semester": 1,
                    "code": "CSE332",
                    "title": "데이터베이스",
                    "professor": "김가톨",
                    "department": "컴퓨터정보공학부",
                    "section": "01",
                    "day_of_week": "월",
                    "period_start": 5,
                    "period_end": 6,
                    "room": "N201",
                    "raw_schedule": "월5~6(N201)",
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                }
            ],
        )
        payload = list_estimated_empty_classrooms(
            conn,
            building="김수환관",
            at=datetime.fromisoformat("2026-03-16T10:15:00+09:00"),
        )

    assert payload.building.slug == "kim-sou-hwan-hall"
    assert payload.items == []
    assert "시간표 데이터를 찾지 못했습니다" in payload.estimate_note


def test_list_estimated_empty_classrooms_accepts_colloquial_building_alias(app_env):
    init_db()
    seed_demo(force=True)
    with connection() as conn:
        repo.replace_courses(
            conn,
            [
                {
                    "year": 2026,
                    "semester": 1,
                    "code": "CSE332",
                    "title": "데이터베이스",
                    "professor": "김가톨",
                    "department": "컴퓨터정보공학부",
                    "section": "01",
                    "day_of_week": "월",
                    "period_start": 5,
                    "period_end": 6,
                    "room": "N201",
                    "raw_schedule": "월5~6(N201)",
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                }
            ],
        )
        payload = list_estimated_empty_classrooms(
            conn,
            building="니콜스",
            at=datetime.fromisoformat("2026-03-16T10:15:00+09:00"),
        )

    assert payload.building.slug == "nichols-hall"
    assert payload.items[0].room == "N201"


def test_list_estimated_empty_classrooms_rejects_non_classroom_place(app_env):
    init_db()
    seed_demo(force=True)

    with connection() as conn, pytest.raises(InvalidRequestError, match="강의실 기반 건물"):
        list_estimated_empty_classrooms(
            conn,
            building="정문",
            at=datetime.fromisoformat("2026-03-16T10:15:00+09:00"),
        )


def test_list_latest_notices_employment_filter_includes_legacy_career_rows(app_env):
    init_db()
    with connection() as conn:
        repo.replace_notices(
            conn,
            [
                {
                    "title": "진로취업상담 안내",
                    "category": "career",
                    "published_at": "2026-03-12",
                    "summary": "",
                    "labels": ["취창업"],
                    "source_url": "https://example.edu/career",
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
                {
                    "title": "채용 설명회 안내",
                    "category": "employment",
                    "published_at": "2026-03-13",
                    "summary": "",
                    "labels": ["취업"],
                    "source_url": "https://example.edu/employment",
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
            ],
        )
        employment_items = list_latest_notices(conn, category="employment", limit=10)
        career_items = list_latest_notices(conn, category="career", limit=10)

    assert [item.title for item in employment_items] == [
        "채용 설명회 안내",
        "진로취업상담 안내",
    ]
    assert [item.title for item in career_items] == [
        "채용 설명회 안내",
        "진로취업상담 안내",
    ]


def test_list_latest_notices_normalizes_public_display_categories(app_env):
    init_db()
    with connection() as conn:
        repo.replace_notices(
            conn,
            [
                {
                    "title": "중앙도서관 자리 안내",
                    "category": "place",
                    "published_at": "2026-03-12",
                    "summary": "",
                    "labels": ["도서관"],
                    "source_url": "https://example.edu/place",
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
                {
                    "title": "채용 설명회 안내",
                    "category": "career",
                    "published_at": "2026-03-13",
                    "summary": "",
                    "labels": ["취업"],
                    "source_url": "https://example.edu/career",
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
                {
                    "title": "알 수 없는 분류 안내",
                    "category": "mystery",
                    "published_at": "2026-03-11",
                    "summary": "",
                    "labels": [],
                    "source_url": "https://example.edu/mystery",
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
            ],
        )
        notices = list_latest_notices(conn, limit=10)

    assert [(item.title, item.category) for item in notices] == [
        ("채용 설명회 안내", "employment"),
        ("중앙도서관 자리 안내", "general"),
        ("알 수 없는 분류 안내", "general"),
    ]


def test_list_estimated_empty_classrooms_prefers_official_realtime_data_when_available(
    app_env,
    monkeypatch,
):
    init_db()
    seed_demo(force=True)
    with connection() as conn:
        repo.replace_courses(
            conn,
            [
                {
                    "year": 2026,
                    "semester": 1,
                    "code": "CSE110",
                    "title": "컴퓨팅사고",
                    "professor": "테스트교수",
                    "department": "컴퓨터정보공학부",
                    "section": "01",
                    "day_of_week": "월",
                    "period_start": 2,
                    "period_end": 3,
                    "room": "N101",
                    "raw_schedule": "월2~3(N101)",
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
                {
                    "year": 2026,
                    "semester": 1,
                    "code": "CSE332",
                    "title": "데이터베이스",
                    "professor": "김가톨",
                    "department": "컴퓨터정보공학부",
                    "section": "01",
                    "day_of_week": "월",
                    "period_start": 5,
                    "period_end": 6,
                    "room": "N201",
                    "raw_schedule": "월5~6(N201)",
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
            ],
        )

    class RealtimeSource:
        def fetch_availability(self, *, building, at, year, semester):
            assert building.slug == "nichols-hall"
            assert year == 2026
            assert semester == 1
            return [
                {
                    "room": "N101",
                    "available_now": True,
                    "source_observed_at": "2026-03-16T10:10:00+09:00",
                },
                {
                    "room": "N201",
                    "available_now": False,
                    "source_observed_at": "2026-03-16T10:10:00+09:00",
                },
            ]

    monkeypatch.setattr(
        "songsim_campus.services._get_official_classroom_availability_source",
        lambda: RealtimeSource(),
    )

    with connection() as conn:
        payload = list_estimated_empty_classrooms(
            conn,
            building="니콜스관",
            at=datetime.fromisoformat("2026-03-16T10:15:00+09:00"),
        )

    assert [item.room for item in payload.items] == ["N101"]
    assert payload.items[0].availability_mode == "realtime"
    assert payload.items[0].source_observed_at == "2026-03-16T10:10:00+09:00"
    assert "공식 실시간 공실" in payload.estimate_note


def test_list_estimated_empty_classrooms_falls_back_per_room_when_realtime_coverage_is_partial(
    app_env,
    monkeypatch,
):
    init_db()
    seed_demo(force=True)
    with connection() as conn:
        repo.replace_courses(
            conn,
            [
                {
                    "year": 2026,
                    "semester": 1,
                    "code": "CSE332",
                    "title": "데이터베이스",
                    "professor": "김가톨",
                    "department": "컴퓨터정보공학부",
                    "section": "01",
                    "day_of_week": "월",
                    "period_start": 5,
                    "period_end": 6,
                    "room": "N201",
                    "raw_schedule": "월5~6(N201)",
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
                {
                    "year": 2026,
                    "semester": 1,
                    "code": "CSE210",
                    "title": "알고리즘",
                    "professor": "박성심",
                    "department": "컴퓨터정보공학부",
                    "section": "01",
                    "day_of_week": "화",
                    "period_start": 1,
                    "period_end": 2,
                    "room": "N301",
                    "raw_schedule": "화1~2(N301)",
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
            ],
        )

    class PartialRealtimeSource:
        def fetch_availability(self, *, building, at, year, semester):
            return [
                {
                    "room": "N201",
                    "available_now": True,
                    "source_observed_at": "2026-03-16T10:10:00+09:00",
                }
            ]

    monkeypatch.setattr(
        "songsim_campus.services._get_official_classroom_availability_source",
        lambda: PartialRealtimeSource(),
    )

    with connection() as conn:
        payload = list_estimated_empty_classrooms(
            conn,
            building="니콜스관",
            at=datetime.fromisoformat("2026-03-16T10:15:00+09:00"),
        )

    assert [item.room for item in payload.items] == ["N301", "N201"]
    assert payload.items[0].availability_mode == "estimated"
    assert payload.items[1].availability_mode == "realtime"
    assert "함께 사용합니다" in payload.estimate_note


def test_list_estimated_empty_classrooms_falls_back_to_estimated_when_realtime_source_fails(
    app_env,
    monkeypatch,
):
    init_db()
    seed_demo(force=True)

    class BrokenRealtimeSource:
        def fetch_availability(self, *, building, at, year, semester):
            raise RuntimeError("official classroom source failed")

    monkeypatch.setattr(
        "songsim_campus.services._get_official_classroom_availability_source",
        lambda: BrokenRealtimeSource(),
    )

    with connection() as conn:
        payload = list_estimated_empty_classrooms(
            conn,
            building="니콜스관",
            at=datetime.fromisoformat("2026-03-16T10:15:00+09:00"),
        )

    assert payload.items
    assert all(item.availability_mode == "estimated" for item in payload.items)
    assert "조회에 실패해" in payload.estimate_note


def test_find_nearby_restaurants_uses_campus_graph_for_external_routes(app_env):
    init_db()
    seed_demo(force=True)
    with connection() as conn:
        replace_restaurants(
            conn,
            [
                _restaurant_row(
                    slug="gate-bap",
                    name="정문백반",
                    latitude=37.48590,
                    longitude=126.80282,
                    source_tag="kakao_local",
                )
            ],
        )
        items = find_nearby_restaurants(conn, origin="central-library", walk_minutes=15)

    assert len(items) == 1
    assert items[0].estimated_walk_minutes == 6
    assert items[0].distance_meters is not None


def test_find_nearby_restaurants_fall_back_to_direct_distance_when_origin_is_not_in_graph(app_env):
    init_db()
    with connection() as conn:
        replace_places(
            conn,
            [
                {
                    "slug": "annex-lobby",
                    "name": "별관로비",
                    "category": "facility",
                    "aliases": [],
                    "description": "",
                    "latitude": 37.48590,
                    "longitude": 126.80282,
                    "opening_hours": {},
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                }
            ],
        )
        replace_restaurants(
            conn,
            [
                _restaurant_row(
                    slug="gate-bap",
                    name="정문백반",
                    latitude=37.48590,
                    longitude=126.80282,
                    source_tag="kakao_local",
                )
            ],
        )
        items = find_nearby_restaurants(conn, origin="annex-lobby", walk_minutes=15)

    assert len(items) == 1
    assert items[0].estimated_walk_minutes == 1


def test_parse_campus_walk_graph_rejects_invalid_edges():
    with pytest.raises(ValueError, match="unknown node"):
        _parse_campus_walk_graph(
            {
                "nodes": ["central-library", "main-gate"],
                "edges": [{"from": "central-library", "to": "north-gate", "walk_minutes": 3}],
            }
        )

    with pytest.raises(ValueError, match="positive"):
        _parse_campus_walk_graph(
            {
                "nodes": ["central-library", "main-gate"],
                "edges": [{"from": "central-library", "to": "main-gate", "walk_minutes": 0}],
            }
        )


def test_find_nearby_restaurants_raises_for_unknown_origin(app_env):
    init_db()
    seed_demo(force=True)

    with connection() as conn, pytest.raises(NotFoundError):
        find_nearby_restaurants(conn, origin='unknown-place')


def test_find_nearby_restaurants_raises_for_ambiguous_origin_alias(app_env):
    init_db()
    with connection() as conn:
        replace_places(
            conn,
            [
                {
                    "slug": "library-a",
                    "name": "중앙도서관A",
                    "category": "library",
                    "aliases": ["중도"],
                    "description": "",
                    "latitude": 37.48643,
                    "longitude": 126.80164,
                    "opening_hours": {},
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
                {
                    "slug": "library-b",
                    "name": "중앙도서관B",
                    "category": "library",
                    "aliases": ["중도"],
                    "description": "",
                    "latitude": 37.48653,
                    "longitude": 126.80174,
                    "opening_hours": {},
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
            ],
        )
        replace_restaurants(
            conn,
            [
                _restaurant_row(
                    slug="test-bap",
                    name="테스트백반",
                    latitude=37.4866,
                    longitude=126.8018,
                )
            ],
        )

        with pytest.raises(InvalidRequestError, match="Ambiguous origin"):
            find_nearby_restaurants(conn, origin="중도", walk_minutes=15)


def test_find_nearby_restaurants_raises_when_origin_has_no_coordinates(app_env):
    init_db()
    with connection() as conn:
        replace_places(
            conn,
            [
                {
                    "slug": "mystery-hall",
                    "name": "미스터리관",
                    "category": "building",
                    "aliases": [],
                    "description": "",
                    "latitude": None,
                    "longitude": None,
                    "opening_hours": {},
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                }
            ],
        )

    with connection() as conn, pytest.raises(NotFoundError):
        find_nearby_restaurants(conn, origin='mystery-hall')


class FakeKakaoClient:
    def __init__(self):
        self.calls = 0

    def search_sync(
        self,
        query: str,
        *,
        x: float | None = None,
        y: float | None = None,
        radius: int = 1000,
    ):
        self.calls += 1
        assert query == '한식'
        assert x is not None and y is not None
        assert radius > 0
        return [
            KakaoPlace(
                name='가톨릭백반',
                category='음식점 > 한식',
                address='경기 부천시 원미구',
                latitude=37.48674,
                longitude=126.80182,
                place_id='1',
                place_url='https://place.map.kakao.com/1',
            ),
            KakaoPlace(
                name='성심돈까스',
                category='음식점 > 한식',
                address='경기 부천시 원미구',
                latitude=37.48691,
                longitude=126.80114,
                place_id='2',
                place_url='https://place.map.kakao.com/2',
            ),
        ]


def test_find_nearby_restaurants_can_use_kakao_live_results(app_env):
    init_db()
    seed_demo(force=True)

    with connection() as conn:
        items = find_nearby_restaurants(
            conn,
            origin='central-library',
            category='korean',
            walk_minutes=15,
            kakao_client=FakeKakaoClient(),
        )

    assert [item.name for item in items] == ['가톨릭백반', '성심돈까스']
    assert all(item.source_tag == 'kakao_local' for item in items)
    assert all(item.origin == 'central-library' for item in items)


class ExplodingKakaoClient:
    def search_sync(
        self,
        query: str,
        *,
        x: float | None = None,
        y: float | None = None,
        radius: int = 1000,
    ):
        raise httpx.HTTPError('boom')


def test_find_nearby_restaurants_reuses_fresh_kakao_cache_without_refetch(app_env):
    init_db()
    seed_demo(force=True)
    client = FakeKakaoClient()

    with connection() as conn:
        first = find_nearby_restaurants(
            conn,
            origin='central-library',
            category='korean',
            walk_minutes=15,
            kakao_client=client,
        )
        second = find_nearby_restaurants(
            conn,
            origin='central-library',
            category='korean',
            walk_minutes=15,
            kakao_client=ExplodingKakaoClient(),
        )

    assert client.calls == 1
    assert [item.name for item in first] == [item.name for item in second]
    assert all(item.source_tag == 'kakao_local' for item in first)
    assert all(item.source_tag == 'kakao_local_cache' for item in second)


def test_find_nearby_restaurants_uses_stale_cache_when_live_fetch_fails(app_env, monkeypatch):
    init_db()
    seed_demo(force=True)
    old_now = datetime.fromisoformat('2026-03-14T12:00:00+09:00')
    stale_now = datetime.fromisoformat('2026-03-14T20:30:00+09:00')
    client = FakeKakaoClient()

    monkeypatch.setattr('songsim_campus.services._now', lambda: old_now)
    with connection() as conn:
        first = find_nearby_restaurants(
            conn,
            origin='central-library',
            category='korean',
            walk_minutes=15,
            kakao_client=client,
        )

    monkeypatch.setattr('songsim_campus.services._now', lambda: stale_now)
    with connection() as conn:
        second = find_nearby_restaurants(
            conn,
            origin='central-library',
            category='korean',
            walk_minutes=15,
            kakao_client=ExplodingKakaoClient(),
        )

    assert client.calls == 1
    assert [item.name for item in first] == [item.name for item in second]
    assert all(item.source_tag == 'kakao_local_cache' for item in second)


def test_find_nearby_restaurants_falls_back_to_local_restaurants_when_cache_expired_and_live_fails(
    app_env,
    monkeypatch,
):
    init_db()
    seed_demo(force=True)
    old_now = datetime.fromisoformat('2026-03-10T12:00:00+09:00')
    expired_now = datetime.fromisoformat('2026-03-14T20:30:00+09:00')

    monkeypatch.setattr('songsim_campus.services._now', lambda: old_now)
    with connection() as conn:
        find_nearby_restaurants(
            conn,
            origin='central-library',
            category='korean',
            walk_minutes=15,
            kakao_client=FakeKakaoClient(),
        )

    monkeypatch.setattr('songsim_campus.services._now', lambda: expired_now)
    with connection() as conn:
        items = find_nearby_restaurants(
            conn,
            origin='central-library',
            category='korean',
            walk_minutes=15,
            kakao_client=ExplodingKakaoClient(),
        )

    assert items
    assert all(item.source_tag not in {'kakao_local', 'kakao_local_cache'} for item in items)


def test_find_nearby_restaurants_cache_key_ignores_budget_open_now_and_limit(app_env):
    init_db()
    seed_demo(force=True)
    client = FakeKakaoClient()

    with connection() as conn:
        find_nearby_restaurants(
            conn,
            origin='central-library',
            category='korean',
            walk_minutes=15,
            kakao_client=client,
            limit=10,
        )
        filtered = find_nearby_restaurants(
            conn,
            origin='central-library',
            category='korean',
            walk_minutes=15,
            kakao_client=ExplodingKakaoClient(),
            budget_max=15000,
            open_now=True,
            limit=1,
        )

    assert client.calls == 1
    assert filtered == []


def test_find_nearby_restaurants_budget_max_requires_price_evidence(app_env):
    init_db()
    seed_demo(force=True)
    with connection() as conn:
        library = get_place(conn, "central-library")
        replace_restaurants(
            conn,
            [
                {
                    "slug": "budget-kimbap",
                    "name": "버짓김밥",
                    "category": "korean",
                    "min_price": 7000,
                    "max_price": 9000,
                    "latitude": library.latitude + 0.0001,
                    "longitude": library.longitude + 0.0001,
                    "tags": ["한식"],
                    "description": "가격 정보가 있는 김밥집",
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
                {
                    "slug": "mystery-price-cafe",
                    "name": "가격미상카페",
                    "category": "cafe",
                    "min_price": None,
                    "max_price": None,
                    "latitude": library.latitude + 0.0002,
                    "longitude": library.longitude + 0.0002,
                    "tags": ["카페"],
                    "description": "가격 정보가 없는 후보",
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
                {
                    "slug": "expensive-pasta",
                    "name": "비싼파스타",
                    "category": "western",
                    "min_price": 14000,
                    "max_price": 18000,
                    "latitude": library.latitude + 0.0003,
                    "longitude": library.longitude + 0.0003,
                    "tags": ["양식"],
                    "description": "예산 초과 후보",
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
            ],
        )
        items = find_nearby_restaurants(
            conn,
            origin="central-library",
            budget_max=10000,
            walk_minutes=15,
            limit=10,
        )

    assert [item.slug for item in items] == ["budget-kimbap"]


@pytest.mark.parametrize(
    ("hours_text", "at", "expected"),
    [
        ("중식 11:30 ~ 14:00", "2026-03-16T12:00:00+09:00", True),
        ("08:00-21:00", "2026-03-16T07:00:00+09:00", False),
        ("평일 08:00~19:00 토 10:00~16:00 (일/공휴일휴무)", "2026-03-15T11:00:00+09:00", False),
        ("mon-fri 08:30-22:00", "2026-03-16T09:00:00+09:00", True),
        ("24시간 운영", "2026-03-15T03:00:00+09:00", True),
        ("휴무", "2026-03-16T12:00:00+09:00", False),
        ("문의", "2026-03-16T12:00:00+09:00", None),
    ],
)
def test_find_nearby_restaurants_marks_open_now_from_facility_hours(
    app_env,
    hours_text,
    at,
    expected,
):
    init_db()
    seed_demo(force=True)
    with connection() as conn:
        library = get_place(conn, "central-library")
        replace_restaurants(
            conn,
            [
                _restaurant_row(
                    slug="cafe-dream",
                    name="카페드림",
                    latitude=library.latitude + 0.0001,
                    longitude=library.longitude + 0.0001,
                    category="cafe",
                )
            ],
        )
        update_place_opening_hours(
            conn,
            "central-library",
            {"카페드림": hours_text},
            last_synced_at="2026-03-13T09:00:00+09:00",
        )

        items = find_nearby_restaurants(
            conn,
            origin="central-library",
            walk_minutes=15,
            at=datetime.fromisoformat(at),
        )

    assert items[0].open_now is expected


def test_find_nearby_restaurants_open_now_filters_closed_and_unknown_candidates(app_env):
    init_db()
    seed_demo(force=True)
    with connection() as conn:
        library = get_place(conn, "central-library")
        replace_restaurants(
            conn,
            [
                _restaurant_row(
                    slug="cafe-dream",
                    name="카페드림",
                    latitude=library.latitude + 0.0001,
                    longitude=library.longitude + 0.0001,
                    category="cafe",
                ),
                _restaurant_row(
                    slug="unknown-bap",
                    name="알수없음식당",
                    latitude=library.latitude + 0.0002,
                    longitude=library.longitude + 0.0002,
                ),
            ],
        )
        update_place_opening_hours(
            conn,
            "central-library",
            {"카페드림": "평일 08:00~19:00 토 10:00~16:00 (일/공휴일휴무)"},
            last_synced_at="2026-03-13T09:00:00+09:00",
        )

        all_items = find_nearby_restaurants(
            conn,
            origin="central-library",
            walk_minutes=15,
            at=datetime.fromisoformat("2026-03-15T11:00:00+09:00"),
        )
        filtered = find_nearby_restaurants(
            conn,
            origin="central-library",
            walk_minutes=15,
            at=datetime.fromisoformat("2026-03-15T11:00:00+09:00"),
            open_now=True,
        )

    open_by_name = {item.name: item.open_now for item in all_items}
    assert open_by_name["카페드림"] is False
    assert open_by_name["알수없음식당"] is None
    assert filtered == []


def test_find_nearby_restaurants_prefers_official_facility_hours_before_kakao_detail(
    app_env,
    monkeypatch,
):
    init_db()
    seed_demo(force=True)
    now = datetime.fromisoformat("2026-03-14T12:00:00+09:00")
    monkeypatch.setattr("songsim_campus.services._now", lambda: now)
    calls = {"detail": 0}

    class ExplodingDetailClient:
        def fetch_sync(self, place_id: str):
            calls["detail"] += 1
            raise AssertionError("detail client should not be used for official facility matches")

    monkeypatch.setattr("songsim_campus.services.KakaoPlaceDetailClient", ExplodingDetailClient)

    with connection() as conn:
        repo.replace_restaurant_cache_snapshot(
            conn,
            origin_slug="central-library",
            kakao_query="카페",
            radius_meters=15 * 75,
            fetched_at="2026-03-14T10:00:00+09:00",
            rows=[
                {
                    "id": -1,
                    "slug": "kakao-cafe-dream",
                    "name": "카페드림",
                    "category": "cafe",
                    "min_price": None,
                    "max_price": None,
                    "latitude": 37.48695,
                    "longitude": 126.79995,
                    "tags": ["카페"],
                    "description": "테스트 카페",
                    "source_tag": "kakao_local_cache",
                    "last_synced_at": "2026-03-14T10:00:00+09:00",
                    "kakao_place_id": "242731511",
                    "source_url": "https://place.map.kakao.com/242731511",
                }
            ],
        )
        update_place_opening_hours(
            conn,
            "central-library",
            {"카페드림": "평일 08:00~19:00 토 10:00~16:00 (일/공휴일휴무)"},
            last_synced_at="2026-03-13T09:00:00+09:00",
        )

        items = find_nearby_restaurants(
            conn,
            origin="central-library",
            category="cafe",
            walk_minutes=15,
            at=datetime.fromisoformat("2026-03-15T11:00:00+09:00"),
        )

    assert items[0].open_now is False
    assert calls["detail"] == 0


def test_find_nearby_restaurants_reuses_fresh_kakao_hours_cache(app_env, monkeypatch):
    init_db()
    seed_demo(force=True)
    now = datetime.fromisoformat("2026-03-14T12:00:00+09:00")
    monkeypatch.setattr("songsim_campus.services._now", lambda: now)
    calls = {"detail": 0}

    class ExplodingDetailClient:
        def fetch_sync(self, place_id: str):
            calls["detail"] += 1
            raise AssertionError("fresh hours cache should be used before detail fetch")

    monkeypatch.setattr("songsim_campus.services.KakaoPlaceDetailClient", ExplodingDetailClient)

    with connection() as conn:
        repo.replace_restaurant_cache_snapshot(
            conn,
            origin_slug="central-library",
            kakao_query="한식",
            radius_meters=15 * 75,
            fetched_at="2026-03-14T10:00:00+09:00",
            rows=[
                {
                    "id": -1,
                    "slug": "kakao-gatolic-bap",
                    "name": "가톨릭백반",
                    "category": "korean",
                    "min_price": None,
                    "max_price": None,
                    "latitude": 37.48674,
                    "longitude": 126.80182,
                    "tags": ["한식"],
                    "description": "경기 부천시 원미구",
                    "source_tag": "kakao_local_cache",
                    "last_synced_at": "2026-03-14T10:00:00+09:00",
                    "kakao_place_id": "242731511",
                    "source_url": "https://place.map.kakao.com/242731511",
                }
            ],
        )
        repo.upsert_restaurant_hours_cache(
            conn,
            kakao_place_id="242731511",
            source_url="https://place.map.kakao.com/242731511",
            raw_payload=_fixture_json("kakao_place_detail.json"),
            opening_hours={
                "mon": "08:00 ~ 21:00",
                "tue": "08:00 ~ 21:00",
                "wed": "08:00 ~ 21:00",
                "thu": "08:00 ~ 21:00",
                "fri": "08:00 ~ 21:00",
                "sat": "10:00 ~ 18:00",
                "sun": "휴무",
            },
            fetched_at="2026-03-14T10:00:00+09:00",
        )

        items = find_nearby_restaurants(
            conn,
            origin="central-library",
            category="korean",
            walk_minutes=15,
            at=datetime.fromisoformat("2026-03-16T09:00:00+09:00"),
        )

    assert items[0].open_now is True
    assert calls["detail"] == 0


def test_find_nearby_restaurants_fetches_and_reuses_kakao_detail_hours(app_env):
    init_db()
    seed_demo(force=True)

    class DetailAwareKakaoClient:
        calls = 0

        def search_sync(self, query: str, *, x=None, y=None, radius: int = 1000):
            type(self).calls += 1
            return [
                KakaoPlace(
                    name="가톨릭백반",
                    category="음식점 > 한식",
                    address="경기 부천시 원미구",
                    latitude=37.48674,
                    longitude=126.80182,
                    place_id="242731511",
                    place_url="https://place.map.kakao.com/242731511",
                )
            ]

    class DetailClient:
        calls = 0

        def fetch_sync(self, place_id: str):
            type(self).calls += 1
            assert place_id == "242731511"
            return _fixture_json("kakao_place_detail.json")

    class ExplodingDetailClient:
        calls = 0

        def fetch_sync(self, place_id: str):
            type(self).calls += 1
            raise AssertionError("hours cache should be reused on the second call")

    with connection() as conn:
        first = find_nearby_restaurants(
            conn,
            origin="central-library",
            category="korean",
            walk_minutes=15,
            at=datetime.fromisoformat("2026-03-17T10:00:00+09:00"),
            kakao_client=DetailAwareKakaoClient(),
            kakao_place_detail_client=DetailClient(),
        )
        second = find_nearby_restaurants(
            conn,
            origin="central-library",
            category="korean",
            walk_minutes=15,
            at=datetime.fromisoformat("2026-03-17T10:00:00+09:00"),
            kakao_client=ExplodingKakaoClient(),
            kakao_place_detail_client=ExplodingDetailClient(),
        )

    assert DetailAwareKakaoClient.calls == 1
    assert DetailClient.calls == 1
    assert ExplodingDetailClient.calls == 0
    assert first[0].open_now is True
    assert second[0].open_now is True


def test_find_nearby_restaurants_uses_stale_kakao_hours_cache_when_detail_fetch_fails(
    app_env,
    monkeypatch,
):
    init_db()
    seed_demo(force=True)
    now = datetime.fromisoformat("2026-03-18T10:00:00+09:00")
    monkeypatch.setattr("songsim_campus.services._now", lambda: now)

    class BrokenDetailClient:
        def fetch_sync(self, place_id: str):
            raise httpx.HTTPError("detail fetch failed")

    with connection() as conn:
        repo.replace_restaurant_cache_snapshot(
            conn,
            origin_slug="central-library",
            kakao_query="한식",
            radius_meters=15 * 75,
            fetched_at="2026-03-18T09:00:00+09:00",
            rows=[
                {
                    "id": -1,
                    "slug": "kakao-gatolic-bap",
                    "name": "가톨릭백반",
                    "category": "korean",
                    "min_price": None,
                    "max_price": None,
                    "latitude": 37.48674,
                    "longitude": 126.80182,
                    "tags": ["한식"],
                    "description": "경기 부천시 원미구",
                    "source_tag": "kakao_local_cache",
                    "last_synced_at": "2026-03-18T09:00:00+09:00",
                    "kakao_place_id": "242731511",
                    "source_url": "https://place.map.kakao.com/242731511",
                }
            ],
        )
        repo.upsert_restaurant_hours_cache(
            conn,
            kakao_place_id="242731511",
            source_url="https://place.map.kakao.com/242731511",
            raw_payload=_fixture_json("kakao_place_detail.json"),
            opening_hours={"wed": "08:00 ~ 21:00"},
            fetched_at="2026-03-15T10:00:00+09:00",
        )

        items = find_nearby_restaurants(
            conn,
            origin="central-library",
            category="korean",
            walk_minutes=15,
            at=datetime.fromisoformat("2026-03-18T10:00:00+09:00"),
            kakao_place_detail_client=BrokenDetailClient(),
        )

    assert items[0].open_now is True


class FakeCampusMapSource:
    def fetch_place_list(self, *, campus: str = '1'):
        assert campus == '1'
        return 'payload'

    def parse_place_list(self, payload: str, *, fetched_at: str):
        assert payload == 'payload'
        assert fetched_at == '2026-03-13T09:00:00+09:00'
        return [
            {
                'slug': 'central-library',
                'name': '중앙도서관',
                'category': 'library',
                'aliases': ['도서관'],
                'description': '실제 캠퍼스맵 데이터',
                'latitude': 37.486853,
                'longitude': 126.799802,
                'opening_hours': {},
                'source_tag': 'cuk_campus_map',
                'last_synced_at': fetched_at,
            },
            {
                'slug': 'sophie-barat-hall',
                'name': '학생미래인재관',
                'category': 'building',
                'aliases': ['B관'],
                'description': '학생식당이 있는 건물',
                'latitude': 37.486466,
                'longitude': 126.801297,
                'opening_hours': {},
                'source_tag': 'cuk_campus_map',
                'last_synced_at': fetched_at,
            },
            {
                'slug': 'nicholls-hall',
                'name': '니콜스관',
                'category': 'building',
                'aliases': ['N관'],
                'description': '강의동',
                'latitude': 37.48587,
                'longitude': 126.802323,
                'opening_hours': {},
                'source_tag': 'cuk_campus_map',
                'last_synced_at': fetched_at,
            },
            {
                'slug': 'kim-sou-hwan-hall',
                'name': '김수환관',
                'category': 'dormitory',
                'aliases': [],
                'description': '강의실과 연구실, 기숙사가 함께 있는 건물',
                'latitude': 37.4855467,
                'longitude': 126.803851,
                'opening_hours': {},
                'source_tag': 'cuk_campus_map',
                'last_synced_at': fetched_at,
            },
        ]


class FakeCourseSource:
    def fetch(
        self,
        *,
        year: int,
        semester: int,
        department: str = 'ALL',
        completion_type: str = 'ALL',
        query: str = '',
        offset: int = 0,
    ):
        assert (year, semester, department, completion_type, query, offset) == (
            2026,
            1,
            'ALL',
            'ALL',
            '',
            0,
        )
        return '<html></html>'

    def parse(self, html: str, *, fetched_at: str):
        assert html == '<html></html>'
        assert fetched_at == '2026-03-13T09:00:00+09:00'
        return [
            {
                'year': 2026,
                'semester': 1,
                'code': '03149',
                'title': '자료구조',
                'professor': '박정흠',
                'department': '컴퓨터정보공학부',
                'section': '01',
                'day_of_week': '화',
                'period_start': 2,
                'period_end': 3,
                'room': 'BA203',
                'raw_schedule': '화2~3(BA203)',
                'source_tag': 'cuk_subject_search',
                'last_synced_at': fetched_at,
            }
        ]


class FakeNoticeSource:
    def fetch_list(self, *, offset: int = 0, limit: int = 10):
        assert offset == 0
        assert limit == 10
        return '<list></list>'

    def parse_list(self, html: str):
        assert html == '<list></list>'
        return [
            {
                'article_no': '1001',
                'title': '2026학년도 1학기 가족장학금 신청 안내',
                'board_category': '장학',
                'published_at': '2026-03-12',
                'source_url': 'https://example.edu/notice/1001',
            }
        ]

    def fetch_detail(self, article_no: str, *, offset: int = 0, limit: int = 10):
        assert article_no == '1001'
        return '<detail></detail>'

    def parse_detail(self, html: str, *, default_title: str = '', default_category: str = ''):
        assert html == '<detail></detail>'
        assert default_title == '2026학년도 1학기 가족장학금 신청 안내'
        assert default_category == '장학'
        return {
            'title': default_title,
            'published_at': '2026-03-12',
            'summary': '가족장학금 신청 안내',
            'labels': ['장학'],
            'category': 'scholarship',
        }


class FakePaginatedCourseSource:
    def __init__(self):
        self.fetch_offsets: list[int] = []

    def fetch(
        self,
        *,
        year: int,
        semester: int,
        department: str = 'ALL',
        completion_type: str = 'ALL',
        query: str = '',
        offset: int = 0,
    ):
        assert (year, semester, department, completion_type, query) == (2026, 1, 'ALL', 'ALL', '')
        self.fetch_offsets.append(offset)
        return f'<html offset="{offset}"></html>'

    def parse(self, html: str, *, fetched_at: str):
        assert fetched_at == '2026-03-13T09:00:00+09:00'
        if 'offset="0"' in html:
            return [
                {
                    'year': 2026,
                    'semester': 1,
                    'code': f'CSE{index:03d}',
                    'title': f'테스트과목{index:03d}',
                    'professor': '테스트교수',
                    'department': '컴퓨터정보공학부',
                    'section': '01',
                    'day_of_week': '월',
                    'period_start': 1,
                    'period_end': 1,
                    'room': f'N{100 + index}',
                    'raw_schedule': f'월1(N{100 + index})',
                    'source_tag': 'cuk_subject_search',
                    'last_synced_at': fetched_at,
                }
                for index in range(50)
            ]
        if 'offset="50"' in html:
            return [
                {
                    'year': 2026,
                    'semester': 1,
                    'code': 'CSE049',
                    'title': '테스트과목049',
                    'professor': '테스트교수',
                    'department': '컴퓨터정보공학부',
                    'section': '01',
                    'day_of_week': '월',
                    'period_start': 1,
                    'period_end': 1,
                    'room': 'N149',
                    'raw_schedule': '월1(N149)',
                    'source_tag': 'cuk_subject_search',
                    'last_synced_at': fetched_at,
                },
                {
                    'year': 2026,
                    'semester': 1,
                    'code': 'CSE999',
                    'title': '추가테스트과목',
                    'professor': '테스트교수',
                    'department': '컴퓨터정보공학부',
                    'section': '02',
                    'day_of_week': '화',
                    'period_start': 2,
                    'period_end': 3,
                    'room': 'N999',
                    'raw_schedule': '화2~3(N999)',
                    'source_tag': 'cuk_subject_search',
                    'last_synced_at': fetched_at,
                },
            ]
        raise AssertionError(f'unexpected html: {html}')


class FakeCourseCoverageSource:
    def fetch(
        self,
        *,
        year: int,
        semester: int,
        department: str = 'ALL',
        completion_type: str = 'ALL',
        query: str = '',
        offset: int = 0,
    ):
        assert (year, semester, department, completion_type, query) == (2026, 1, 'ALL', 'ALL', '')
        return f'<html offset="{offset}"></html>'

    def parse(self, html: str, *, fetched_at: str):
        assert fetched_at == '2026-03-13T09:00:00+09:00'
        if 'offset="0"' in html:
            return [
                {
                    'year': 2026,
                    'semester': 1,
                    'code': '05497',
                    'title': '데이터베이스활용',
                    'professor': '권보람',
                    'department': '경영학과',
                    'section': '01',
                    'day_of_week': '화',
                    'period_start': 1,
                    'period_end': 2,
                    'room': 'M307',
                    'raw_schedule': '화1~2(M307)',
                    'source_tag': 'cuk_subject_search',
                    'last_synced_at': fetched_at,
                },
                {
                    'year': 2026,
                    'semester': 1,
                    'code': 'CSE420',
                    'title': '임베디드시스템',
                    'professor': '박성심',
                    'department': '컴퓨터정보공학부',
                    'section': '01',
                    'day_of_week': '목',
                    'period_start': 5,
                    'period_end': 6,
                    'room': 'N201',
                    'raw_schedule': '목5~6(N201)',
                    'source_tag': 'cuk_subject_search',
                    'last_synced_at': fetched_at,
                },
            ]
        return []


class FakeNoticeSourceWithDetailFailure:
    def fetch_list(self, *, offset: int = 0, limit: int = 10):
        assert offset == 0
        assert limit == 10
        return '<list></list>'

    def parse_list(self, html: str):
        assert html == '<list></list>'
        return [
            {
                'article_no': '2001',
                'title': '2026학년도 1학기 Major Discovery Week 특강 신청 마감 안내',
                'board_category': '학사',
                'published_at': '2026-03-14',
                'source_url': 'https://example.edu/notice/2001',
            }
        ]

    def fetch_detail(self, article_no: str, *, offset: int = 0, limit: int = 10):
        raise httpx.ReadError('detail unavailable')


class FakeNoticeSourceWithGenericDetailLabel:
    def fetch_list(self, *, offset: int = 0, limit: int = 10):
        assert offset == 0
        assert limit == 10
        return '<list></list>'

    def parse_list(self, html: str):
        assert html == '<list></list>'
        return [
            {
                'article_no': '3001',
                'title': '2026학년도 1학기 Major Discovery Week 특강 신청 마감 안내',
                'board_category': '학사',
                'published_at': '2026-03-14',
                'source_url': 'https://example.edu/notice/3001',
            }
        ]

    def fetch_detail(self, article_no: str, *, offset: int = 0, limit: int = 10):
        assert article_no == '3001'
        return '<detail></detail>'

    def parse_detail(self, html: str, *, default_title: str = '', default_category: str = ''):
        assert html == '<detail></detail>'
        assert default_title == '2026학년도 1학기 Major Discovery Week 특강 신청 마감 안내'
        assert default_category == '학사'
        return {
            'title': default_title,
            'published_at': '2026-03-14',
            'summary': '학사 일정과 특강 신청 마감 일정을 안내합니다.',
            'labels': ['공지'],
            'category': 'urgent',
        }


def test_refresh_places_from_campus_map_replaces_place_rows(app_env):
    init_db()

    with connection() as conn:
        refresh_places_from_campus_map(
            conn,
            source=FakeCampusMapSource(),
            fetched_at='2026-03-13T09:00:00+09:00',
        )
        places = search_places(conn, query='중앙')

    assert len(places) == 1
    assert places[0].source_tag == 'cuk_campus_map'


def test_refresh_places_from_campus_map_applies_place_alias_overrides(app_env):
    init_db()
    seed_demo(force=True)

    with connection() as conn:
        refresh_places_from_campus_map(
            conn,
            source=FakeCampusMapSource(),
            fetched_at='2026-03-13T09:00:00+09:00',
        )
        place_alias_hits = search_places(conn, query='중도')
        restaurant_items = find_nearby_restaurants(conn, origin='학생식당', limit=1)
        classroom_payload = list_estimated_empty_classrooms(
            conn,
            building='니콜스',
            at=datetime.fromisoformat("2026-03-16T10:15:00+09:00"),
        )
        kim_place = get_place(conn, 'kim-sou-hwan-hall')

    assert any(item.slug == 'central-library' for item in place_alias_hits)
    assert restaurant_items
    assert restaurant_items[0].origin == 'sophie-barat-hall'
    assert classroom_payload.building.slug == 'nicholls-hall'
    assert kim_place.category == 'building'


def test_refresh_courses_from_subject_search_replaces_course_rows(app_env):
    init_db()

    with connection() as conn:
        refresh_courses_from_subject_search(
            conn,
            source=FakeCourseSource(),
            year=2026,
            semester=1,
            fetched_at='2026-03-13T09:00:00+09:00',
        )
        courses = search_courses(conn, query='자료')

    assert len(courses) == 1
    assert courses[0].source_tag == 'cuk_subject_search'


def test_refresh_courses_from_subject_search_ingests_paginated_snapshot_and_dedupes(app_env):
    init_db()
    source = FakePaginatedCourseSource()

    with connection() as conn:
        refresh_courses_from_subject_search(
            conn,
            source=source,
            year=2026,
            semester=1,
            fetched_at='2026-03-13T09:00:00+09:00',
        )
        stored = repo.search_courses(conn, year=2026, semester=1, limit=200)

    assert source.fetch_offsets == [0, 50]
    assert len(stored) == 51
    assert any(item['code'] == 'CSE999' for item in stored)


def test_investigate_course_query_coverage_reports_covered_and_source_gaps(app_env):
    init_db()
    with connection() as conn:
        repo.replace_courses(
            conn,
            [
                {
                    'year': 2026,
                    'semester': 1,
                    'code': '05497',
                    'title': '데이터베이스활용',
                    'professor': '권보람',
                    'department': '경영학과',
                    'section': '01',
                    'day_of_week': '화',
                    'period_start': 1,
                    'period_end': 2,
                    'room': 'M307',
                    'raw_schedule': '화1~2(M307)',
                    'source_tag': 'cuk_subject_search',
                    'last_synced_at': '2026-03-13T09:00:00+09:00',
                },
                {
                    'year': 2026,
                    'semester': 1,
                    'code': 'CSE420',
                    'title': '임베디드시스템',
                    'professor': '박성심',
                    'department': '컴퓨터정보공학부',
                    'section': '01',
                    'day_of_week': '목',
                    'period_start': 5,
                    'period_end': 6,
                    'room': 'N201',
                    'raw_schedule': '목5~6(N201)',
                    'source_tag': 'cuk_subject_search',
                    'last_synced_at': '2026-03-13T09:00:00+09:00',
                },
            ],
        )
        reports = investigate_course_query_coverage(
            conn,
            queries=['데이터베이스', 'CSE301', 'CSE 420'],
            source=FakeCourseCoverageSource(),
            year=2026,
            semester=1,
            fetched_at='2026-03-13T09:00:00+09:00',
        )

    assert reports == [
        {
            'query': '데이터베이스',
            'year': 2026,
            'semester': 1,
            'status': 'covered',
            'source_match_count': 1,
            'db_match_count': 1,
            'search_match_count': 1,
            'source_matches': [
                {
                    'code': '05497',
                    'title': '데이터베이스활용',
                    'professor': '권보람',
                    'department': '경영학과',
                    'section': '01',
                }
            ],
            'db_matches': [
                {
                    'code': '05497',
                    'title': '데이터베이스활용',
                    'professor': '권보람',
                    'department': '경영학과',
                    'section': '01',
                }
            ],
            'search_matches': [
                {
                    'code': '05497',
                    'title': '데이터베이스활용',
                    'professor': '권보람',
                    'department': '경영학과',
                    'section': '01',
                }
            ],
        },
        {
            'query': 'CSE301',
            'year': 2026,
            'semester': 1,
            'status': 'source_gap',
            'source_match_count': 0,
            'db_match_count': 0,
            'search_match_count': 0,
            'source_matches': [],
            'db_matches': [],
            'search_matches': [],
        },
        {
            'query': 'CSE 420',
            'year': 2026,
            'semester': 1,
            'status': 'covered',
            'source_match_count': 1,
            'db_match_count': 1,
            'search_match_count': 1,
            'source_matches': [
                {
                    'code': 'CSE420',
                    'title': '임베디드시스템',
                    'professor': '박성심',
                    'department': '컴퓨터정보공학부',
                    'section': '01',
                }
            ],
            'db_matches': [
                {
                    'code': 'CSE420',
                    'title': '임베디드시스템',
                    'professor': '박성심',
                    'department': '컴퓨터정보공학부',
                    'section': '01',
                }
            ],
            'search_matches': [
                {
                    'code': 'CSE420',
                    'title': '임베디드시스템',
                    'professor': '박성심',
                    'department': '컴퓨터정보공학부',
                    'section': '01',
                }
            ],
        },
    ]


def test_investigate_course_query_coverage_reports_db_gap_when_source_rows_are_not_synced(app_env):
    init_db()
    with connection() as conn:
        reports = investigate_course_query_coverage(
            conn,
            queries=['데이터베이스'],
            source=FakeCourseCoverageSource(),
            year=2026,
            semester=1,
            fetched_at='2026-03-13T09:00:00+09:00',
        )

    assert reports[0]['status'] == 'db_gap'
    assert reports[0]['source_match_count'] == 1
    assert reports[0]['db_match_count'] == 0
    assert reports[0]['search_match_count'] == 0


def test_investigate_course_query_coverage_reports_search_gap(
    app_env,
    monkeypatch,
):
    init_db()
    with connection() as conn:
        repo.replace_courses(
            conn,
            [
                {
                    'year': 2026,
                    'semester': 1,
                    'code': 'CSE420',
                    'title': '임베디드시스템',
                    'professor': '박성심',
                    'department': '컴퓨터정보공학부',
                    'section': '01',
                    'day_of_week': '목',
                    'period_start': 5,
                    'period_end': 6,
                    'room': 'N201',
                    'raw_schedule': '목5~6(N201)',
                    'source_tag': 'cuk_subject_search',
                    'last_synced_at': '2026-03-13T09:00:00+09:00',
                }
            ],
        )
        monkeypatch.setattr('songsim_campus.services.search_courses', lambda *args, **kwargs: [])
        reports = investigate_course_query_coverage(
            conn,
            queries=['CSE 420'],
            source=FakeCourseCoverageSource(),
            year=2026,
            semester=1,
            fetched_at='2026-03-13T09:00:00+09:00',
        )

    assert reports[0]['status'] == 'search_gap'
    assert reports[0]['source_match_count'] == 1
    assert reports[0]['db_match_count'] == 1
    assert reports[0]['search_match_count'] == 0


def test_refresh_notices_from_notice_board_replaces_notice_rows(app_env):
    init_db()

    with connection() as conn:
        refresh_notices_from_notice_board(
            conn,
            source=FakeNoticeSource(),
            pages=1,
            fetched_at='2026-03-13T09:00:00+09:00',
        )
        notices = list_latest_notices(conn)

    assert len(notices) == 1
    assert notices[0].category == 'scholarship'
    assert notices[0].source_tag == 'cuk_campus_notices'


def test_refresh_notices_from_notice_board_fallback_classifies_board_category(app_env):
    init_db()

    with connection() as conn:
        refresh_notices_from_notice_board(
            conn,
            source=FakeNoticeSourceWithDetailFailure(),
            pages=1,
            fetched_at='2026-03-13T09:00:00+09:00',
        )
        notices = list_latest_notices(conn)

    assert len(notices) == 1
    assert notices[0].category == 'academic'


def test_refresh_notices_from_notice_board_preserves_list_board_category_over_generic_detail_label(
    app_env,
):
    init_db()

    with connection() as conn:
        refresh_notices_from_notice_board(
            conn,
            source=FakeNoticeSourceWithGenericDetailLabel(),
            pages=1,
            fetched_at='2026-03-13T09:00:00+09:00',
        )
        notices = list_latest_notices(conn)

    assert len(notices) == 1
    assert notices[0].category == 'academic'
    assert notices[0].labels == ['학사']


class FakeLibraryHoursSource:
    def fetch(self):
        return '<library></library>'

    def parse(self, html: str, *, fetched_at: str):
        assert html == '<library></library>'
        assert fetched_at == '2026-03-13T09:00:00+09:00'
        return [
            {
                'place_name': '중앙도서관',
                'opening_hours': {
                    '대출반납실': '학기중 평일 09:00-21:00 / 토요일 09:00-13:00',
                },
                'source_tag': 'cuk_library_hours',
                'last_synced_at': fetched_at,
            }
        ]


class FakeFacilitiesSource:
    def fetch(self):
        return '<facilities></facilities>'

    def parse(self, html: str, *, fetched_at: str):
        assert html == '<facilities></facilities>'
        assert fetched_at == '2026-03-13T09:00:00+09:00'
        return [
            {
                'facility_name': '카페드림',
                'location': '중앙도서관 2층',
                'hours_text': '평일 08:00~19:00 토 10:00~16:00 (일/공휴일휴무)',
                'category': '카페',
                'source_tag': 'cuk_facilities',
                'last_synced_at': fetched_at,
            },
            {
                'facility_name': '매머드커피',
                'location': 'K관 1층',
                'hours_text': '평일 08:00~20:00 주말,공휴일 09:00~17:00',
                'category': '카페',
                'source_tag': 'cuk_facilities',
                'last_synced_at': fetched_at,
            },
            {
                'facility_name': '없는시설',
                'location': '없는관 1층',
                'hours_text': '상시 09:00~18:00',
                'category': '편의점',
                'source_tag': 'cuk_facilities',
                'last_synced_at': fetched_at,
            },
        ]


class FakeTransportSource:
    def fetch(self):
        return '<transport></transport>'

    def parse(self, html: str, *, fetched_at: str):
        assert html == '<transport></transport>'
        assert fetched_at == '2026-03-13T09:00:00+09:00'
        return [
            {
                'mode': 'subway',
                'title': '1호선',
                'summary': '역곡역 2번 출구 또는 소사역 3번 출구에서 도보 10분',
                'steps': ['인천역 ↔ 역곡역 : 35분 소요'],
                'source_url': 'https://www.catholic.ac.kr/ko/about/location_songsim.do',
                'source_tag': 'cuk_transport',
                'last_synced_at': fetched_at,
            }
        ]


def test_refresh_library_hours_merges_opening_hours_into_existing_place(app_env):
    init_db()
    seed_demo(force=True)

    with connection() as conn:
        refresh_library_hours_from_library_page(
            conn,
            source=FakeLibraryHoursSource(),
            fetched_at='2026-03-13T09:00:00+09:00',
        )
        place = get_place(conn, 'central-library')

    assert place.source_tag == 'demo'
    assert place.opening_hours['대출반납실'] == '학기중 평일 09:00-21:00 / 토요일 09:00-13:00'


def test_refresh_facility_hours_merges_by_location_and_skips_unknown_places(app_env):
    init_db()
    seed_demo(force=True)

    with connection() as conn:
        places = refresh_facility_hours_from_facilities_page(
            conn,
            source=FakeFacilitiesSource(),
            fetched_at='2026-03-13T09:00:00+09:00',
        )
        library = get_place(conn, 'central-library')
        hall = get_place(conn, 'kim-sou-hwan-hall')

    assert sorted(item.slug for item in places) == ['central-library', 'kim-sou-hwan-hall']
    assert library.opening_hours['카페드림'] == '평일 08:00~19:00 토 10:00~16:00 (일/공휴일휴무)'
    assert hall.opening_hours['매머드커피'] == '평일 08:00~20:00 주말,공휴일 09:00~17:00'
    assert '없는시설' not in library.opening_hours


def test_refresh_transport_guides_replaces_rows(app_env):
    init_db()

    with connection() as conn:
        refresh_transport_guides_from_location_page(
            conn,
            source=FakeTransportSource(),
            fetched_at='2026-03-13T09:00:00+09:00',
        )
        guides = list_transport_guides(conn)

    assert len(guides) == 1
    assert guides[0].mode == 'subway'
    assert guides[0].title == '1호선'
    assert guides[0].source_tag == 'cuk_transport'


def test_sync_official_snapshot_runs_opening_hours_before_courses_and_transport(
    app_env,
    monkeypatch,
):
    call_order: list[str] = []

    monkeypatch.setattr(
        'songsim_campus.services.refresh_places_from_campus_map',
        lambda conn, campus=None: call_order.append('places') or [],
    )
    monkeypatch.setattr(
        'songsim_campus.services.refresh_library_hours_from_library_page',
        lambda conn: call_order.append('library') or [],
    )
    monkeypatch.setattr(
        'songsim_campus.services.refresh_facility_hours_from_facilities_page',
        lambda conn: call_order.append('facilities') or [],
    )
    monkeypatch.setattr(
        'songsim_campus.services.refresh_courses_from_subject_search',
        lambda conn, year=None, semester=None: call_order.append('courses') or [],
    )
    monkeypatch.setattr(
        'songsim_campus.services.refresh_notices_from_notice_board',
        lambda conn, pages=None: call_order.append('notices') or [],
    )
    monkeypatch.setattr(
        'songsim_campus.services.refresh_transport_guides_from_location_page',
        lambda conn: call_order.append('transport') or [],
    )

    init_db()
    with connection() as conn:
        summary = sync_official_snapshot(conn, year=2026, semester=1, notice_pages=1)

    assert call_order == ['places', 'library', 'facilities', 'courses', 'notices', 'transport']
    assert summary['transport_guides'] == 0
