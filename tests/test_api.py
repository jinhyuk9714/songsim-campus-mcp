from __future__ import annotations

from fastapi.testclient import TestClient

from songsim_campus import services
from songsim_campus.api import create_app
from songsim_campus.db import connection
from songsim_campus.repo import (
    replace_courses,
    replace_notices,
    replace_restaurants,
    update_place_opening_hours,
)
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


def test_public_readonly_mode_exposes_only_public_routes(app_env, monkeypatch):
    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    monkeypatch.setenv("SONGSIM_ADMIN_ENABLED", "true")
    monkeypatch.setenv("SONGSIM_PUBLIC_HTTP_URL", "https://songsim-api.onrender.com")
    monkeypatch.setenv("SONGSIM_PUBLIC_MCP_URL", "https://songsim-mcp.onrender.com/mcp")
    monkeypatch.setenv("SONGSIM_MCP_OAUTH_ENABLED", "true")
    monkeypatch.setenv("SONGSIM_MCP_OAUTH_ISSUER", "https://songsim.us.auth0.com/")
    monkeypatch.setenv("SONGSIM_MCP_OAUTH_AUDIENCE", "https://songsim-mcp.onrender.com/mcp")
    clear_settings_cache()

    app = create_app()
    with TestClient(app) as public_client:
        landing = public_client.get("/")
        docs = public_client.get("/docs")
        openapi = public_client.get("/openapi.json")
        places = public_client.get("/places", params={"query": "도서관"})
        create_profile = public_client.post("/profiles", json={"display_name": "성심학생"})
        admin_sync = public_client.get("/admin/sync")

    clear_settings_cache()

    assert landing.status_code == 200
    assert "Songsim Campus MCP" in landing.text
    assert "https://songsim-api.onrender.com" in landing.text
    assert "https://songsim-mcp.onrender.com/mcp" in landing.text
    assert "Google login" in landing.text
    assert docs.status_code == 200
    assert places.status_code == 200
    assert create_profile.status_code == 404
    assert admin_sync.status_code == 404
    assert "/profiles" not in openapi.text
    assert "/admin/sync" not in openapi.text


def test_public_readonly_mode_exposes_gpt_actions_openapi(app_env, monkeypatch):
    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    monkeypatch.setenv("SONGSIM_PUBLIC_HTTP_URL", "https://songsim-api.onrender.com")
    clear_settings_cache()

    app = create_app()
    with TestClient(app) as public_client:
        response = public_client.get("/gpt-actions-openapi.json")

    clear_settings_cache()

    assert response.status_code == 200
    payload = response.json()
    assert payload["info"]["title"] == "Songsim Campus GPT Actions"
    assert payload["servers"] == [{"url": "https://songsim-api.onrender.com"}]
    assert set(payload["paths"]) == {
        "/places",
        "/courses",
        "/notices",
        "/restaurants/nearby",
        "/transport",
    }
    assert payload["paths"]["/places"]["get"]["operationId"] == "searchPlaces"
    assert payload["paths"]["/courses"]["get"]["operationId"] == "searchCourses"
    assert payload["paths"]["/notices"]["get"]["operationId"] == "listLatestNotices"
    assert (
        payload["paths"]["/restaurants/nearby"]["get"]["operationId"]
        == "findNearbyRestaurants"
    )
    assert payload["paths"]["/transport"]["get"]["operationId"] == "listTransportGuides"


def test_public_readonly_mode_exposes_gpt_actions_openapi_v2(app_env, monkeypatch):
    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    monkeypatch.setenv("SONGSIM_PUBLIC_HTTP_URL", "https://songsim-api.onrender.com")
    clear_settings_cache()

    app = create_app()
    with TestClient(app) as public_client:
        response = public_client.get("/gpt-actions-openapi-v2.json")

    clear_settings_cache()

    assert response.status_code == 200
    payload = response.json()
    assert payload["info"]["title"] == "Songsim Campus GPT Actions v2"
    assert payload["servers"] == [{"url": "https://songsim-api.onrender.com"}]
    assert set(payload["paths"]) == {
        "/gpt/places",
        "/gpt/notices",
        "/gpt/restaurants/nearby",
        "/gpt/classrooms/empty",
    }
    assert payload["paths"]["/gpt/places"]["get"]["operationId"] == "searchPlacesForGpt"
    assert payload["paths"]["/gpt/notices"]["get"]["operationId"] == "listLatestNoticesForGpt"
    assert (
        payload["paths"]["/gpt/restaurants/nearby"]["get"]["operationId"]
        == "findNearbyRestaurantsForGpt"
    )
    assert (
        payload["paths"]["/gpt/classrooms/empty"]["get"]["operationId"]
        == "listEstimatedEmptyClassroomsForGpt"
    )


