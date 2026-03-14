from __future__ import annotations

from datetime import datetime

import pytest

from songsim_campus.db import connection, init_db
from songsim_campus.repo import (
    replace_courses,
    replace_notices,
    replace_restaurants,
    update_place_opening_hours,
)
from songsim_campus.schemas import (
    ProfileCourseRef,
    ProfileInterests,
    ProfileNoticePreferences,
    ProfileUpdateRequest,
)
from songsim_campus.seed import seed_demo
from songsim_campus.services import (
    InvalidRequestError,
    KakaoPlace,
    create_profile,
    get_place,
    get_profile_course_recommendations,
    get_profile_interests,
    get_profile_meal_recommendations,
    get_profile_timetable,
    list_profile_notices,
    set_profile_interests,
    set_profile_notice_preferences,
    set_profile_timetable,
    update_profile,
)
from songsim_campus.settings import clear_settings_cache


def _course_row(
    *,
    code: str,
    title: str,
    day: str,
    period_start: int,
    period_end: int,
    room: str,
    department: str = "컴퓨터정보공학부",
    section: str = "01",
) -> dict:
    return {
        "year": 2026,
        "semester": 1,
        "code": code,
        "title": title,
        "professor": "테스트교수",
        "department": department,
        "section": section,
        "day_of_week": day,
        "period_start": period_start,
        "period_end": period_end,
        "room": room,
        "raw_schedule": f"{day}{period_start}~{period_end}({room})",
        "source_tag": "test",
        "last_synced_at": "2026-03-13T09:00:00+09:00",
    }


def _notice_row(
    title: str,
    category: str,
    *,
    summary: str,
    labels: list[str],
    published_at: str = "2026-03-12",
) -> dict:
    return {
        "title": title,
        "category": category,
        "published_at": published_at,
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


def test_profile_update_and_interests_validate_and_persist(app_env):
    init_db()
    with connection() as conn:
        profile = create_profile(conn)
        updated = update_profile(
            conn,
            profile.id,
            ProfileUpdateRequest(
                display_name="성심학생",
                department="컴퓨터정보공학부",
                student_year=1,
                admission_type="freshman",
            ),
        )
        interests = set_profile_interests(
            conn,
            profile.id,
            ProfileInterests(tags=["language", "language", "scholarship"]),
        )
        loaded_interests = get_profile_interests(conn, profile.id)

        with pytest.raises(InvalidRequestError):
            update_profile(conn, profile.id, ProfileUpdateRequest(student_year=7))

        with pytest.raises(InvalidRequestError):
            set_profile_interests(conn, profile.id, ProfileInterests(tags=["unknown-tag"]))

    assert updated.display_name == "성심학생"
    assert updated.department == "컴퓨터정보공학부"
    assert updated.student_year == 1
    assert updated.admission_type == "freshman"
    assert interests.tags == ["language", "scholarship"]
    assert loaded_interests.tags == ["language", "scholarship"]


def test_profile_notices_match_profile_context_and_return_reasons(app_env):
    init_db()
    with connection() as conn:
        empty_profile = create_profile(conn)
        profile = create_profile(conn)
        update_profile(
            conn,
            profile.id,
            ProfileUpdateRequest(
                department="컴퓨터정보공학부",
                student_year=1,
                admission_type="exchange",
            ),
        )
        set_profile_interests(conn, profile.id, ProfileInterests(tags=["scholarship"]))
        replace_notices(
            conn,
            [
                _notice_row(
                    "2026학년도 1학기 수강신청 안내",
                    "academic",
                    summary="수강신청 일정 안내",
                    labels=["학사"],
                    published_at="2026-03-11",
                ),
                _notice_row(
                    "커리어 특강 안내",
                    "event",
                    summary="진로와 자기소개서 특강",
                    labels=["특강"],
                    published_at="2026-03-12",
                ),
                _notice_row(
                    "컴퓨터정보공학부 신입생 장학금 안내",
                    "student",
                    summary="교환학생도 신청 가능한 장학 공지",
                    labels=["컴퓨터정보공학부", "신입생"],
                    published_at="2026-03-13",
                ),
            ],
        )

        with pytest.raises(InvalidRequestError):
            list_profile_notices(conn, empty_profile.id)

        set_profile_notice_preferences(
            conn,
            profile.id,
            ProfileNoticePreferences(categories=["academic"], keywords=["자기소개서"]),
        )
        notices = list_profile_notices(conn, profile.id)

    assert [item.notice.title for item in notices] == [
        "컴퓨터정보공학부 신입생 장학금 안내",
        "커리어 특강 안내",
        "2026학년도 1학기 수강신청 안내",
    ]
    assert notices[0].matched_reasons == [
        "department:컴퓨터정보공학부",
        "student_year:1",
        "admission_type:exchange",
        "interest:scholarship",
    ]
    assert notices[1].matched_reasons == ["keyword:자기소개서"]
    assert notices[2].matched_reasons == ["category:academic"]


def test_profile_course_recommendations_prioritize_department_and_exclude_timetable(app_env):
    init_db()
    seed_demo(force=True)
    with connection() as conn:
        replace_courses(
            conn,
            [
                _course_row(
                    code="CSE101",
                    title="컴퓨터정보공학부 세미나",
                    day="월",
                    period_start=7,
                    period_end=8,
                    room="K201",
                ),
                _course_row(
                    code="CSE102",
                    title="1학년 프로젝트입문",
                    day="화",
                    period_start=3,
                    period_end=4,
                    room="K201",
                ),
                _course_row(
                    code="HIS101",
                    title="역사와사회",
                    day="수",
                    period_start=5,
                    period_end=6,
                    room="M101",
                    department="사학과",
                    section="02",
                ),
            ],
        )
        profile = create_profile(conn)
        update_profile(
            conn,
            profile.id,
            ProfileUpdateRequest(department="컴퓨터정보공학부", student_year=1),
        )
        set_profile_timetable(
            conn,
            profile.id,
            [ProfileCourseRef(year=2026, semester=1, code="CSE101", section="01")],
        )

        items = get_profile_course_recommendations(
            conn,
            profile.id,
            year=2026,
            semester=1,
        )

        with pytest.raises(InvalidRequestError):
            get_profile_course_recommendations(
                conn,
                create_profile(conn).id,
                year=2026,
                semester=1,
            )

    assert [item.course.code for item in items] == ["CSE102"]
    assert items[0].matched_reasons == ["department:컴퓨터정보공학부", "student_year:1"]


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


def test_meal_recommendations_use_campus_graph_for_external_route_segments(app_env):
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

    assert recommendation.next_place is not None
    assert recommendation.next_place.slug == "kim-soo-hwan-hall"
    assert recommendation.items[0].restaurant.estimated_walk_minutes == 6
    assert recommendation.items[0].total_estimated_walk_minutes == 11


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


def test_meal_recommendations_open_now_returns_reason_when_only_closed_matches(app_env):
    init_db()
    seed_demo(force=True)
    with connection() as conn:
        replace_courses(
            conn,
            [
                _course_row(
                    code="CSE401",
                    title="캡스톤디자인",
                    day="일",
                    period_start=8,
                    period_end=9,
                    room="K201",
                )
            ],
        )
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
            {"카페드림": "평일 08:00~19:00 토 10:00~16:00 (일/공휴일휴무)"},
            last_synced_at="2026-03-13T09:00:00+09:00",
        )
        profile = create_profile(conn)
        set_profile_timetable(
            conn,
            profile.id,
            [ProfileCourseRef(year=2026, semester=1, code="CSE401", section="01")],
        )

        recommendation = get_profile_meal_recommendations(
            conn,
            profile.id,
            origin="central-library",
            at=datetime.fromisoformat("2026-03-15T12:00:00+09:00"),
            year=2026,
            semester=1,
            open_now=True,
        )

    assert recommendation.items == []
    assert recommendation.reason == "No currently open restaurants matched the filters."


