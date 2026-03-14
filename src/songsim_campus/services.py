from __future__ import annotations

import math
import re
import sqlite3
import uuid
from datetime import datetime
from typing import Any

import httpx

from . import repo
from .ingest.kakao_places import KakaoLocalClient, KakaoPlace
from .ingest.official_sources import (
    CampusFacilitiesSource,
    CampusMapSource,
    CourseCatalogSource,
    LibraryHoursSource,
    NoticeSource,
    TransportGuideSource,
)
from .schemas import (
    Course,
    MealRecommendation,
    MealRecommendationResponse,
    NearbyRestaurant,
    Notice,
    Period,
    Place,
    Profile,
    ProfileCourseRef,
    ProfileNoticePreferences,
    Restaurant,
    TransportGuide,
)
from .settings import get_settings

WALKING_METERS_PER_MINUTE = 75
COURSE_SOURCE_URL = "https://www.catholic.ac.kr/ko/support/subject.do"
NOTICE_SOURCE_URL = "https://www.catholic.ac.kr/ko/campuslife/notice.do"
CAMPUS_MAP_SOURCE_URL = "https://www.catholic.ac.kr/ko/about/campus-map.do"
LIBRARY_HOURS_SOURCE_URL = "https://library.catholic.ac.kr/webcontent/info/45"
FACILITIES_SOURCE_URL = "https://www.catholic.ac.kr/ko/campuslife/restaurant.do"
TRANSPORT_SOURCE_URL = "https://www.catholic.ac.kr/ko/about/location_songsim.do"
CLASS_PERIODS = [
    (1, "09:00", "09:50"),
    (2, "10:00", "10:50"),
    (3, "11:00", "11:50"),
    (4, "12:00", "12:50"),
    (5, "13:00", "13:50"),
    (6, "14:00", "14:50"),
    (7, "15:00", "15:50"),
    (8, "16:00", "16:50"),
    (9, "17:00", "17:50"),
    (10, "18:00", "18:50"),
]


class NotFoundError(ValueError):
    pass


class InvalidRequestError(ValueError):
    pass


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _current_year_and_semester(now: datetime | None = None) -> tuple[int, int]:
    current = now or datetime.now().astimezone()
    semester = 1 if current.month <= 6 else 2
    return current.year, semester


def _coerce_datetime(value: datetime | None = None) -> datetime:
    current = value or datetime.now().astimezone()
    return current if current.tzinfo else current.astimezone()


def _normalize_place_key(value: str) -> str:
    normalized = value.strip().lower()
    normalized = normalized.split(",")[0]
    normalized = normalized.replace("가톨릭대학교", "")
    normalized = normalized.replace("성심교정", "")
    normalized = normalized.replace("중앙도서관", "중앙도서관")
    normalized = "".join(char for char in normalized if not char.isspace())
    normalized = "".join(char for char in normalized if char not in "()")
    for marker in ["지하", "층", "호", "동"]:
        if marker == "층":
            normalized = normalized.split(marker)[0]
    normalized = normalized.rstrip("0123456789")
    return normalized


def _place_index(conn: sqlite3.Connection) -> dict[str, str]:
    index: dict[str, str] = {}
    for place in repo.list_places(conn):
        keys = [place["name"], *place.get("aliases", [])]
        for key in keys:
            normalized = _normalize_place_key(key)
            if normalized:
                index[normalized] = place["slug"]
    return index


def _location_candidates(value: str) -> list[str]:
    candidates: list[str] = []
    for item in value.replace("/", ",").split(","):
        token = item.strip()
        if not token:
            continue
        token = token.replace("가톨릭대학교", "")
        token = token.replace("성심교정", "")
        token = token.split()[0] if " " in token else token
        token = token.split("층")[0]
        token = token.split("호")[0]
        token = token.strip()
        if token:
            candidates.append(token)
    return candidates


def _day_label_from_datetime(value: datetime) -> str:
    return ["월", "화", "수", "목", "금", "토", "일"][value.weekday()]


def _period_start_minutes(period: int | None) -> int | None:
    if period is None:
        return None
    for item_period, start, _ in CLASS_PERIODS:
        if item_period == period:
            hour, minute = start.split(":")
            return int(hour) * 60 + int(minute)
    return None