def test_gpt_places_endpoint_returns_compact_summary_payload(client):
    response = client.get("/gpt/places", params={"query": "도서관", "limit": 1})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0] == {
        "name": "중앙도서관",
        "canonical_name": "중앙도서관",
        "aliases": ["도서관", "중도"],
        "category": "library",
        "short_location": "자료 열람과 시험기간 공부에 쓰는 중심 공간",
        "coordinates": {"latitude": 37.48643, "longitude": 126.80164},
        "highlights": [
            "별칭: 도서관, 중도",
            "자료 열람과 시험기간 공부에 쓰는 중심 공간",
            "운영: mon-fri: 08:30-22:00 / sat: 09:00-17:00",
        ],
    }


def test_gpt_notices_endpoint_returns_normalized_category_and_summary_preview(client):
    long_summary = (
        "중앙도서관 이용 학생을 위한 장학 연계 프로그램 안내입니다. "
        "자세한 일정과 신청 자격, 제출 서류를 확인해 주세요. "
        "설명이 길어져도 GPT 응답에서는 짧은 미리보기만 내려가야 합니다. "
        "추가 문의는 도서관 장학 담당 부서로 연락해 주세요."
    )
    with connection() as conn:
        replace_notices(
            conn,
            [
                {
                    "title": "중앙도서관 장학 안내",
                    "category": "place",
                    "published_at": "2026-03-08",
                    "summary": long_summary,
                    "labels": ["도서관", "장학"],
                    "source_url": "https://example.edu/notices/central-library-aid",
                    "source_tag": "demo",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                }
            ],
        )

    response = client.get("/gpt/notices", params={"limit": 1})

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["title"] == "중앙도서관 장학 안내"
    assert payload[0]["category_display"] == "general"
    assert payload[0]["published_at"] == "2026-03-08"
    assert payload[0]["source_url"] == "https://example.edu/notices/central-library-aid"
    assert payload[0]["summary"].endswith("...")
    assert len(payload[0]["summary"]) <= 160
    assert payload[0]["summary"] != long_summary


