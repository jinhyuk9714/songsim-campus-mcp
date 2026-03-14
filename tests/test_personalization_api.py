from __future__ import annotations

from songsim_campus.db import connection
from songsim_campus.repo import replace_courses, replace_notices, replace_restaurants
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
    assert notices_with_preferences.json()[0]["category"] == "academic"


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