def test_meal_recommendations_reuse_kakao_cache(app_env, monkeypatch):
    init_db()
    seed_demo(force=True)
    with connection() as conn:
        replace_courses(
            conn,
            [
                _course_row(
                    code="CSE501",
                    title="데이터마이닝",
                    day="월",
                    period_start=7,
                    period_end=8,
                    room="K201",
                )
            ],
        )
        profile = create_profile(conn)
        set_profile_timetable(
            conn,
            profile.id,
            [ProfileCourseRef(year=2026, semester=1, code="CSE501", section="01")],
        )

    monkeypatch.setenv("SONGSIM_KAKAO_REST_API_KEY", "test-key")
    clear_settings_cache()

    class CacheAwareKakaoClient:
        calls = 0

        def __init__(self, api_key: str):
            assert api_key == "test-key"

        def search_sync(self, query: str, *, x=None, y=None, radius: int = 1000):
            type(self).calls += 1
            return [
                KakaoPlace(
                    name="가톨릭백반",
                    category="음식점 > 한식",
                    address="경기 부천시 원미구",
                    latitude=37.48674,
                    longitude=126.80182,
                    place_url="https://place.map.kakao.com/1",
                )
            ]

    monkeypatch.setattr('songsim_campus.services.KakaoLocalClient', CacheAwareKakaoClient)

    with connection() as conn:
        first = get_profile_meal_recommendations(
            conn,
            profile.id,
            origin="central-library",
            at=datetime.fromisoformat("2026-03-16T12:00:00+09:00"),
            year=2026,
            semester=1,
        )
        second = get_profile_meal_recommendations(
            conn,
            profile.id,
            origin="central-library",
            at=datetime.fromisoformat("2026-03-16T12:00:00+09:00"),
            year=2026,
            semester=1,
        )

    assert CacheAwareKakaoClient.calls == 1
    assert first.items[0].restaurant.source_tag == "kakao_local"
    assert second.items[0].restaurant.source_tag == "kakao_local_cache"