def _unique_stripped(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = value.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def _resolve_place_from_room(conn: sqlite3.Connection, room: str | None) -> Place | None:
    if not room:
        return None
    place_lookup = _place_index(conn)
    candidates = [room]
    match = re.match(r"([A-Za-z]+)", room)
    if match:
        prefix = match.group(1).upper()
        candidates.extend([prefix, f"{prefix}관"])
    for candidate in candidates:
        slug = place_lookup.get(_normalize_place_key(candidate))
        if slug:
            return get_place(conn, slug)
    return None


def _ensure_profile(conn: sqlite3.Connection, profile_id: str) -> Profile:
    row = repo.get_profile(conn, profile_id)
    if not row:
        raise NotFoundError(f"Profile not found: {profile_id}")
    return Profile.model_validate(row)


def get_class_periods() -> list[Period]:
    return [Period(period=period, start=start, end=end) for period, start, end in CLASS_PERIODS]


def search_places(
    conn: sqlite3.Connection,
    query: str = "",
    category: str | None = None,
    limit: int = 10,
) -> list[Place]:
    return [Place.model_validate(item) for item in repo.search_places(conn, query, category, limit)]


def search_courses(
    conn: sqlite3.Connection,
    query: str = "",
    *,
    year: int | None = None,
    semester: int | None = None,
    limit: int = 20,
) -> list[Course]:
    return [
        Course.model_validate(item)
        for item in repo.search_courses(conn, query, year=year, semester=semester, limit=limit)
    ]


def list_latest_notices(
    conn: sqlite3.Connection,
    category: str | None = None,
    limit: int = 10,
) -> list[Notice]:
    return [Notice.model_validate(item) for item in repo.list_notices(conn, category, limit)]


def list_transport_guides(
    conn: sqlite3.Connection,
    mode: str | None = None,
    limit: int = 20,
) -> list[TransportGuide]:
    return [
        TransportGuide.model_validate(item)
        for item in repo.list_transport_guides(conn, mode=mode, limit=limit)
    ]


def create_profile(conn: sqlite3.Connection, display_name: str = "") -> Profile:
    created_at = _now_iso()
    profile_id = uuid.uuid4().hex
    repo.create_profile(
        conn,
        profile_id=profile_id,
        display_name=display_name.strip(),
        created_at=created_at,
        updated_at=created_at,
    )
    return _ensure_profile(conn, profile_id)


def set_profile_timetable(
    conn: sqlite3.Connection,
    profile_id: str,
    courses: list[ProfileCourseRef],
) -> list[Course]:
    _ensure_profile(conn, profile_id)
    unique_courses = _unique_stripped(
        [
            f"{item.year}:{item.semester}:{item.code.strip()}:{item.section.strip()}"
            for item in courses
        ]
    )
    refs = [
        ProfileCourseRef(
            year=int(year),
            semester=int(semester),
            code=code,
            section=section,
        )
        for year, semester, code, section in (item.split(":", 3) for item in unique_courses)
    ]
    missing = [
        ref
        for ref in refs
        if repo.get_course_by_key(
            conn,
            year=ref.year,
            semester=ref.semester,
            code=ref.code,
            section=ref.section,
        )
        is None
    ]
    if missing:
        first = missing[0]
        raise InvalidRequestError(
            "Course not found for timetable import: "
            f"{first.year}-{first.semester} {first.code} {first.section}"
        )
    updated_at = _now_iso()
    repo.replace_profile_courses(
        conn,
        profile_id,
        [ref.model_dump() for ref in refs],
        updated_at=updated_at,
    )
    return get_profile_timetable(conn, profile_id)


def get_profile_timetable(
    conn: sqlite3.Connection,
    profile_id: str,
    *,
    year: int | None = None,
    semester: int | None = None,
) -> list[Course]:
    _ensure_profile(conn, profile_id)
    refs = repo.list_profile_courses(conn, profile_id, year=year, semester=semester)
    courses: list[Course] = []
    for ref in refs:
        row = repo.get_course_by_key(
            conn,
            year=ref["year"],
            semester=ref["semester"],
            code=ref["code"],
            section=ref["section"],
        )
        if row:
            courses.append(Course.model_validate(row))
    return courses


def set_profile_notice_preferences(
    conn: sqlite3.Connection,
    profile_id: str,
    preferences: ProfileNoticePreferences,
) -> ProfileNoticePreferences:
    _ensure_profile(conn, profile_id)
    categories = _unique_stripped(preferences.categories)
    keywords = _unique_stripped(preferences.keywords)
    if not categories and not keywords:
        raise InvalidRequestError(
            "Notice preferences must include at least one category or keyword."
        )
    repo.save_profile_notice_preferences(
        conn,
        profile_id,
        categories=categories,
        keywords=keywords,
        updated_at=_now_iso(),
    )
    return ProfileNoticePreferences(categories=categories, keywords=keywords)


def list_profile_notices(
    conn: sqlite3.Connection,
    profile_id: str,
    *,
    limit: int = 10,
) -> list[Notice]:
    _ensure_profile(conn, profile_id)
    preferences = repo.get_profile_notice_preferences(conn, profile_id)
    if not preferences or (not preferences["categories"] and not preferences["keywords"]):
        raise InvalidRequestError("Profile has no notice preferences.")

    categories = set(preferences["categories"])
    keywords = [keyword.lower() for keyword in preferences["keywords"]]
    matched: list[Notice] = []
    for item in repo.list_notices(conn, limit=max(limit * 5, 100)):
        label_set = set(item.get("labels", []))
        text = " ".join([item["title"], item.get("summary", "")]).lower()
        if item["category"] in categories or label_set.intersection(categories):
            matched.append(Notice.model_validate(item))
            continue
        if any(keyword in text for keyword in keywords):
            matched.append(Notice.model_validate(item))
    return matched[:limit]


def get_profile_meal_recommendations(
    conn: sqlite3.Connection,
    profile_id: str,
    *,
    origin: str,
    at: datetime | None = None,
    year: int | None = None,
    semester: int | None = None,
    budget_max: int | None = None,
    category: str | None = None,
    limit: int = 10,
) -> MealRecommendationResponse:
    current = _coerce_datetime(at)
    resolved_year, resolved_semester = _current_year_and_semester(current)
    timetable = get_profile_timetable(
        conn,
        profile_id,
        year=year or resolved_year,
        semester=semester or resolved_semester,
    )
    day_label = _day_label_from_datetime(current)
    same_day_courses = [
        course
        for course in timetable
        if course.day_of_week == day_label
        and _period_start_minutes(course.period_start) is not None
    ]
    same_day_courses.sort(key=lambda item: _period_start_minutes(item.period_start) or 9999)

    next_course = None
    for course in same_day_courses:
        start_minutes = _period_start_minutes(course.period_start)
        current_minutes = current.hour * 60 + current.minute
        if start_minutes is not None and start_minutes > current_minutes:
            next_course = course
            break

    next_place = _resolve_place_from_room(conn, next_course.room) if next_course else None
    available_minutes = None
    if next_course and next_course.period_start is not None:
        start_minutes = _period_start_minutes(next_course.period_start)
        current_minutes = current.hour * 60 + current.minute
        if start_minutes is not None:
            available_minutes = start_minutes - current_minutes - 10
            if available_minutes < 20:
                return MealRecommendationResponse(
                    items=[],
                    next_course=next_course,
                    next_place=next_place,
                    available_minutes=available_minutes,
                    reason="Not enough time before the next class.",
                )

    walk_limit = 15 if available_minutes is None else max(1, min(available_minutes, 60))
    nearby = find_nearby_restaurants(
        conn,
        origin=origin,
        category=category,
        budget_max=budget_max,
        walk_minutes=walk_limit,
        limit=max(limit * 5, 20),
    )

    items: list[MealRecommendation] = []
    for restaurant in nearby:
        total_walk_minutes = restaurant.estimated_walk_minutes
        if (
            next_place is not None
            and next_place.latitude is not None
            and next_place.longitude is not None
        ):
            second_leg = max(
                1,
                round(
                    _haversine_meters(
                        restaurant.latitude,
                        restaurant.longitude,
                        next_place.latitude,
                        next_place.longitude,
                    )
                    / WALKING_METERS_PER_MINUTE
                ),
            )
            total_walk_minutes = (restaurant.estimated_walk_minutes or 0) + second_leg
            if available_minutes is not None and total_walk_minutes + 10 > available_minutes:
                continue
        items.append(
            MealRecommendation(
                restaurant=restaurant,
                next_course=next_course,
                next_place=next_place,
                total_estimated_walk_minutes=total_walk_minutes,
            )
        )

    items.sort(
        key=lambda item: (
            item.total_estimated_walk_minutes or 999,
            item.restaurant.min_price or 0,
            item.restaurant.name,
        )
    )
    return MealRecommendationResponse(
        items=items[:limit],
        next_course=next_course,
        next_place=next_place,
        available_minutes=available_minutes,
    )


def _haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    radius = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return int(2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


def _category_to_kakao_query(category: str | None) -> str:
    mapping = {
        "korean": "한식",
        "japanese": "일식",
        "western": "양식",
        "chinese": "중식",
        "cafe": "카페",
    }
    return mapping.get(category or "", "식당")


def _infer_kakao_category(category_name: str) -> str:
    normalized = category_name.lower()
    if "카페" in category_name or "cafe" in normalized:
        return "cafe"
    if "일식" in category_name or "japanese" in normalized:
        return "japanese"
    if "양식" in category_name or "western" in normalized:
        return "western"
    if "중식" in category_name or "chinese" in normalized:
        return "chinese"
    return "korean"


def _normalize_kakao_restaurant(place: KakaoPlace, *, fetched_at: str) -> dict[str, Any]:
    slug = f"kakao-{place.name}-{place.latitude:.5f}-{place.longitude:.5f}".lower()
    slug = "".join(char if char.isalnum() else "-" for char in slug).strip("-")
    return {
        "slug": slug,
        "name": place.name,
        "category": _infer_kakao_category(place.category),
        "min_price": None,
        "max_price": None,
        "latitude": place.latitude,
        "longitude": place.longitude,
        "tags": [segment.strip() for segment in place.category.split(">") if segment.strip()][-2:],
        "description": place.address,
        "source_tag": "kakao_local",
        "last_synced_at": fetched_at,
    }


def _live_restaurant_rows(
    *,
    place: dict[str, Any],
    category: str | None,
    walk_minutes: int,
    kakao_client: KakaoLocalClient | Any,
) -> list[dict[str, Any]]:
    query = _category_to_kakao_query(category)
    radius = walk_minutes * WALKING_METERS_PER_MINUTE
    fetched_at = _now_iso()
    try:
        items = kakao_client.search_sync(
            query,
            x=place["longitude"],
            y=place["latitude"],
            radius=radius,
        )
    except httpx.HTTPError:
        return []
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        row = _normalize_kakao_restaurant(item, fetched_at=fetched_at)
        row["id"] = -index
        rows.append(row)
    return rows


def find_nearby_restaurants(
    conn: sqlite3.Connection,
    *,
    origin: str,
    category: str | None = None,
    budget_max: int | None = None,
    walk_minutes: int = 15,
    limit: int = 10,
    kakao_client: KakaoLocalClient | Any | None = None,
) -> list[NearbyRestaurant]:
    place = repo.get_place_by_slug_or_name(conn, origin)
    if not place:
        raise NotFoundError(f"Origin place not found: {origin}")
    if place.get("latitude") is None or place.get("longitude") is None:
        raise NotFoundError(f"Origin place has no coordinates: {origin}")

    has_local_restaurants = repo.count_rows(conn, "restaurants") > 0

    if kakao_client is None and not has_local_restaurants and get_settings().kakao_rest_api_key:
        kakao_client = KakaoLocalClient(get_settings().kakao_rest_api_key)

    raw_restaurants = (
        _live_restaurant_rows(
            place=place,
            category=category,
            walk_minutes=walk_minutes,
            kakao_client=kakao_client,
        )
        if kakao_client is not None
        else repo.list_restaurants(conn)
    )

    results: list[NearbyRestaurant] = []
    for raw in raw_restaurants:
        if category and raw["category"] != category:
            continue
        if (
            budget_max is not None
            and raw.get("min_price") is not None
            and raw["min_price"] > budget_max
        ):
            continue
        if raw.get("latitude") is None or raw.get("longitude") is None:
            continue

        distance = _haversine_meters(
            place["latitude"],
            place["longitude"],
            raw["latitude"],
            raw["longitude"],
        )
        estimated_walk_minutes = max(1, round(distance / WALKING_METERS_PER_MINUTE))
        if estimated_walk_minutes > walk_minutes:
            continue

        results.append(
            NearbyRestaurant.model_validate(
                {
                    **raw,
                    "distance_meters": distance,
                    "estimated_walk_minutes": estimated_walk_minutes,
                    "origin": place["slug"],
                }
            )
        )

    results.sort(
        key=lambda item: (
            item.estimated_walk_minutes or 999,
            item.min_price or 0,
            item.name,
        )
    )
    return results[:limit]


def refresh_places_from_campus_map(
    conn: sqlite3.Connection,
    *,
    source: CampusMapSource | Any | None = None,
    campus: str = "1",
    fetched_at: str | None = None,
) -> list[Place]:
    source = source or CampusMapSource(CAMPUS_MAP_SOURCE_URL)
    synced_at = fetched_at or _now_iso()
    payload = source.fetch_place_list(campus=campus)
    rows = source.parse_place_list(payload, fetched_at=synced_at)
    repo.replace_places(conn, rows)
    return [
        Place.model_validate(item)
        for item in repo.search_places(conn, limit=max(len(rows), 1))
    ]


def refresh_library_hours_from_library_page(
    conn: sqlite3.Connection,
    *,
    source: LibraryHoursSource | Any | None = None,
    fetched_at: str | None = None,
) -> list[Place]:
    source = source or LibraryHoursSource(LIBRARY_HOURS_SOURCE_URL)
    synced_at = fetched_at or _now_iso()
    rows = source.parse(source.fetch(), fetched_at=synced_at)
    place_lookup = _place_index(conn)
    updated: list[Place] = []
    seen_slugs: set[str] = set()
    for row in rows:
        slug = place_lookup.get(_normalize_place_key(row["place_name"]))
        if not slug:
            continue
        repo.update_place_opening_hours(
            conn,
            slug,
            row["opening_hours"],
            last_synced_at=row.get("last_synced_at", synced_at),
        )
        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)
        updated.append(get_place(conn, slug))
    return updated


def refresh_facility_hours_from_facilities_page(
    conn: sqlite3.Connection,
    *,
    source: CampusFacilitiesSource | Any | None = None,
    fetched_at: str | None = None,
) -> list[Place]:
    source = source or CampusFacilitiesSource(FACILITIES_SOURCE_URL)
    synced_at = fetched_at or _now_iso()
    rows = source.parse(source.fetch(), fetched_at=synced_at)
    place_lookup = _place_index(conn)
    touched: list[Place] = []
    seen_slugs: set[str] = set()
    for row in rows:
        slug = None
        for candidate in _location_candidates(row["location"]):
            slug = place_lookup.get(_normalize_place_key(candidate))
            if slug:
                break
        if not slug:
            continue
        repo.update_place_opening_hours(
            conn,
            slug,
            {row["facility_name"]: row["hours_text"]},
            last_synced_at=row.get("last_synced_at", synced_at),
        )
        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)
        touched.append(get_place(conn, slug))
    return touched


