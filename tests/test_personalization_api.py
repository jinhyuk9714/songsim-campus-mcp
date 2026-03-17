from __future__ import annotations

from songsim_campus.db import connection
from songsim_campus.repo import (
    replace_courses,
    replace_notices,
    replace_restaurants,
    update_place_opening_hours,
)
from songsim_campus.seed import seed_demo


def _course_row() -> dict:
    return {
        "year": 2026,
        "semester": 1,
        "code": "CSE101",
        "title": "자료구조",
        "professor": "테스트교수",
        "department": "컴퓨터정보공학부",
        "section": "01",
        "day_of_week": "월",
        "period_start": 7,
        "period_end": 8,
        "room": "K201",
        "raw_schedule": "월7~8(K201)",
        "source_tag": "test",
        "last_synced_at": "2026-03-13T09:00:00+09:00",
    }


def test_profile_endpoints_store_timetable_and_notice_preferences(client):
    with connection() as conn:
        seed_demo(force=True)
        replace_courses(conn, [_course_row()])
        replace_notices(
            conn,
            [
                {
                    "title": "2026학년도 1학기 수강신청 안내",
                    "category": "academic",
                    "published_at": "2026-03-12",
                    "summary": "수강신청 일정 안내",
                    "labels": ["학사"],
                    "source_url": "https://example.edu/notices/1",
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                }
            ],
        )

    created = client.post("/profiles", json={"display_name": "성심학생"})
    profile_id = created.json()["id"]

    timetable_response = client.put(
        f"/profiles/{profile_id}/timetable",
        json=[{"year": 2026, "semester": 1, "code": "CSE101", "section": "01"}],
    )
    notices_without_preferences = client.get(f"/profiles/{profile_id}/notices")
    preferences_response = client.put(
        f"/profiles/{profile_id}/notice-preferences",
        json={"categories": ["academic"], "keywords": []},
    )
    notices_with_preferences = client.get(f"/profiles/{profile_id}/notices")

    assert created.status_code == 200
    assert timetable_response.status_code == 200
    assert timetable_response.json()[0]["title"] == "자료구조"
    assert notices_without_preferences.status_code == 400
    assert preferences_response.status_code == 200
    assert notices_with_preferences.status_code == 200
    assert notices_with_preferences.json()[0]["notice"]["category"] == "academic"


