from __future__ import annotations

from songsim_campus import services
from songsim_campus.db import connection
from songsim_campus.repo import replace_restaurants, update_place_opening_hours
from songsim_campus.services import (
    refresh_facility_hours_from_facilities_page,
    refresh_transport_guides_from_location_page,
)
from songsim_campus.settings import clear_settings_cache


def test_healthz(client):
    response = client.get('/healthz')
    assert response.status_code == 200
    assert response.json() == {'ok': True}


def test_readyz_reports_database_and_table_status(client):
    response = client.get("/readyz")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["database"]["ok"] is True
    assert payload["tables"]["places"]["ok"] is True
    assert payload["tables"]["courses"]["ok"] is True
    assert payload["tables"]["sync_runs"]["ok"] is True


def test_admin_sync_route_is_disabled_by_default(client):
    response = client.get("/admin/sync")

    assert response.status_code == 404


def test_admin_observability_routes_are_disabled_by_default(client):
    html_response = client.get("/admin/observability")
    json_response = client.get("/admin/observability.json")

    assert html_response.status_code == 404
    assert json_response.status_code == 404


def test_admin_sync_route_rejects_non_loopback(remote_admin_client):
    response = remote_admin_client.get("/admin/sync")

    assert response.status_code == 403


def test_admin_observability_routes_reject_non_loopback(remote_admin_client):
    html_response = remote_admin_client.get("/admin/observability")
    json_response = remote_admin_client.get("/admin/observability.json")

    assert html_response.status_code == 403
    assert json_response.status_code == 403