def refresh_courses_from_subject_search(
    conn: sqlite3.Connection,
    *,
    source: CourseCatalogSource | Any | None = None,
    year: int | None = None,
    semester: int | None = None,
    fetched_at: str | None = None,
) -> list[Course]:
    source = source or CourseCatalogSource(COURSE_SOURCE_URL)
    synced_at = fetched_at or _now_iso()
    resolved_year, resolved_semester = _current_year_and_semester()
    html = source.fetch(
        year=year or resolved_year,
        semester=semester or resolved_semester,
        department="ALL",
        completion_type="ALL",
        query="",
    )
    rows = source.parse(html, fetched_at=synced_at)
    repo.replace_courses(conn, rows)
    return [
        Course.model_validate(item)
        for item in repo.search_courses(
            conn,
            year=year or resolved_year,
            semester=semester or resolved_semester,
            limit=max(len(rows), 1),
        )
    ]


def refresh_notices_from_notice_board(
    conn: sqlite3.Connection,
    *,
    source: NoticeSource | Any | None = None,
    pages: int = 1,
    fetched_at: str | None = None,
) -> list[Notice]:
    source = source or NoticeSource(NOTICE_SOURCE_URL)
    synced_at = fetched_at or _now_iso()
    rows: list[dict[str, Any]] = []
    seen_articles: set[str] = set()
    for page in range(pages):
        offset = page * 10
        list_html = source.fetch_list(offset=offset, limit=10)
        for item in source.parse_list(list_html):
            article_no = item.get("article_no")
            if not article_no or article_no in seen_articles:
                continue
            seen_articles.add(article_no)
            try:
                detail_html = source.fetch_detail(article_no, offset=offset, limit=10)
                detail = source.parse_detail(
                    detail_html,
                    default_title=item["title"],
                    default_category=item.get("board_category", ""),
                )
            except httpx.HTTPError:
                detail = {
                    "title": item["title"],
                    "published_at": item.get("published_at"),
                    "summary": "",
                    "labels": [],
                    "category": item.get("board_category") or "general",
                }

            rows.append(
                {
                    "title": detail["title"],
                    "category": detail["category"],
                    "published_at": detail.get("published_at") or item.get("published_at"),
                    "summary": detail.get("summary", ""),
                    "labels": detail.get("labels", []),
                    "source_url": item.get("source_url"),
                    "source_tag": "cuk_campus_notices",
                    "last_synced_at": synced_at,
                }
            )
    repo.replace_notices(conn, rows)
    return [
        Notice.model_validate(item)
        for item in repo.list_notices(conn, limit=max(len(rows), 1))
    ]