def test_notice_endpoints_treat_employment_and_career_as_same_filter(client):
    with connection() as conn:
        replace_notices(
            conn,
            [
                {
                    "title": "진로취업상담 안내",
                    "category": "career",
                    "published_at": "2026-03-12",
                    "summary": "취업 상담 일정",
                    "labels": ["취업"],
                    "source_url": "https://example.edu/notices/career",
                    "source_tag": "demo",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
                {
                    "title": "채용 설명회 안내",
                    "category": "employment",
                    "published_at": "2026-03-13",
                    "summary": "채용 설명회 일정",
                    "labels": ["취업"],
                    "source_url": "https://example.edu/notices/employment",
                    "source_tag": "demo",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
            ],
        )

    api_response = client.get("/notices", params={"category": "employment", "limit": 10})
    gpt_response = client.get("/gpt/notices", params={"category": "career", "limit": 10})

    assert api_response.status_code == 200
    assert [item["title"] for item in api_response.json()] == [
        "채용 설명회 안내",
        "진로취업상담 안내",
    ]
    assert gpt_response.status_code == 200
    assert [item["title"] for item in gpt_response.json()] == [
        "채용 설명회 안내",
        "진로취업상담 안내",
    ]
    assert all(item["category_display"] == "employment" for item in gpt_response.json())


def test_notice_endpoints_normalize_place_category_to_general(client):
    with connection() as conn:
        replace_notices(
            conn,
            [
                {
                    "title": "중앙도서관 자리 안내",
                    "category": "place",
                    "published_at": "2026-03-12",
                    "summary": "도서관 좌석 안내",
                    "labels": ["도서관"],
                    "source_url": "https://example.edu/notices/place",
                    "source_tag": "demo",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                }
            ],
        )

    api_response = client.get("/notices", params={"limit": 1})
    gpt_response = client.get("/gpt/notices", params={"limit": 1})

    assert api_response.status_code == 200
    assert api_response.json()[0]["category"] == "general"
    assert gpt_response.status_code == 200
    assert gpt_response.json()[0]["category_display"] == "general"


def test_gpt_nearby_restaurants_endpoint_returns_compact_summary_payload(client):
    response = client.get(
        "/gpt/restaurants/nearby",
        params={"origin": "central-library", "category": "western", "limit": 1},
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0] == {
        "name": "도서관파스타",
        "category_display": "양식",
        "distance_meters": 31,
        "estimated_walk_minutes": 1,
        "price_hint": "11,000~15,000원",
        "open_now": None,
        "location_hint": "도서관 근처 데모 양식집",
    }


def test_classrooms_empty_endpoint_returns_estimated_empty_rooms_for_building_alias(client):
    with connection() as conn:
        replace_courses(
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

    response = client.get(
        "/classrooms/empty",
        params={"building": "N관", "at": "2026-03-16T10:15:00+09:00", "limit": 5},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["building"]["slug"] == "nichols-hall"
    assert payload["building"]["name"] == "니콜스관"
    assert payload["year"] == 2026
    assert payload["semester"] == 1
    assert payload["availability_mode"] == "estimated"
    assert payload["observed_at"] is None
    assert payload["estimate_note"].startswith("공식 시간표 기준 예상 공실입니다.")
    assert [item["room"] for item in payload["items"]] == ["N301", "N201"]
    assert payload["items"][0]["available_now"] is True
    assert payload["items"][0]["availability_mode"] == "estimated"
    assert payload["items"][0]["source_observed_at"] is None
    assert payload["items"][0]["next_occupied_at"] is None
    assert payload["items"][1]["next_occupied_at"] == "2026-03-16T13:00:00+09:00"
    assert "데이터베이스" in (payload["items"][1]["next_course_summary"] or "")


def test_classrooms_empty_endpoint_prefers_official_realtime_when_source_is_available(
    client,
    monkeypatch,
):
    with connection() as conn:
        replace_courses(
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
        services,
        "_get_official_classroom_availability_source",
        lambda: RealtimeSource(),
    )

    response = client.get(
        "/classrooms/empty",
        params={"building": "니콜스관", "at": "2026-03-16T10:15:00+09:00"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["availability_mode"] == "realtime"
    assert payload["observed_at"] == "2026-03-16T10:10:00+09:00"
    assert "공식 실시간 공실" in payload["estimate_note"]
    assert [item["room"] for item in payload["items"]] == ["N101"]
    assert payload["items"][0]["availability_mode"] == "realtime"
    assert payload["items"][0]["source_observed_at"] == "2026-03-16T10:10:00+09:00"


def test_classrooms_empty_endpoint_rejects_non_classroom_place(client):
    response = client.get(
        "/classrooms/empty",
        params={"building": "정문", "at": "2026-03-16T10:15:00+09:00"},
    )

    assert response.status_code == 400
    assert "강의실 기반 건물" in response.json()["detail"]


def test_classrooms_empty_endpoint_returns_404_for_missing_building(client):
    response = client.get(
        "/classrooms/empty",
        params={"building": "없는건물", "at": "2026-03-16T10:15:00+09:00"},
    )

    assert response.status_code == 404


def test_classrooms_empty_endpoint_accepts_kim_sou_hwan_hall_as_building(client):
    response = client.get(
        "/classrooms/empty",
        params={"building": "김수환관", "at": "2026-03-16T10:15:00+09:00"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["building"]["slug"] == "kim-sou-hwan-hall"
    assert payload["availability_mode"] == "estimated"
    assert payload["items"]
    assert all(item["room"].startswith("K") for item in payload["items"])


def test_gpt_empty_classrooms_endpoint_returns_estimate_payload(client):
    with connection() as conn:
        replace_courses(
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

    response = client.get(
        "/gpt/classrooms/empty",
        params={"building": "니콜스", "at": "2026-03-16T10:15:00+09:00"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["building"]["slug"] == "nichols-hall"
    assert payload["availability_mode"] == "estimated"
    assert payload["items"][0]["room"] == "N201"
    assert payload["items"][0]["available_now"] is True
    assert payload["items"][0]["availability_mode"] == "estimated"
    assert payload["items"][0]["next_occupied_at"] == "2026-03-16T13:00:00+09:00"


def test_public_readonly_mode_exposes_privacy_page(app_env, monkeypatch):
    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    clear_settings_cache()

    app = create_app()
    with TestClient(app) as public_client:
        response = public_client.get("/privacy")

    clear_settings_cache()

    assert response.status_code == 200
    assert "Songsim Campus Privacy Policy" in response.text
    assert "ChatGPT Actions" in response.text
    assert "Kakao" in response.text


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
    assert "Automation Status" in page.text
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
    assert payload["automation"]["enabled"] is False
    assert payload["automation"]["leader"] is False
    assert {job["name"] for job in payload["automation"]["jobs"]} == {"snapshot", "cache_cleanup"}
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


def test_places_endpoint_prioritizes_exact_short_match_over_partial_noise(client):
    with connection() as conn:
        from songsim_campus.repo import replace_places

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

    response = client.get("/places", params={"query": "정문", "limit": 10})

    assert response.status_code == 200
    assert [item["slug"] for item in response.json()] == ["main-gate", "startup-incubator"]


def test_places_endpoint_normalizes_spacing_variants(client):
    response = client.get("/places", params={"query": "중앙 도서관", "limit": 5})

    assert response.status_code == 200
    assert response.json()
    assert response.json()[0]["slug"] == "central-library"


def test_courses_endpoint_normalizes_spacing_variants(client):
    response = client.get("/courses", params={"query": "객체 지향", "year": 2026, "semester": 1})

    assert response.status_code == 200
    assert response.json()
    assert response.json()[0]["title"] == "객체지향프로그래밍설계"


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


def test_nearby_restaurants_endpoint_budget_max_requires_price_evidence(client):
    with connection() as conn:
        replace_restaurants(
            conn,
            [
                {
                    "slug": "budget-kimbap",
                    "name": "버짓김밥",
                    "category": "korean",
                    "min_price": 7000,
                    "max_price": 9000,
                    "latitude": 37.48653,
                    "longitude": 126.80174,
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
                    "latitude": 37.48663,
                    "longitude": 126.80184,
                    "tags": ["카페"],
                    "description": "가격 정보가 없는 후보",
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
            ],
        )

    response = client.get(
        "/restaurants/nearby",
        params={"origin": "central-library", "budget_max": 10000, "walk_minutes": 15},
    )

    assert response.status_code == 200
    assert [item["slug"] for item in response.json()] == ["budget-kimbap"]


def test_place_detail_returns_404_for_missing_place(client):
    response = client.get('/places/does-not-exist')

    assert response.status_code == 404


def test_places_endpoint_matches_alias_from_override_taxonomy(client):
    response = client.get('/places', params={'query': '중도', 'limit': 5})

    assert response.status_code == 200
    payload = response.json()
    assert any(item['slug'] == 'central-library' for item in payload)


def test_nearby_restaurants_returns_404_for_missing_origin(client):
    response = client.get('/restaurants/nearby', params={'origin': 'does-not-exist'})

    assert response.status_code == 404


def test_nearby_restaurants_accepts_origin_alias(client):
    response = client.get('/restaurants/nearby', params={'origin': '중도', 'limit': 3})

    assert response.status_code == 200
    items = response.json()
    assert items
    assert all(item['origin'] == 'central-library' for item in items)


def test_nearby_restaurants_accepts_facility_alias_origin(client):
    response = client.get('/restaurants/nearby', params={'origin': '학생식당', 'limit': 3})

    assert response.status_code == 200
    items = response.json()
    assert items
    assert all(item['origin'] == 'student-center' for item in items)


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
    assert response.json() == []


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