def test_admin_sync_dashboard_runs_snapshot_and_shows_recent_history(admin_client, monkeypatch):
    def fake_snapshot(
        conn,
        *,
        campus: str | None = None,
        year: int | None = None,
        semester: int | None = None,
        notice_pages: int | None = None,
    ):
        assert campus == "1"
        assert year == 2026
        assert semester == 1
        assert notice_pages == 2
        return {"places": 5, "courses": 10, "notices": 4, "transport_guides": 2}

    monkeypatch.setattr("songsim_campus.services.sync_official_snapshot", fake_snapshot)

    response = admin_client.post(
        "/admin/sync/run",
        data={
            "target": "snapshot",
            "campus": "1",
            "year": "2026",
            "semester": "1",
            "notice_pages": "2",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/sync"

    page = admin_client.get("/admin/sync")
    assert page.status_code == 200
    assert "Songsim Admin Sync" in page.text
    assert "snapshot" in page.text
    assert "success" in page.text
    assert "transport_guides" in page.text


def test_admin_observability_pages_render_runtime_state(admin_client, client, monkeypatch):
    services.reset_observability_state()

    def fake_snapshot(
        conn,
        *,
        campus: str | None = None,
        year: int | None = None,
        semester: int | None = None,
        notice_pages: int | None = None,
    ):
        return {"places": 5, "courses": 10, "notices": 4, "transport_guides": 2}

    def broken_transport(conn, *, fetched_at: str | None = None, source=None):
        raise RuntimeError("transport sync exploded")

    monkeypatch.setattr("songsim_campus.services.sync_official_snapshot", fake_snapshot)
    monkeypatch.setattr(
        "songsim_campus.services.refresh_transport_guides_from_location_page",
        broken_transport,
    )

    nearby = client.get("/restaurants/nearby", params={"origin": "central-library", "limit": 3})
    assert nearby.status_code == 200

    success = admin_client.post(
        "/admin/sync/run",
        data={"target": "snapshot", "campus": "1", "year": "2026", "semester": "1"},
        follow_redirects=False,
    )
    failed = admin_client.post(
        "/admin/sync/run",
        data={"target": "transport_guides"},
        follow_redirects=False,
    )

    assert success.status_code == 303
    assert failed.status_code == 303

    html_page = admin_client.get("/admin/observability")
    json_page = admin_client.get("/admin/observability.json")

    assert html_page.status_code == 200
    assert "Songsim Observability" in html_page.text
    assert json_page.status_code == 200
    payload = json_page.json()
    assert payload["health"]["ok"] is True
    assert payload["readiness"]["ok"] is True
    assert payload["cache"]["local_fallback"] >= 1
    assert payload["sync"]["last_failure_message"] == "transport sync exploded"
    assert payload["datasets"][0]["name"] == "places"
    assert payload["recent_sync_runs"][0]["status"] in {"success", "failed"}


def test_admin_sync_dashboard_passes_target_specific_form_values(admin_client, monkeypatch):
    captured: dict[str, object] = {}

    def fake_places(conn, *, campus: str = "1", fetched_at: str | None = None):
        captured["places"] = campus
        return []

    def fake_courses(
        conn,
        *,
        year: int | None = None,
        semester: int | None = None,
        fetched_at: str | None = None,
        source=None,
    ):
        captured["courses"] = (year, semester)
        return []

    def fake_notices(conn, *, pages: int = 1, fetched_at: str | None = None, source=None):
        captured["notices"] = pages
        return []

    monkeypatch.setattr("songsim_campus.services.refresh_places_from_campus_map", fake_places)
    monkeypatch.setattr("songsim_campus.services.refresh_courses_from_subject_search", fake_courses)
    monkeypatch.setattr("songsim_campus.services.refresh_notices_from_notice_board", fake_notices)

    assert admin_client.post(
        "/admin/sync/run",
        data={"target": "places", "campus": "7"},
        follow_redirects=False,
    ).status_code == 303
    assert admin_client.post(
        "/admin/sync/run",
        data={"target": "courses", "year": "2026", "semester": "1"},
        follow_redirects=False,
    ).status_code == 303
    assert admin_client.post(
        "/admin/sync/run",
        data={"target": "notices", "notice_pages": "3"},
        follow_redirects=False,
    ).status_code == 303

    assert captured["places"] == "7"
    assert captured["courses"] == (2026, 1)
    assert captured["notices"] == 3


def test_places_query_returns_library(client):
    response = client.get('/places', params={'query': '도서관'})
    assert response.status_code == 200
    names = [item['name'] for item in response.json()]
    assert '중앙도서관' in names


def test_courses_query_returns_expected_course(client):
    response = client.get('/courses', params={'query': '객체지향', 'year': 2026, 'semester': 1})
    assert response.status_code == 200
    items = response.json()
    assert items
    assert items[0]['title'] == '객체지향프로그래밍설계'


def test_nearby_restaurants_uses_origin(client):
    response = client.get(
        '/restaurants/nearby',
        params={'origin': 'central-library', 'budget_max': 10000, 'walk_minutes': 15},
    )
    assert response.status_code == 200
    items = response.json()
    assert items
    assert all(item['estimated_walk_minutes'] <= 15 for item in items)


def test_nearby_restaurants_endpoint_uses_campus_graph_for_external_routes(client):
    with connection() as conn:
        replace_restaurants(
            conn,
            [
                {
                    "slug": "gate-bap",
                    "name": "정문백반",
                    "category": "korean",
                    "min_price": 7000,
                    "max_price": 9000,
                    "latitude": 37.48590,
                    "longitude": 126.80282,
                    "tags": ["한식"],
                    "description": "테스트 식당",
                    "source_tag": "kakao_local",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                }
            ],
        )

    response = client.get(
        '/restaurants/nearby',
        params={'origin': 'central-library', 'walk_minutes': 15},
    )

    assert response.status_code == 200
    assert response.json()[0]['estimated_walk_minutes'] == 6


def test_place_detail_returns_404_for_missing_place(client):
    response = client.get('/places/does-not-exist')

    assert response.status_code == 404


def test_nearby_restaurants_returns_404_for_missing_origin(client):
    response = client.get('/restaurants/nearby', params={'origin': 'does-not-exist'})

    assert response.status_code == 404


def test_nearby_restaurants_can_filter_open_now(client):
    with connection() as conn:
        replace_restaurants(
            conn,
            [
                {
                    "slug": "cafe-dream",
                    "name": "카페드림",
                    "category": "cafe",
                    "min_price": 4000,
                    "max_price": 6500,
                    "latitude": 37.48695,
                    "longitude": 126.79995,
                    "tags": ["카페"],
                    "description": "테스트 카페",
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
                {
                    "slug": "unknown-bap",
                    "name": "알수없음식당",
                    "category": "korean",
                    "min_price": 7000,
                    "max_price": 9000,
                    "latitude": 37.4869,
                    "longitude": 126.7999,
                    "tags": ["한식"],
                    "description": "테스트 식당",
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
            ],
        )
        update_place_opening_hours(
            conn,
            "central-library",
            {"카페드림": "평일 08:00~19:00 토 10:00~16:00 (일/공휴일휴무)"},
            last_synced_at="2026-03-13T09:00:00+09:00",
        )

    response = client.get(
        "/restaurants/nearby",
        params={
            "origin": "central-library",
            "open_now": True,
            "at": "2026-03-15T11:00:00+09:00",
        },
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "알수없음식당"
    assert response.json()[0]["origin"] == "central-library"
    assert response.json()[0]["open_now"] is None


def test_nearby_restaurants_endpoint_reuses_kakao_cache(client, monkeypatch):
    monkeypatch.setenv("SONGSIM_KAKAO_REST_API_KEY", "test-key")
    clear_settings_cache()

    class ApiCacheKakaoClient:
        calls = 0

        def __init__(self, api_key: str):
            assert api_key == "test-key"

        def search_sync(self, query: str, *, x=None, y=None, radius: int = 1000):
            type(self).calls += 1
            return [
                services.KakaoPlace(
                    name="가톨릭백반",
                    category="음식점 > 한식",
                    address="경기 부천시 원미구",
                    latitude=37.48674,
                    longitude=126.80182,
                    place_id="1",
                    place_url="https://place.map.kakao.com/1",
                )
            ]

    monkeypatch.setattr('songsim_campus.services.KakaoLocalClient', ApiCacheKakaoClient)

    first = client.get(
        '/restaurants/nearby',
        params={'origin': 'central-library', 'category': 'korean', 'walk_minutes': 15},
    )
    second = client.get(
        '/restaurants/nearby',
        params={'origin': 'central-library', 'category': 'korean', 'walk_minutes': 15},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert ApiCacheKakaoClient.calls == 1
    assert [item['name'] for item in first.json()] == [item['name'] for item in second.json()]
    assert all(item['source_tag'] == 'kakao_local' for item in first.json())
    assert all(item['source_tag'] == 'kakao_local_cache' for item in second.json())


def test_nearby_restaurants_endpoint_uses_kakao_detail_hours(client, monkeypatch):
    monkeypatch.setenv("SONGSIM_KAKAO_REST_API_KEY", "test-key")
    clear_settings_cache()

    class ApiHoursKakaoClient:
        def __init__(self, api_key: str):
            assert api_key == "test-key"

        def search_sync(self, query: str, *, x=None, y=None, radius: int = 1000):
            return [
                services.KakaoPlace(
                    name="가톨릭백반",
                    category="음식점 > 한식",
                    address="경기 부천시 원미구",
                    latitude=37.48674,
                    longitude=126.80182,
                    place_id="242731511",
                    place_url="https://place.map.kakao.com/242731511",
                )
            ]

    class ApiHoursDetailClient:
        def fetch_sync(self, place_id: str):
            assert place_id == "242731511"
            return {
                "open_hours": {
                    "all": {
                        "periods": [
                            {
                                "period_title": "기본 영업시간",
                                "days": [
                                    {
                                        "day_of_the_week": "월",
                                        "on_days": {
                                            "start_end_time_desc": "08:00 ~ 21:00"
                                        },
                                    }
                                ],
                            }
                        ]
                    }
                }
            }

    monkeypatch.setattr("songsim_campus.services.KakaoLocalClient", ApiHoursKakaoClient)
    monkeypatch.setattr("songsim_campus.services.KakaoPlaceDetailClient", ApiHoursDetailClient)

    response = client.get(
        "/restaurants/nearby",
        params={
            "origin": "central-library",
            "category": "korean",
            "open_now": True,
            "at": "2026-03-16T09:00:00+09:00",
        },
    )

    assert response.status_code == 200
    assert response.json()[0]["name"] == "가톨릭백반"
    assert response.json()[0]["open_now"] is True


class ApiFacilitiesSource:
    def fetch(self):
        return '<facilities></facilities>'

    def parse(self, html: str, *, fetched_at: str):
        assert html == '<facilities></facilities>'
        return [
            {
                'facility_name': '카페드림',
                'location': '중앙도서관 2층',
                'hours_text': '평일 08:00~19:00 토 10:00~16:00 (일/공휴일휴무)',
                'category': '카페',
                'source_tag': 'cuk_facilities',
                'last_synced_at': fetched_at,
            }
        ]


class ApiTransportSource:
    def fetch(self):
        return '<transport></transport>'

    def parse(self, html: str, *, fetched_at: str):
        assert html == '<transport></transport>'
        return [
            {
                'mode': 'bus',
                'title': '마을버스',
                'summary': '51번, 51-1번, 51-2번 버스',
                'steps': ['[가톨릭대학교, 역곡도서관] 정류장 하차'],
                'source_url': 'https://www.catholic.ac.kr/ko/about/location_songsim.do',
                'source_tag': 'cuk_transport',
                'last_synced_at': fetched_at,
            }
        ]


def test_place_detail_returns_merged_opening_hours(client):
    with connection() as conn:
        refresh_facility_hours_from_facilities_page(conn, source=ApiFacilitiesSource())

    response = client.get('/places/central-library')
    payload = response.json()

    assert response.status_code == 200
    assert (
        payload['opening_hours']['카페드림']
        == '평일 08:00~19:00 토 10:00~16:00 (일/공휴일휴무)'
    )


def test_transport_endpoint_returns_guides(client):
    with connection() as conn:
        refresh_transport_guides_from_location_page(conn, source=ApiTransportSource())

    response = client.get('/transport', params={'mode': 'bus'})
    items = response.json()

    assert response.status_code == 200
    assert items == [
        {
            'id': 1,
            'mode': 'bus',
            'title': '마을버스',
            'summary': '51번, 51-1번, 51-2번 버스',
            'steps': ['[가톨릭대학교, 역곡도서관] 정류장 하차'],
            'source_url': 'https://www.catholic.ac.kr/ko/about/location_songsim.do',
            'source_tag': 'cuk_transport',
            'last_synced_at': items[0]['last_synced_at'],
        }
    ]
