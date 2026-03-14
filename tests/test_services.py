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
    _parse_campus_walk_graph,
    find_nearby_restaurants,
    get_class_periods,
    get_place,
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
    assert len(filtered) == 1
    assert filtered[0].source_tag == 'kakao_local_cache'


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


def test_find_nearby_restaurants_open_now_filters_closed_but_keeps_unknown(app_env):
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
    assert [item.name for item in filtered] == ["알수없음식당"]


def test_find_nearby_restaurants_prefers_official_facility_hours_before_kakao_detail(
    app_env,
    monkeypatch,
):
    init_db()
    seed_demo(force=True)
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
            }
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
    ):
        assert (year, semester, department, completion_type, query) == (2026, 1, 'ALL', 'ALL', '')
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
        hall = get_place(conn, 'kim-soo-hwan-hall')

    assert sorted(item.slug for item in places) == ['central-library', 'kim-soo-hwan-hall']
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