def refresh_transport_guides_from_location_page(
    conn: sqlite3.Connection,
    *,
    source: TransportGuideSource | Any | None = None,
    fetched_at: str | None = None,
) -> list[TransportGuide]:
    source = source or TransportGuideSource(TRANSPORT_SOURCE_URL)
    synced_at = fetched_at or _now_iso()
    rows = source.parse(source.fetch(), fetched_at=synced_at)
    repo.replace_transport_guides(conn, rows)
    return [
        TransportGuide.model_validate(item)
        for item in repo.list_transport_guides(conn, limit=max(len(rows), 1))
    ]


def sync_official_snapshot(
    conn: sqlite3.Connection,
    *,
    campus: str | None = None,
    year: int | None = None,
    semester: int | None = None,
    notice_pages: int | None = None,
) -> dict[str, int]:
    settings = get_settings()
    resolved_year = year or settings.official_course_year
    resolved_semester = semester or settings.official_course_semester
    places = refresh_places_from_campus_map(
        conn,
        campus=campus or settings.official_campus_id,
    )
    refresh_library_hours_from_library_page(conn)
    refresh_facility_hours_from_facilities_page(conn)
    courses = refresh_courses_from_subject_search(
        conn,
        year=resolved_year,
        semester=resolved_semester,
    )
    notices = refresh_notices_from_notice_board(
        conn,
        pages=notice_pages or settings.official_notice_pages,
    )
    transport_guides = refresh_transport_guides_from_location_page(conn)
    return {
        "places": len(places),
        "courses": len(courses),
        "notices": len(notices),
        "transport_guides": len(transport_guides),
    }


def get_place(conn: sqlite3.Connection, identifier: str) -> Place:
    place = repo.get_place_by_slug_or_name(conn, identifier)
    if not place:
        raise NotFoundError(f"Place not found: {identifier}")
    return Place.model_validate(place)


def list_restaurants(conn: sqlite3.Connection) -> list[Restaurant]:
    return [Restaurant.model_validate(item) for item in repo.list_restaurants(conn)]