def test_profile_notice_preferences_endpoint_canonicalizes_aliases_and_matches_legacy_categories(
    client,
):
    with connection() as conn:
        seed_demo(force=True)
        replace_notices(
            conn,
            [
                {
                    "title": "진로취업상담 안내",
                    "category": "career",
                    "published_at": "2026-03-12",
                    "summary": "진로 상담 공지",
                    "labels": ["취창업"],
                    "source_url": "https://example.edu/notices/career",
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
                {
                    "title": "중앙도서관 자리 안내",
                    "category": "place",
                    "published_at": "2026-03-13",
                    "summary": "도서관 자리 현황 안내",
                    "labels": ["생활"],
                    "source_url": "https://example.edu/notices/place",
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
            ],
        )

    created = client.post("/profiles", json={"display_name": "성심학생"})
    profile_id = created.json()["id"]

    preferences_response = client.put(
        f"/profiles/{profile_id}/notice-preferences",
        json={"categories": ["career", "employment", "place"], "keywords": []},
    )
    notices_response = client.get(f"/profiles/{profile_id}/notices")

    assert created.status_code == 200
    assert preferences_response.status_code == 200
    assert preferences_response.json()["categories"] == ["employment", "general"]
    assert notices_response.status_code == 200
    assert [item["notice"]["title"] for item in notices_response.json()] == [
        "중앙도서관 자리 안내",
        "진로취업상담 안내",
    ]
    assert [item["notice"]["category"] for item in notices_response.json()] == [
        "general",
        "employment",
    ]


def test_profile_patch_interests_and_course_recommendations_endpoints(client):
    with connection() as conn:
        seed_demo(force=True)
        replace_courses(
            conn,
            [
                {
                    "year": 2026,
                    "semester": 1,
                    "code": "CSE201",
                    "title": "1학년 프로젝트입문",
                    "professor": "테스트교수",
                    "department": "컴퓨터정보공학부",
                    "section": "01",
                    "day_of_week": "화",
                    "period_start": 3,
                    "period_end": 4,
                    "room": "K201",
                    "raw_schedule": "화3~4(K201)",
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
                {
                    "year": 2026,
                    "semester": 1,
                    "code": "CSE201",
                    "title": "컴정 1학년 프로젝트입문",
                    "professor": "테스트교수",
                    "department": "컴퓨터정보공학부",
                    "section": "02",
                    "day_of_week": "수",
                    "period_start": 4,
                    "period_end": 5,
                    "room": "K202",
                    "raw_schedule": "수4~5(K202)",
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                }
            ],
        )
        replace_notices(
            conn,
            [
                {
                    "title": "컴퓨터정보공학부 신입생 장학금 안내",
                    "category": "student",
                    "published_at": "2026-03-12",
                    "summary": "장학 신청 공지",
                    "labels": ["컴퓨터정보공학부", "신입생"],
                    "source_url": "https://example.edu/notices/2",
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
                {
                    "title": "자기소개서 특강 안내",
                    "category": "event",
                    "published_at": "2026-03-13",
                    "summary": "커리어 자기소개서 첨삭 특강",
                    "labels": ["특강"],
                    "source_url": "https://example.edu/notices/3",
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                }
            ],
        )

    created = client.post("/profiles", json={"display_name": "성심학생"})
    profile_id = created.json()["id"]

    patch_response = client.patch(
        f"/profiles/{profile_id}",
        json={
            "department": "컴퓨터정보공학부",
            "student_year": 1,
            "admission_type": "freshman",
        },
    )
    interests_response = client.put(
        f"/profiles/{profile_id}/interests",
        json={"tags": ["scholarship", "language", "scholarship"]},
    )
    get_interests_response = client.get(f"/profiles/{profile_id}/interests")
    notices_response = client.get(f"/profiles/{profile_id}/notices")
    courses_response = client.get(
        f"/profiles/{profile_id}/courses/recommended",
        params={"year": 2026, "semester": 1},
    )

    assert patch_response.status_code == 200
    assert patch_response.json()["department"] == "컴퓨터정보공학부"
    assert interests_response.status_code == 200
    assert interests_response.json()["tags"] == ["scholarship", "language"]
    assert get_interests_response.status_code == 200
    assert get_interests_response.json()["tags"] == ["scholarship", "language"]
    assert notices_response.status_code == 200
    assert notices_response.json()[0]["matched_reasons"] == [
        "department:컴퓨터정보공학부",
        "student_year:1",
        "admission_type:freshman",
        "interest:scholarship",
    ]
    assert notices_response.json()[0]["notice"]["title"] == "컴퓨터정보공학부 신입생 장학금 안내"
    assert courses_response.status_code == 200
    assert courses_response.json()[0]["course"]["code"] == "CSE201"
    assert courses_response.json()[0]["course"]["section"] == "02"


def test_profile_personalization_endpoints_validate_payloads(client):
    created = client.post("/profiles")
    profile_id = created.json()["id"]

    invalid_patch = client.patch(
        f"/profiles/{profile_id}",
        json={"student_year": 7, "admission_type": "mystery"},
    )
    invalid_interests = client.put(
        f"/profiles/{profile_id}/interests",
        json={"tags": ["mystery"]},
    )
    no_context_courses = client.get(f"/profiles/{profile_id}/courses/recommended")

    assert invalid_patch.status_code == 400
    assert invalid_interests.status_code == 400
    assert no_context_courses.status_code == 400


def test_meal_recommendations_endpoint_returns_reason_for_short_gap(client):
    with connection() as conn:
        seed_demo(force=True)
        replace_courses(
            conn,
            [
                {
                    "year": 2026,
                    "semester": 1,
                    "code": "CSE201",
                    "title": "알고리즘",
                    "professor": "테스트교수",
                    "department": "컴퓨터정보공학부",
                    "section": "01",
                    "day_of_week": "월",
                    "period_start": 6,
                    "period_end": 6,
                    "room": "K201",
                    "raw_schedule": "월6(K201)",
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                }
            ],
        )
        replace_restaurants(
            conn,
            [
                {
                    "slug": "midpoint-bap",
                    "name": "중간백반",
                    "category": "korean",
                    "min_price": 7000,
                    "max_price": 9000,
                    "latitude": 37.4865,
                    "longitude": 126.8015,
                    "tags": ["한식"],
                    "description": "테스트 식당",
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                }
            ],
        )

    created = client.post("/profiles")
    profile_id = created.json()["id"]
    client.put(
        f"/profiles/{profile_id}/timetable",
        json=[{"year": 2026, "semester": 1, "code": "CSE201", "section": "01"}],
    )

    response = client.get(
        f"/profiles/{profile_id}/meal-recommendations",
        params={
            "origin": "central-library",
            "at": "2026-03-16T13:45:00+09:00",
            "year": 2026,
            "semester": 1,
        },
    )

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["reason"] == "Not enough time before the next class."


def test_meal_recommendations_endpoint_can_filter_open_now(client):
    with connection() as conn:
        seed_demo(force=True)
        replace_courses(
            conn,
            [
                {
                    "year": 2026,
                    "semester": 1,
                    "code": "CSE401",
                    "title": "캡스톤디자인",
                    "professor": "테스트교수",
                    "department": "컴퓨터정보공학부",
                    "section": "01",
                    "day_of_week": "일",
                    "period_start": 8,
                    "period_end": 9,
                    "room": "K201",
                    "raw_schedule": "일8~9(K201)",
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                }
            ],
        )
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
                }
            ],
        )
        update_place_opening_hours(
            conn,
            "central-library",
            {"카페드림": "평일 08:00~19:00 토 10:00~16:00 (일/공휴일휴무)"},
            last_synced_at="2026-03-13T09:00:00+09:00",
        )

    created = client.post("/profiles")
    profile_id = created.json()["id"]
    client.put(
        f"/profiles/{profile_id}/timetable",
        json=[{"year": 2026, "semester": 1, "code": "CSE401", "section": "01"}],
    )

    response = client.get(
        f"/profiles/{profile_id}/meal-recommendations",
        params={
            "origin": "central-library",
            "open_now": True,
            "at": "2026-03-15T12:00:00+09:00",
            "year": 2026,
            "semester": 1,
        },
    )

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["reason"] == "No currently open restaurants matched the filters."


def test_meal_recommendations_endpoint_uses_campus_graph_for_external_routes(client):
    with connection() as conn:
        seed_demo(force=True)
        replace_courses(conn, [_course_row()])
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

    created = client.post("/profiles")
    profile_id = created.json()["id"]
    client.put(
        f"/profiles/{profile_id}/timetable",
        json=[{"year": 2026, "semester": 1, "code": "CSE101", "section": "01"}],
    )

    response = client.get(
        f"/profiles/{profile_id}/meal-recommendations",
        params={
            "origin": "central-library",
            "at": "2026-03-16T12:00:00+09:00",
            "year": 2026,
            "semester": 1,
        },
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["restaurant"]["estimated_walk_minutes"] == 6
    assert response.json()["items"][0]["total_estimated_walk_minutes"] == 11
