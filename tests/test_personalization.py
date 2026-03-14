from __future__ import annotations

from datetime import datetime

import pytest

from songsim_campus.db import connection, init_db
from songsim_campus.repo import replace_courses, replace_notices, replace_restaurants
from songsim_campus.schemas import ProfileCourseRef, ProfileNoticePreferences
from songsim_campus.seed import seed_demo
from songsim_campus.services import (
    InvalidRequestError,
    create_profile,
    get_place,
    get_profile_meal_recommendations,
    get_profile_timetable,
    list_profile_notices,
    set_profile_notice_preferences,
    set_profile_timetable,
)


def _course_row(
    *,
    code: str,
    title: str,
    day: str,
    period_start: int,
    period_end: int,
    room: str,
    section: str = "01",
) -> dict:
    return {
        "year": 2026,
        "semester": 1,
        "code": code,
        "title": title,
        "professor": "테스트교수",
        "department": "컴퓨터정보공학부",
        "section": section,
        "day_of_week": day,
        "period_start": period_start,
        "period_end": period_end,
        "room": room,
        "raw_schedule": f"{day}{period_start}~{period_end}({room})",
        "source_tag": "test",
        "last_synced_at": "2026-03-13T09:00:00+09:00",
    }


def _notice_row(title: str, category: str, *, summary: str, labels: list[str]) -> dict:
    return {
        "title": title,
        "category": category,
        "published_at": "2026-03-12",
        "summary": summary,
        "labels": labels,
        "source_url": "https://example.edu/notices/1",
        "source_tag": "test",
        "last_synced_at": "2026-03-13T09:00:00+09:00",
    }


def _restaurant_row(
    *,
    slug: str,
    name: str,
    latitude: float,
    longitude: float,
    category: str = "korean",
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
        "source_tag": "test",
        "last_synced_at": "2026-03-13T09:00:00+09:00",
    }


def test_profile_timetable_uses_stable_course_keys_and_resolves_after_course_resync(app_env):
    init_db()
    seed_demo(force=True)
    with connection() as conn:
        replace_courses(
            conn,
            [
                _course_row(
                    code="CSE101",
                    title="자료구조",
                    day="월",
                    period_start=7,
                    period_end=8,
                    room="K201",
                )
            ],
        )
        profile = create_profile(conn, display_name="성심학생")
        set_profile_timetable(
            conn,
            profile.id,
            [ProfileCourseRef(year=2026, semester=1, code="CSE101", section="01")],
        )

        replace_courses(
            conn,
            [
                _course_row(
                    code="CSE101",
                    title="자료구조(개편)",
                    day="월",
                    period_start=7,
                    period_end=8,
                    room="K201",
                )
            ],
        )
        courses = get_profile_timetable(conn, profile.id, year=2026, semester=1)

    assert [course.title for course in courses] == ["자료구조(개편)"]


def test_profile_timetable_rejects_unknown_course_keys(app_env):
    init_db()
    seed_demo(force=True)
    with connection() as conn:
        profile = create_profile(conn)

        with pytest.raises(InvalidRequestError):
            set_profile_timetable(
                conn,
                profile.id,
                [ProfileCourseRef(year=2026, semester=1, code="NOPE101", section="01")],
            )


def test_profile_notices_require_preferences_and_match_category_or_keyword(app_env):
    init_db()
    with connection() as conn:
        profile = create_profile(conn)
        replace_notices(
            conn,
            [
                _notice_row(
                    "2026학년도 1학기 수강신청 안내",
                    "academic",
                    summary="수강신청 일정 안내",
                    labels=["학사"],
                ),
                _notice_row(
                    "커리어 특강 안내",
                    "event",
                    summary="진로와 자기소개서 특강",
                    labels=["특강"],
                ),
            ],
        )

        with pytest.raises(InvalidRequestError):
            list_profile_notices(conn, profile.id)

        set_profile_notice_preferences(
            conn,
            profile.id,
            ProfileNoticePreferences(categories=["academic"], keywords=["자기소개서"]),
        )
        notices = list_profile_notices(conn, profile.id)

    assert [notice.title for notice in notices] == [
        "커리어 특강 안내",
        "2026학년도 1학기 수강신청 안내",
    ]


def test_meal_recommendations_use_next_course_destination_when_room_maps_to_place(app_env):
    init_db()
    seed_demo(force=True)
    with connection() as conn:
        replace_courses(
            conn,
            [
                _course_row(
                    code="CSE101",
                    title="자료구조",
                    day="월",
                    period_start=7,
                    period_end=8,
                    room="K201",
                )
            ],
        )
        library = get_place(conn, "central-library")
        hall = get_place(conn, "kim-soo-hwan-hall")
        replace_restaurants(
            conn,
            [
                _restaurant_row(
                    slug="midpoint-bap",
                    name="중간백반",
                    latitude=(library.latitude + hall.latitude) / 2,
                    longitude=(library.longitude + hall.longitude) / 2,
                )
            ],
        )
        profile = create_profile(conn)
        set_profile_timetable(
            conn,
            profile.id,
            [ProfileCourseRef(year=2026, semester=1, code="CSE101", section="01")],
        )

        recommendation = get_profile_meal_recommendations(
            conn,
            profile.id,
            origin="central-library",
            at=datetime.fromisoformat("2026-03-16T12:00:00+09:00"),
            year=2026,
            semester=1,
        )

    assert recommendation.reason is None
    assert recommendation.next_place is not None
    assert recommendation.next_place.slug == "kim-soo-hwan-hall"
    assert recommendation.items[0].restaurant.name == "중간백반"


def test_meal_recommendations_return_reason_when_gap_is_too_short(app_env):
    init_db()
    seed_demo(force=True)
    with connection() as conn:
        replace_courses(
            conn,
            [
                _course_row(
                    code="CSE201",
                    title="알고리즘",
                    day="월",
                    period_start=6,
                    period_end=6,
                    room="K201",
                )
            ],
        )
        profile = create_profile(conn)
        set_profile_timetable(
            conn,
            profile.id,
            [ProfileCourseRef(year=2026, semester=1, code="CSE201", section="01")],
        )

        recommendation = get_profile_meal_recommendations(
            conn,
            profile.id,
            origin="central-library",
            at=datetime.fromisoformat("2026-03-16T13:45:00+09:00"),
            year=2026,
            semester=1,
        )

    assert recommendation.items == []
    assert recommendation.reason == "Not enough time before the next class."


def test_meal_recommendations_fallback_to_origin_only_when_room_cannot_map(app_env):
    init_db()
    seed_demo(force=True)
    with connection() as conn:
        replace_courses(
            conn,
            [
                _course_row(
                    code="CSE301",
                    title="운영체제",
                    day="월",
                    period_start=7,
                    period_end=8,
                    room="ZZ101",
                )
            ],
        )
        library = get_place(conn, "central-library")
        replace_restaurants(
            conn,
            [
                _restaurant_row(
                    slug="library-bap",
                    name="도서관백반",
                    latitude=library.latitude + 0.0002,
                    longitude=library.longitude + 0.0002,
                )
            ],
        )
        profile = create_profile(conn)
        set_profile_timetable(
            conn,
            profile.id,
            [ProfileCourseRef(year=2026, semester=1, code="CSE301", section="01")],
        )

        recommendation = get_profile_meal_recommendations(
            conn,
            profile.id,
            origin="central-library",
            at=datetime.fromisoformat("2026-03-16T12:00:00+09:00"),
            year=2026,
            semester=1,
        )

    assert recommendation.next_place is None
    assert recommendation.items[0].restaurant.name == "도서관백반"
