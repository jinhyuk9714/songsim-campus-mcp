from __future__ import annotations

import heapq
import json
import logging
import math
import re
import unicodedata
import uuid
from copy import deepcopy
from datetime import date, datetime, timedelta
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any, Protocol

import httpx
from pypdf import PdfReader

from . import ops_runtime, place_search_runtime, repo
from .db import DBConnection, connection, get_connection
from .ingest.kakao_places import (
    KakaoLocalClient,
    KakaoPlace,
    KakaoPlaceDetailClient,
    extract_kakao_place_id,
    parse_place_detail_opening_hours,
)
from .ingest.official_sources import (
    AcademicCalendarSource,
    AcademicSupportGuideSource,
    CampusFacilitiesSource,
    CampusMapSource,
    CertificateGuideSource,
    CourseCatalogSource,
    DropoutGuideSource,
    LeaveOfAbsenceGuideSource,
    LibraryHoursSource,
    LibrarySeatStatusSource,
    NoticeSource,
    ReAdmissionGuideSource,
    RegistrationBillLookupGuideSource,
    RegistrationPaymentAndReturnGuideSource,
    RegistrationPaymentByStudentGuideSource,
    ReturnFromLeaveOfAbsenceGuideSource,
    ScholarshipGuideSource,
    TransportGuideSource,
    WifiGuideSource,
    classify_notice_category,
)
from .schemas import (
    AcademicCalendarEvent,
    AcademicStatusGuide,
    AcademicSupportGuide,
    AutomationJobObservability,
    AutomationObservability,
    CampusDiningMenu,
    CertificateGuide,
    Course,
    EmptyClassroomBuilding,
    EstimatedEmptyClassroom,
    EstimatedEmptyClassroomResponse,
    LeaveOfAbsenceGuide,
    LibrarySeatStatus,
    LibrarySeatStatusResponse,
    MatchedCourse,
    MatchedNotice,
    MealRecommendation,
    MealRecommendationResponse,
    NearbyRestaurant,
    Notice,
    NoticeCategoryInfo,
    ObservabilitySnapshot,
    Period,
    Place,
    Profile,
    ProfileCourseRef,
    ProfileInterests,
    ProfileNoticePreferences,
    ProfileUpdateRequest,
    RegistrationGuide,
    Restaurant,
    RestaurantSearchResult,
    ScholarshipGuide,
    SyncRun,
    TransportGuide,
    WifiGuide,
)
from .settings import get_settings

WALKING_METERS_PER_MINUTE = 75
COURSE_SOURCE_URL = "https://www.catholic.ac.kr/ko/support/subject.do"
NOTICE_SOURCE_URL = "https://www.catholic.ac.kr/ko/campuslife/notice.do"
CAMPUS_MAP_SOURCE_URL = "https://www.catholic.ac.kr/ko/about/campus-map.do"
LIBRARY_HOURS_SOURCE_URL = "https://library.catholic.ac.kr/webcontent/info/45"
LIBRARY_SEAT_STATUS_SOURCE_URL = "http://203.229.203.240/8080/Domian5.asp"
FACILITIES_SOURCE_URL = "https://www.catholic.ac.kr/ko/campuslife/restaurant.do"
TRANSPORT_SOURCE_URL = "https://www.catholic.ac.kr/ko/about/location_songsim.do"
CERTIFICATE_SOURCE_URL = "https://www.catholic.ac.kr/ko/support/certificate.do"
LEAVE_OF_ABSENCE_SOURCE_URL = "https://www.catholic.ac.kr/ko/support/leave_of_absence.do"
SCHOLARSHIP_GUIDE_SOURCE_URL = "https://www.catholic.ac.kr/ko/support/scholarship_songsim.do"
WIFI_GUIDE_SOURCE_URL = "https://www.catholic.ac.kr/ko/campuslife/wifi.do"
ACADEMIC_CALENDAR_SOURCE_URL = "https://www.catholic.ac.kr/ko/support/calendar2024_list.do"
ACADEMIC_SUPPORT_GUIDE_SOURCE_URL = "https://www.catholic.ac.kr/ko/support/academic_contact_information.do"
RETURN_FROM_LEAVE_SOURCE_URL = "https://www.catholic.ac.kr/ko/support/return_from_leave_of_absence.do"
DROPOUT_GUIDE_SOURCE_URL = "https://www.catholic.ac.kr/ko/support/dropout.do"
RE_ADMISSION_GUIDE_SOURCE_URL = "https://www.catholic.ac.kr/ko/support/re_admission.do"
REGISTRATION_BILL_LOOKUP_SOURCE_URL = (
    "https://www.catholic.ac.kr/ko/support/tuition_fee_payment_schedule.do"
)
REGISTRATION_PAYMENT_AND_RETURN_SOURCE_URL = (
    "https://www.catholic.ac.kr/ko/support/tuition_payment_and_returning.do"
)
REGISTRATION_PAYMENT_BY_STUDENT_SOURCE_URL = (
    "https://www.catholic.ac.kr/ko/support/tuition_payment_by_student.do"
)
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
CAMPUS_WALK_GRAPH_PATH = DATA_DIR / "campus_walk_graph.json"
PERSONALIZATION_RULES_PATH = DATA_DIR / "personalization_rules.json"
RESTAURANT_SEARCH_ALIASES_PATH = DATA_DIR / "restaurant_search_aliases.json"
RESTAURANT_SEARCH_NOISE_TERMS_PATH = DATA_DIR / "restaurant_search_noise_terms.json"
SYNC_DATASET_TABLES = (
    "places",
    "campus_facilities",
    "campus_dining_menus",
    "courses",
    "notices",
    "academic_calendar",
    "certificate_guides",
    "leave_of_absence_guides",
    "academic_status_guides",
    "registration_guides",
    "scholarship_guides",
    "wifi_guides",
    "academic_support_guides",
    "transport_guides",
)
PUBLIC_READY_CORE_DATASETS = frozenset(
    {
        "places",
        "notices",
        "academic_calendar",
        "certificate_guides",
        "leave_of_absence_guides",
        "academic_status_guides",
        "registration_guides",
        "scholarship_guides",
        "academic_support_guides",
        "wifi_guides",
        "transport_guides",
    }
)
PUBLIC_READY_BEST_EFFORT_DATASETS = frozenset({"campus_facilities", "campus_dining_menus"})
PUBLIC_READY_OPTIONAL_DATASETS = frozenset({"courses"})
PUBLIC_READY_REQUIRED_DATASETS = PUBLIC_READY_CORE_DATASETS
PUBLIC_READY_DATASET_POLICIES = {
    table: (
        "core"
        if table in PUBLIC_READY_CORE_DATASETS
        else "best_effort"
        if table in PUBLIC_READY_BEST_EFFORT_DATASETS
        else "optional"
    )
    for table in SYNC_DATASET_TABLES
}
ADMIN_SYNC_TARGETS = {
    "snapshot",
    "places",
    "campus_facilities",
    "library_hours",
    "library_seat_status",
    "facility_hours",
    "dining_menus",
    "courses",
    "notices",
    "academic_calendar",
    "leave_of_absence_guides",
    "academic_status_guides",
    "registration_guides",
    "scholarship_guides",
    "academic_support_guides",
    "wifi_guides",
    "transport_guides",
}
AUTOMATION_SYNC_TARGETS = {"snapshot", "library_seat_prewarm", "cache_cleanup"}
SYNC_RUN_TARGETS = ADMIN_SYNC_TARGETS | AUTOMATION_SYNC_TARGETS
AUTOMATION_LOCK_KEY = 20_260_314
ALLOWED_ADMISSION_TYPES = {"general", "freshman", "transfer", "exchange"}
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

logger = logging.getLogger(__name__)
OBSERVABILITY_EVENT_LIMIT = ops_runtime.OBSERVABILITY_EVENT_LIMIT
READINESS_CACHE_TTL_SECONDS = ops_runtime.READINESS_CACHE_TTL_SECONDS
READINESS_CACHE_MAX_STALE_SECONDS = ops_runtime.READINESS_CACHE_MAX_STALE_SECONDS
EMPTY_CLASSROOM_ESTIMATE_NOTE = (
    "공식 시간표 기준 예상 공실입니다. 실시간 점유는 반영되지 않습니다."
)
DEFAULT_RESTAURANT_SEARCH_ORIGIN = "central-library"
DEFAULT_RESTAURANT_SEARCH_RADIUS_METERS = 15 * WALKING_METERS_PER_MINUTE
EXTENDED_RESTAURANT_SEARCH_RADIUS_METERS = 5000
NOTICE_CATEGORY_FILTER_ALIASES = {
    "employment": ("employment", "career"),
    "career": ("employment", "career"),
    "general": ("general", "place"),
    "place": ("general", "place"),
}
PUBLIC_NOTICE_CATEGORY_METADATA = (
    {"category": "academic", "category_display": "학사", "aliases": []},
    {"category": "scholarship", "category_display": "장학", "aliases": []},
    {"category": "employment", "category_display": "취업", "aliases": ["career"]},
    {"category": "general", "category_display": "일반", "aliases": ["place"]},
)
LIBRARY_SEAT_GENERIC_QUERY_CUES = (
    "열람실",
    "좌석",
    "남은좌석",
    "좌석현황",
    "자리",
    "중앙도서관",
)
LIBRARY_SEAT_ROOM_QUERY_ALIASES = {
    "제1자유열람실": ("제1자유열람실", "1자유열람실", "1열람실"),
    "제2자유열람실": ("제2자유열람실", "2자유열람실", "2열람실"),
}
NOTICE_CANONICAL_LIST_CATEGORIES = {"학사", "장학", "취창업"}
TRANSPORT_UNSUPPORTED_QUERY_CUES = ("셔틀", "shuttle")
TRANSPORT_SUBWAY_QUERY_CUES = ("지하철", "전철", "1호선", "subway", "역곡역", "역곡")
TRANSPORT_BUS_QUERY_CUES = ("버스", "마을버스", "시내버스", "bus")
DINING_MENU_GENERIC_QUERY_CUES = (
    "교내 식당",
    "교내식당",
    "학생식당",
    "학식",
    "메뉴",
    "오늘 메뉴",
    "오늘메뉴",
    "내일 메뉴",
    "내일메뉴",
)
DINING_MENU_QUERY_FILLER_TERMS = (
    "메뉴",
    "오늘",
    "내일",
    "이번 주",
    "이번주",
    "주간",
)
ACADEMIC_STATUS_GUIDE_VALUES = {"return_from_leave", "dropout", "re_admission"}
REGISTRATION_GUIDE_TOPICS = {"bill_lookup", "payment_and_return", "payment_by_student"}


class NotFoundError(ValueError):
    pass


class InvalidRequestError(ValueError):
    pass


class OfficialClassroomAvailabilitySource(Protocol):
    def fetch_availability(
        self,
        *,
        building: Place,
        at: datetime,
        year: int,
        semester: int,
    ) -> list[dict[str, Any]]: ...


def _now() -> datetime:
    return datetime.now().astimezone()


def _now_iso() -> str:
    return _now().isoformat(timespec="seconds")


def _current_academic_year(today: date | None = None) -> int:
    resolved_today = today or _now().date()
    return resolved_today.year if resolved_today.month >= 3 else resolved_today.year - 1


def _academic_year_bounds(academic_year: int) -> tuple[str, str]:
    start = date(academic_year, 3, 1)
    end = date(academic_year + 1, 3, 1) - timedelta(days=1)
    return start.isoformat(), end.isoformat()


def _academic_month_bounds(academic_year: int, month: int) -> tuple[str, str]:
    if month < 1 or month > 12:
        raise InvalidRequestError("month must be an integer between 1 and 12.")
    year = academic_year if month >= 3 else academic_year + 1
    start = date(year, month, 1)
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    return start.isoformat(), (next_month - timedelta(days=1)).isoformat()


def _academic_calendar_priority(event: AcademicCalendarEvent) -> tuple[int, str, str, str, int]:
    return (
        0 if "성심" in event.campuses else 1,
        event.start_date,
        event.end_date,
        event.title,
        event.id,
    )


def _new_observability_state(process_started_at: str | None = None) -> dict[str, Any]:
    return ops_runtime._new_observability_state(
        process_started_at=process_started_at or _now_iso()
    )


_OBSERVABILITY_STATE = ops_runtime._OBSERVABILITY_STATE
_READINESS_CACHE_LOCK = ops_runtime._READINESS_CACHE_LOCK
_READINESS_CACHE = ops_runtime._READINESS_CACHE
_READINESS_REFRESH_IN_PROGRESS = ops_runtime._READINESS_REFRESH_IN_PROGRESS


def reset_observability_state() -> None:
    ops_runtime.reset_observability_state(process_started_at=_now_iso())


def reset_readiness_cache() -> None:
    ops_runtime.reset_readiness_cache()


def set_automation_leader(is_leader: bool) -> None:
    ops_runtime.set_automation_leader(is_leader)


def _prepend_observability_event(items: list[dict[str, Any]], payload: dict[str, Any]) -> None:
    ops_runtime.prepend_observability_event(items, payload)


def _record_cache_decision(
    *,
    decision: str,
    origin_slug: str,
    kakao_query: str,
    radius_meters: int,
    error_text: str | None = None,
) -> None:
    ops_runtime.record_cache_decision(
        decision=decision,
        origin_slug=origin_slug,
        kakao_query=kakao_query,
        radius_meters=radius_meters,
        occurred_at=_now_iso(),
        logger=logger,
        error_text=error_text,
    )


def _record_hours_cache_decision(
    *,
    decision: str,
    kakao_place_id: str,
    source_url: str | None,
    error_text: str | None = None,
) -> None:
    ops_runtime.record_hours_cache_decision(
        decision=decision,
        kakao_place_id=kakao_place_id,
        source_url=source_url,
        occurred_at=_now_iso(),
        logger=logger,
        error_text=error_text,
    )


def _record_sync_result(
    *,
    target: str,
    trigger: str,
    status: str,
    started_at: str,
    finished_at: str,
    summary: dict[str, int] | None = None,
    error_text: str | None = None,
) -> None:
    ops_runtime.record_sync_result(
        target=target,
        trigger=trigger,
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        logger=logger,
        summary=summary,
        error_text=error_text,
    )


def _readiness_cache_key(settings: Any) -> tuple[str, str]:
    return ops_runtime.readiness_cache_key(settings)


def _cache_readiness_snapshot(
    cache_key: tuple[str, str],
    *,
    fetched_at: datetime,
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    return ops_runtime.cache_readiness_snapshot(
        cache_key,
        fetched_at=fetched_at,
        snapshot=snapshot,
    )


def _readiness_snapshot_has_runtime_errors(snapshot: dict[str, Any]) -> bool:
    return ops_runtime.readiness_snapshot_has_runtime_errors(snapshot)


def _readiness_failure_reason(snapshot: dict[str, Any]) -> str:
    return ops_runtime.readiness_failure_reason(snapshot)


def _compute_and_store_readiness_snapshot(
    cache_key: tuple[str, str],
    settings: Any,
    *,
    background: bool,
) -> dict[str, Any]:
    logger.info(
        "event=readiness_refresh_started background=%s app_mode=%s",
        background,
        settings.app_mode,
    )
    snapshot = _compute_readiness_snapshot(settings)
    fetched_at = _now()
    ops_runtime.store_readiness_snapshot(
        cache_key,
        fetched_at=fetched_at,
        snapshot=snapshot,
    )
    if _readiness_snapshot_has_runtime_errors(snapshot):
        logger.warning(
            "event=readiness_refresh_failed background=%s app_mode=%s error=%s",
            background,
            settings.app_mode,
            _readiness_failure_reason(snapshot),
        )
    else:
        logger.info(
            "event=readiness_refresh_succeeded background=%s app_mode=%s ok=%s",
            background,
            settings.app_mode,
            snapshot.get("ok", False),
        )
    return snapshot


def _refresh_readiness_snapshot_in_background(
    cache_key: tuple[str, str],
    settings: Any,
) -> None:
    try:
        snapshot = _compute_readiness_snapshot(settings)
        if _readiness_snapshot_has_runtime_errors(snapshot):
            logger.warning(
                "event=readiness_refresh_failed background=%s app_mode=%s error=%s",
                True,
                settings.app_mode,
                _readiness_failure_reason(snapshot),
            )
            return
        fetched_at = _now()
        ops_runtime.store_readiness_snapshot(
            cache_key,
            fetched_at=fetched_at,
            snapshot=snapshot,
            clear_refresh_flag=False,
        )
        logger.info(
            "event=readiness_refresh_succeeded background=%s app_mode=%s ok=%s",
            True,
            settings.app_mode,
            snapshot.get("ok", False),
        )
    except Exception as exc:
        logger.warning(
            "event=readiness_refresh_failed background=%s app_mode=%s error=%s",
            True,
            settings.app_mode,
            exc,
        )
    finally:
        ops_runtime.clear_readiness_refresh_flag(cache_key)


def _start_background_readiness_refresh(
    cache_key: tuple[str, str],
    settings: Any,
) -> None:
    logger.info(
        "event=readiness_refresh_started background=%s app_mode=%s",
        True,
        settings.app_mode,
    )
    ops_runtime.start_background_readiness_refresh(
        target=_refresh_readiness_snapshot_in_background,
        args=(cache_key, settings),
    )


def _rollback_readiness_connection(conn: DBConnection) -> None:
    try:
        conn.rollback()
    except Exception:
        pass


def _compute_readiness_snapshot(settings: Any) -> dict[str, Any]:
    public_readonly = settings.app_mode == "public_readonly"
    readiness: dict[str, Any] = {
        "ok": True,
        "database": {"ok": False, "error": None},
        "tables": {},
    }
    try:
        conn = get_connection()
    except Exception as exc:
        readiness["ok"] = False
        readiness["database"] = {"ok": False, "error": str(exc)}
        logger.warning("event=readiness_check_failed check=database error=%s", exc)
        return readiness

    try:
        readiness["database"] = {"ok": True, "error": None}
        dataset_states, datasets_ok = ops_runtime.collect_dataset_sync_states(
            conn,
            tables=SYNC_DATASET_TABLES,
            public_readonly=public_readonly,
            dataset_policies=PUBLIC_READY_DATASET_POLICIES,
            capture_errors=True,
            rollback_connection=_rollback_readiness_connection,
            logger=logger,
            error_event_name="readiness_check_failed",
        )
        readiness["tables"].update(dataset_states)
        readiness["ok"] = readiness["ok"] and datasets_ok
        sync_runs_state, sync_runs_ok = ops_runtime.collect_sync_runs_table_state(
            conn,
            capture_errors=True,
            rollback_connection=_rollback_readiness_connection,
            logger=logger,
            error_event_name="readiness_check_failed",
        )
        readiness["tables"]["sync_runs"] = sync_runs_state
        readiness["ok"] = readiness["ok"] and sync_runs_ok
    finally:
        _rollback_readiness_connection(conn)
        conn.close()

    readiness["ok"] = readiness["database"]["ok"] and all(
        item.get("ok", False) for item in readiness["tables"].values()
    )
    return readiness


def get_readiness_snapshot() -> dict[str, Any]:
    settings = get_settings()
    cache_key = _readiness_cache_key(settings)
    current = _now()
    snapshot, start_background_refresh = ops_runtime.get_cached_readiness_snapshot(
        cache_key,
        current=current,
        is_snapshot_error=_readiness_snapshot_has_runtime_errors,
    )

    if snapshot is not None:
        if start_background_refresh:
            _start_background_readiness_refresh(cache_key, settings)
        return snapshot

    return deepcopy(
        _compute_and_store_readiness_snapshot(
            cache_key,
            settings,
            background=False,
        )
    )


def get_observability_snapshot(
    conn: DBConnection,
    *,
    runs_limit: int = 20,
) -> ObservabilitySnapshot:
    settings = get_settings()
    return ops_runtime.build_observability_snapshot(
        conn,
        runs_limit=runs_limit,
        now=_coerce_datetime(),
        public_readonly=settings.app_mode == "public_readonly",
        tables=SYNC_DATASET_TABLES,
        dataset_policies=PUBLIC_READY_DATASET_POLICIES,
        list_sync_runs_fn=list_sync_runs,
    )


def _automation_interval_minutes(target: str) -> int:
    try:
        return ops_runtime.automation_interval_minutes(target)
    except ValueError as exc:
        raise InvalidRequestError(str(exc)) from exc


def _sync_run_completed_at(run: dict[str, Any] | SyncRun | None) -> str | None:
    if isinstance(run, SyncRun):
        return run.finished_at or run.started_at
    return ops_runtime.sync_run_completed_at(run)


def _automation_job_snapshot(
    conn: DBConnection,
    *,
    target: str,
    now: datetime | None = None,
) -> AutomationJobObservability:
    return ops_runtime.automation_job_snapshot(
        conn,
        target=target,
        now=_coerce_datetime(now),
    )


def get_automation_status(
    conn: DBConnection,
    *,
    now: datetime | None = None,
) -> AutomationObservability:
    return ops_runtime.get_automation_status(
        conn,
        now=_coerce_datetime(now),
    )


def try_acquire_automation_leader(conn: DBConnection) -> bool:
    return ops_runtime.try_acquire_automation_leader(
        conn,
        lock_key=AUTOMATION_LOCK_KEY,
    )


def release_automation_leader(conn: DBConnection) -> bool:
    return ops_runtime.release_automation_leader(
        conn,
        lock_key=AUTOMATION_LOCK_KEY,
    )


def _is_automation_job_due(
    conn: DBConnection,
    *,
    target: str,
    now: datetime | None = None,
) -> bool:
    return ops_runtime.is_automation_job_due(
        conn,
        target=target,
        now=_coerce_datetime(now),
    )


def _current_year_and_semester(now: datetime | None = None) -> tuple[int, int]:
    current = now or _now()
    semester = 1 if current.month <= 6 else 2
    return current.year, semester


def _coerce_datetime(value: datetime | None = None) -> datetime:
    current = value or _now()
    return current if current.tzinfo else current.astimezone()


_normalize_place_key = place_search_runtime._normalize_place_key
_build_place_slug_lookup = place_search_runtime._build_place_slug_lookup
_build_place_slug_candidates_lookup = place_search_runtime._build_place_slug_candidates_lookup
_build_place_model_lookup = place_search_runtime._build_place_model_lookup
_location_candidates = place_search_runtime._location_candidates
_resolve_campus_facility_place_slug = place_search_runtime._resolve_campus_facility_place_slug
_load_place_alias_overrides = place_search_runtime._load_place_alias_overrides
_load_place_facility_keywords = place_search_runtime._load_place_facility_keywords
_load_place_short_query_preferences = place_search_runtime._load_place_short_query_preferences
_preferred_place_slugs_for_query = place_search_runtime._preferred_place_slugs_for_query
_display_name_for_place_result = place_search_runtime._display_name_for_place_result
_normalize_campus_facility_phone = place_search_runtime._normalize_campus_facility_phone
_normalize_campus_facility_location = place_search_runtime._normalize_campus_facility_location
_matched_facility_from_row = place_search_runtime._matched_facility_from_row
_facility_hours_index = place_search_runtime._facility_hours_index


def _place_index(conn: DBConnection) -> dict[str, str]:
    return _build_place_slug_lookup(repo.list_places(conn))


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


def _period_end_minutes(period: int | None) -> int | None:
    if period is None:
        return None
    for item_period, _, end in CLASS_PERIODS:
        if item_period == period:
            hour, minute = end.split(":")
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


def _unique_lower_stripped(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = value.strip().lower()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def _parse_restaurant_search_aliases(payload: Any) -> dict[str, list[str]]:
    if not isinstance(payload, dict):
        raise ValueError("restaurant search aliases must be a JSON object keyed by brand token")

    aliases: dict[str, list[str]] = {}
    for raw_brand, raw_aliases in payload.items():
        if not isinstance(raw_brand, str) or not raw_brand.strip():
            raise ValueError("restaurant search alias key must be a non-empty string")
        if not isinstance(raw_aliases, list) or any(
            not isinstance(item, str) for item in raw_aliases
        ):
            raise ValueError("restaurant search alias entries must be a list of strings")
        aliases[raw_brand.strip()] = _unique_stripped(list(raw_aliases))
    return aliases


@lru_cache(maxsize=1)
def _load_restaurant_search_aliases() -> dict[str, list[str]]:
    payload = json.loads(RESTAURANT_SEARCH_ALIASES_PATH.read_text(encoding="utf-8"))
    return _parse_restaurant_search_aliases(payload)


def _parse_restaurant_search_noise_terms(payload: Any) -> dict[str, list[str]]:
    if not isinstance(payload, dict):
        raise ValueError("restaurant search noise terms must be a JSON object")
    allowed_keys = {"name_terms", "tag_terms", "description_terms"}
    unknown_keys = set(payload) - allowed_keys
    if unknown_keys:
        raise ValueError(
            "restaurant search noise terms only support name_terms, tag_terms, "
            "and description_terms"
        )

    parsed: dict[str, list[str]] = {}
    for key in allowed_keys:
        raw_values = payload.get(key, [])
        if not isinstance(raw_values, list) or any(
            not isinstance(item, str) for item in raw_values
        ):
            raise ValueError(f"restaurant search noise terms {key} must be a list of strings")
        parsed[key] = _unique_stripped(list(raw_values))
    return parsed


@lru_cache(maxsize=1)
def _load_restaurant_search_noise_terms() -> dict[str, list[str]]:
    payload = json.loads(RESTAURANT_SEARCH_NOISE_TERMS_PATH.read_text(encoding="utf-8"))
    return _parse_restaurant_search_noise_terms(payload)


def apply_place_alias_overrides(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    overrides = _load_place_alias_overrides()
    merged_rows: list[dict[str, Any]] = []
    for row in rows:
        merged = dict(row)
        override = overrides.get(str(merged.get("slug") or "").strip())
        if override is not None:
            merged["aliases"] = _unique_stripped(
                [*list(merged.get("aliases", [])), *override.get("aliases", [])]
            )
            if override.get("category"):
                merged["category"] = override["category"]
        merged_rows.append(merged)
    return merged_rows


def _normalize_notice_category_filter(category: str | None) -> list[str] | None:
    cleaned = _normalize_optional_text(category)
    if cleaned is None:
        return None
    normalized = cleaned.lower()
    aliases = NOTICE_CATEGORY_FILTER_ALIASES.get(normalized)
    if aliases is not None:
        return list(aliases)
    return [normalized]


def _canonical_notice_category(category: str | None) -> str | None:
    cleaned = _normalize_optional_text(category)
    if cleaned is None:
        return None
    normalized = cleaned.lower()
    if normalized in {"employment", "career"}:
        return "employment"
    if normalized in {"general", "place"}:
        return "general"
    return normalized


def _normalize_notice_public_category(category: str | None) -> str:
    canonical = _canonical_notice_category(category)
    if canonical is None:
        return "general"
    if canonical in {"academic", "scholarship", "employment", "event", "facility", "library"}:
        return canonical
    return "general"


def _normalize_notice_preference_categories(categories: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for category in categories:
        canonical = _canonical_notice_category(category)
        if canonical is None or canonical in seen:
            continue
        seen.add(canonical)
        normalized.append(canonical)
    return normalized


def _canonicalize_notice_detail(
    *,
    item: dict[str, Any],
    detail: dict[str, Any],
) -> dict[str, Any]:
    board_category = _normalize_optional_text(item.get("board_category"))
    if board_category not in NOTICE_CANONICAL_LIST_CATEGORIES:
        return detail

    labels = [
        label
        for label in detail.get("labels", [])
        if _normalize_optional_text(label) not in {None, "공지", board_category}
    ]
    return {
        **detail,
        "labels": [board_category, *labels],
        "category": classify_notice_category(
            detail.get("title") or item.get("title", ""),
            detail.get("summary", ""),
            board_category,
        ),
    }


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _collapse_whitespace(value: str) -> str:
    return " ".join(value.split())


def _compact_text(value: str) -> str:
    return re.sub(r"\s+", "", value).strip()


def _normalized_query_variants(value: str | None) -> tuple[str | None, str | None]:
    cleaned = _normalize_optional_text(value)
    if cleaned is None:
        return None, None
    collapsed = _collapse_whitespace(cleaned)
    compacted = _compact_text(cleaned)
    return collapsed, compacted or None


def _matches_exact_text_candidate(
    text: str | None,
    *,
    collapsed_query: str,
    compact_query: str | None,
) -> bool:
    cleaned = _normalize_optional_text(text)
    if cleaned is None:
        return False
    collapsed_text = _collapse_whitespace(cleaned).lower()
    if collapsed_text == collapsed_query.lower():
        return True
    if compact_query is None:
        return False
    return _compact_text(cleaned).lower() == compact_query.lower()


def _matches_partial_text_candidate(
    text: str | None,
    *,
    collapsed_query: str,
    compact_query: str | None,
) -> bool:
    cleaned = _normalize_optional_text(text)
    if cleaned is None:
        return False
    collapsed_text = _collapse_whitespace(cleaned).lower()
    if collapsed_query.lower() in collapsed_text:
        return True
    if compact_query is None:
        return False
    compact_text = _compact_text(cleaned).lower()
    return bool(compact_query) and compact_query.lower() in compact_text


def _matches_prefix_text_candidate(
    text: str | None,
    *,
    collapsed_query: str,
    compact_query: str | None,
) -> bool:
    cleaned = _normalize_optional_text(text)
    if cleaned is None:
        return False
    collapsed_text = _collapse_whitespace(cleaned).lower()
    if collapsed_text.startswith(collapsed_query.lower()):
        return True
    if compact_query is None:
        return False
    compact_text = _compact_text(cleaned).lower()
    return bool(compact_query) and compact_text.startswith(compact_query.lower())


def _rank_course_search_candidate(
    item: dict[str, Any],
    *,
    collapsed_query: str,
    compact_query: str | None,
) -> int | None:
    code = str(item.get("code") or "")
    title = str(item.get("title") or "")
    professor = str(item.get("professor") or "")

    if _matches_exact_text_candidate(
        code,
        collapsed_query=collapsed_query,
        compact_query=compact_query,
    ):
        return 0
    if _matches_prefix_text_candidate(
        code,
        collapsed_query=collapsed_query,
        compact_query=compact_query,
    ):
        return 1
    if _matches_exact_text_candidate(
        title,
        collapsed_query=collapsed_query,
        compact_query=compact_query,
    ):
        return 2
    if _matches_prefix_text_candidate(
        title,
        collapsed_query=collapsed_query,
        compact_query=compact_query,
    ):
        return 3
    if _matches_exact_text_candidate(
        professor,
        collapsed_query=collapsed_query,
        compact_query=compact_query,
    ):
        return 4
    if _matches_prefix_text_candidate(
        professor,
        collapsed_query=collapsed_query,
        compact_query=compact_query,
    ):
        return 5
    if any(
        _matches_partial_text_candidate(
            field,
            collapsed_query=collapsed_query,
            compact_query=compact_query,
        )
        for field in (code, title, professor)
    ):
        return 6
    return None


def _normalize_transport_mode(mode: str | None) -> str | None:
    cleaned = _normalize_optional_text(mode)
    if cleaned is None:
        return None
    return cleaned.lower()


def _contains_transport_query_cue(
    compact_query: str,
    cues: tuple[str, ...],
) -> bool:
    lowered_query = compact_query.lower()
    return any(_compact_text(cue).lower() in lowered_query for cue in cues)


def _infer_transport_mode_from_query(query: str | None) -> str | None:
    _, compact_query = _normalized_query_variants(query)
    if compact_query is None:
        return None

    lowered_query = compact_query.lower()
    if _contains_transport_query_cue(compact_query, TRANSPORT_UNSUPPORTED_QUERY_CUES):
        return "unsupported"

    has_subway = _contains_transport_query_cue(compact_query, TRANSPORT_SUBWAY_QUERY_CUES)
    has_bus = _contains_transport_query_cue(compact_query, TRANSPORT_BUS_QUERY_CUES)
    if not has_subway and ("역에서" in lowered_query or lowered_query.endswith("역")):
        has_subway = True

    if "버스말고" in lowered_query or "버스빼고" in lowered_query:
        has_bus = False
    if "지하철말고" in lowered_query or "지하철빼고" in lowered_query:
        has_subway = False

    if has_subway and not has_bus:
        return "subway"
    if has_bus and not has_subway:
        return "bus"
    return None


def _rank_transport_guide_candidate(
    guide: TransportGuide,
    *,
    collapsed_query: str,
    compact_query: str | None,
) -> int | None:
    if _matches_exact_text_candidate(
        guide.title,
        collapsed_query=collapsed_query,
        compact_query=compact_query,
    ):
        return 0
    if _matches_exact_text_candidate(
        guide.summary,
        collapsed_query=collapsed_query,
        compact_query=compact_query,
    ):
        return 1
    if any(
        _matches_exact_text_candidate(
            step,
            collapsed_query=collapsed_query,
            compact_query=compact_query,
        )
        for step in guide.steps
    ):
        return 2
    if _matches_partial_text_candidate(
        guide.title,
        collapsed_query=collapsed_query,
        compact_query=compact_query,
    ):
        return 3
    if _matches_partial_text_candidate(
        guide.summary,
        collapsed_query=collapsed_query,
        compact_query=compact_query,
    ):
        return 4
    if any(
        _matches_partial_text_candidate(
            step,
            collapsed_query=collapsed_query,
            compact_query=compact_query,
        )
        for step in guide.steps
    ):
        return 5
    return None


def _rank_transport_guides(
    guides: list[TransportGuide],
    *,
    query: str,
    limit: int,
) -> list[TransportGuide]:
    collapsed_query, compact_query = _normalized_query_variants(query)
    if collapsed_query is None:
        return guides[:limit]

    def sort_key(guide: TransportGuide) -> tuple[int, str, str]:
        rank = _rank_transport_guide_candidate(
            guide,
            collapsed_query=collapsed_query,
            compact_query=compact_query,
        )
        return (99 if rank is None else rank, guide.mode, guide.title)

    ranked = sorted(guides, key=sort_key)
    return ranked[:limit]


def _restaurant_brand_aliases_for_row(item: dict[str, Any]) -> list[str]:
    normalized_targets = {
        _normalize_facility_name(str(item.get("name") or "")),
        *[
            _normalize_facility_name(str(tag))
            for tag in item.get("tags", [])
        ],
    }
    aliases: list[str] = []
    for canonical_brand, brand_aliases in _load_restaurant_search_aliases().items():
        normalized_brand = _normalize_facility_name(canonical_brand)
        if normalized_brand and any(
            normalized_brand in target for target in normalized_targets if target
        ):
            aliases.extend(brand_aliases)
    return _unique_stripped(aliases)


def _resolve_restaurant_brand_query_token(query: str) -> str:
    collapsed_query, _ = _normalized_query_variants(query)
    normalized_query = _normalize_facility_name(query)
    for canonical_brand, brand_aliases in _load_restaurant_search_aliases().items():
        for candidate in [canonical_brand, *brand_aliases]:
            if _normalize_facility_name(candidate) == normalized_query:
                return canonical_brand
    if collapsed_query is not None:
        return collapsed_query
    return query.strip()


def _restaurant_brand_exactness(
    item: dict[str, Any],
    *,
    canonical_query: str | None,
) -> int:
    if canonical_query is None:
        return 0

    normalized_brand_terms = _unique_lower_stripped(
        [
            canonical_query,
            *(_load_restaurant_search_aliases().get(canonical_query, [])),
        ]
    )
    if not normalized_brand_terms:
        return 2

    tag_targets = [
        _normalize_facility_name(str(tag))
        for tag in item.get("tags", [])
    ]
    name_target = _normalize_facility_name(str(item.get("name") or ""))

    if any(target == term for term in normalized_brand_terms for target in tag_targets if target):
        return 0
    if any(target == term for term in normalized_brand_terms for target in [name_target] if target):
        return 0
    if any(term in target for term in normalized_brand_terms for target in tag_targets if target):
        return 1
    if any(term in name_target for term in normalized_brand_terms if term and name_target):
        return 1
    return 2


def _restaurant_search_text_contains_noise(value: str | None, terms: list[str]) -> bool:
    normalized_value = _normalize_facility_name(value)
    if not normalized_value:
        return False
    return any(
        normalized_term in normalized_value
        for normalized_term in (_normalize_facility_name(term) for term in terms)
        if normalized_term
    )


def _is_restaurant_search_noise_candidate(item: dict[str, Any]) -> bool:
    noise_terms = _load_restaurant_search_noise_terms()
    if _restaurant_search_text_contains_noise(item.get("name"), noise_terms["name_terms"]):
        return True
    if any(
        _restaurant_search_text_contains_noise(str(tag), noise_terms["tag_terms"])
        for tag in item.get("tags", [])
    ):
        return True
    if _restaurant_search_text_contains_noise(
        item.get("description"),
        noise_terms["description_terms"],
    ):
        return True
    return False


def _rank_restaurant_search_candidate(
    item: dict[str, Any],
    *,
    collapsed_query: str,
    compact_query: str | None,
) -> int | None:
    name = str(item.get("name") or "")
    aliases = _restaurant_brand_aliases_for_row(item)
    tags = [str(tag) for tag in item.get("tags", [])]

    if any(
        _matches_exact_text_candidate(
            alias,
            collapsed_query=collapsed_query,
            compact_query=compact_query,
        )
        for alias in aliases
    ):
        return 0
    if _matches_exact_text_candidate(
        name,
        collapsed_query=collapsed_query,
        compact_query=compact_query,
    ):
        return 1
    if any(
        _matches_partial_text_candidate(
            alias,
            collapsed_query=collapsed_query,
            compact_query=compact_query,
        )
        for alias in aliases
    ):
        return 2
    if _matches_partial_text_candidate(
        name,
        collapsed_query=collapsed_query,
        compact_query=compact_query,
    ):
        return 3
    if any(
        _matches_partial_text_candidate(
            tag,
            collapsed_query=collapsed_query,
            compact_query=compact_query,
        )
        for tag in tags
    ):
        return 4
    return None


def _normalize_profile_display_name(value: str | None) -> str:
    return (value or "").strip()


def _validate_student_year(value: int | None) -> int | None:
    if value is None:
        return None
    if 1 <= value <= 6:
        return value
    raise InvalidRequestError("student_year must be between 1 and 6.")


def _validate_admission_type(value: str | None) -> str | None:
    cleaned = _normalize_optional_text(value)
    if cleaned is None:
        return None
    normalized = cleaned.lower()
    if normalized not in ALLOWED_ADMISSION_TYPES:
        raise InvalidRequestError(
            "admission_type must be one of: general, freshman, transfer, exchange."
        )
    return normalized


def _normalize_interest_tags(tags: list[str]) -> list[str]:
    normalized = _unique_lower_stripped(tags)
    invalid = [tag for tag in normalized if tag not in ALLOWED_PROFILE_INTERESTS]
    if invalid:
        raise InvalidRequestError(f"Unsupported interest tag: {invalid[0]}")
    return normalized


def _student_year_keywords(student_year: int | None) -> list[str]:
    if student_year is None:
        return []
    return list(_load_personalization_rules()["student_year_keywords"].get(student_year, []))


def _joined_notice_text(item: dict[str, Any]) -> str:
    parts = [item["category"], item["title"], item.get("summary", ""), *item.get("labels", [])]
    return " ".join(str(part) for part in parts if part).lower()


def _joined_course_text(course: Course) -> str:
    return " ".join(
        part
        for part in [
            course.title,
            course.department or "",
            course.raw_schedule or "",
        ]
        if part
    ).lower()


def _sort_matched_notices(items: list[tuple[int, MatchedNotice]]) -> list[MatchedNotice]:
    ranked = sorted(
        items,
        key=lambda item: (
            -item[0],
            -date.fromisoformat(item[1].notice.published_at).toordinal(),
            item[1].notice.title,
        ),
    )
    return [item for _, item in ranked]


def _normalize_facility_name(value: str) -> str:
    normalized = value.strip().lower()
    normalized = re.sub(r"\([^)]*\)", "", normalized)
    for token in ("가톨릭대학교", "가톨릭대", "성심교정"):
        normalized = normalized.replace(token, "")
    normalized = "".join(char for char in normalized if not char.isspace())
    if normalized.endswith("점"):
        normalized = normalized[:-1]
    return normalized


def _slugify_text(value: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text).strip("-").lower()
    return slug or _normalize_facility_name(value)


def _normalize_dining_menu_query(query: str | None) -> tuple[str | None, str | None, bool]:
    collapsed_query, compact_query = _normalized_query_variants(query)
    if collapsed_query is None:
        return None, None, True

    normalized_query = _normalize_facility_name(collapsed_query)
    generic_normalized = {
        _normalize_facility_name(item) for item in DINING_MENU_GENERIC_QUERY_CUES
    }
    stripped_query = collapsed_query
    for token in DINING_MENU_QUERY_FILLER_TERMS:
        stripped_query = stripped_query.replace(token, " ")
    stripped_query = _collapse_whitespace(stripped_query)
    stripped_compact = _compact_text(stripped_query)
    is_generic = (
        normalized_query in generic_normalized
        or _normalize_facility_name(stripped_query) in generic_normalized
        or not stripped_compact
    )
    return stripped_query or None, stripped_compact or None, is_generic


def _rank_campus_dining_menu_candidate(
    item: dict[str, Any],
    *,
    collapsed_query: str,
    compact_query: str | None,
) -> int | None:
    venue_name = str(item.get("venue_name") or "")
    venue_slug = str(item.get("venue_slug") or "")
    place_name = str(item.get("place_name") or "")
    if venue_slug.lower() == collapsed_query.lower():
        return 0
    if _matches_exact_text_candidate(
        venue_name,
        collapsed_query=collapsed_query,
        compact_query=compact_query,
    ):
        return 1
    if _matches_exact_text_candidate(
        place_name,
        collapsed_query=collapsed_query,
        compact_query=compact_query,
    ):
        return 2
    if _matches_partial_text_candidate(
        venue_name,
        collapsed_query=collapsed_query,
        compact_query=compact_query,
    ):
        return 3
    if _matches_partial_text_candidate(
        place_name,
        collapsed_query=collapsed_query,
        compact_query=compact_query,
    ):
        return 4
    lowered_query = collapsed_query.lower()
    if venue_name and venue_name.lower() in lowered_query:
        return 5
    if place_name and place_name.lower() in lowered_query:
        return 6
    return None


def _extract_campus_dining_menu_text(pdf_bytes: bytes) -> str | None:
    reader = PdfReader(BytesIO(pdf_bytes))
    lines: list[str] = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        for raw_line in page_text.splitlines():
            cleaned = raw_line.strip()
            if cleaned:
                lines.append(cleaned)
    if not lines:
        return None
    return "\n".join(lines)


def _extract_campus_dining_menu_week_range(
    menu_text: str | None,
) -> tuple[str | None, str | None]:
    if not menu_text:
        return None, None

    match = re.search(
        r"(\d{4})[./-](\d{2})[./-](\d{2})\s*[-~]\s*"
        r"(?:(\d{4})[./-](\d{2})[./-](\d{2})|(\d{2})[./-](\d{2}))",
        menu_text,
    )
    if not match:
        return None, None

    start_year = int(match.group(1))
    start_month = int(match.group(2))
    start_day = int(match.group(3))
    if match.group(4) is not None:
        end_year = int(match.group(4))
        end_month = int(match.group(5))
        end_day = int(match.group(6))
    else:
        end_year = start_year
        end_month = start_month
        end_day = int(match.group(8))

    try:
        week_start = date(start_year, start_month, start_day).isoformat()
        week_end = date(end_year, end_month, end_day).isoformat()
    except ValueError:
        return None, None
    return week_start, week_end


def _resolve_campus_dining_menu_place(
    conn: DBConnection,
    *,
    facility_name: str,
    location: str,
) -> Place | None:
    place_lookup = _place_index(conn)
    for candidate in _location_candidates(location):
        slug = place_lookup.get(_normalize_place_key(candidate))
        if slug:
            return get_place(conn, slug)
    query_candidates = [facility_name]
    korean_query = " ".join(re.findall(r"[가-힣]+", facility_name))
    if korean_query and korean_query not in query_candidates:
        query_candidates.append(korean_query)
    for candidate_query in query_candidates:
        matches = search_places(conn, query=candidate_query, limit=1)
        if matches:
            return matches[0]
    return None


def _campus_dining_menu_preview(menu_text: str | None, *, limit: int = 220) -> str | None:
    if not menu_text:
        return None
    preview = " | ".join(line.strip() for line in menu_text.splitlines() if line.strip())
    if len(preview) <= limit:
        return preview
    return preview[: max(0, limit - 3)].rstrip() + "..."


def _minutes_from_time_string(value: str) -> int | None:
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", value.strip())
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    if minute > 59:
        return None
    if hour == 24:
        return 24 * 60 if minute == 0 else None
    if hour > 23:
        return None
    return hour * 60 + minute


def _extract_time_range(value: str) -> tuple[int, int] | None:
    match = re.search(r"(\d{1,2}:\d{2})\s*[~\-]\s*(\d{1,2}:\d{2})", value)
    if not match:
        return None
    start = _minutes_from_time_string(match.group(1))
    end = _minutes_from_time_string(match.group(2))
    if start is None or end is None:
        return None
    return start, end


def _is_in_time_range(current_minutes: int, time_range: tuple[int, int]) -> bool:
    start, end = time_range
    if end == start:
        return False
    if end < start:
        return current_minutes >= start or current_minutes < end
    return start <= current_minutes < end


def _is_explicitly_closed_for_day(value: str, weekday: int) -> bool:
    compact = value.strip().lower().replace(" ", "")
    if compact == "휴무":
        return True
    if "휴무" not in compact:
        return False
    if weekday == 6 and any(
        token in compact
        for token in ("일/공휴일휴무", "일휴무", "일요일휴무", "토/일휴무", "주말휴무")
    ):
        return True
    if weekday == 5 and any(
        token in compact for token in ("토휴무", "토요일휴무", "토/일휴무", "주말휴무")
    ):
        return True
    if weekday < 5 and any(
        token in compact for token in ("평일휴무", "주중휴무", "weekdayclosed")
    ):
        return True
    return False


def _find_day_specific_time_ranges(value: str, weekday: int) -> tuple[bool, list[tuple[int, int]]]:
    time_pattern = r"(\d{1,2}:\d{2}\s*[~\-]\s*\d{1,2}:\d{2})"
    patterns = [
        (
            (0, 1, 2, 3, 4),
            [
                rf"평일\s*{time_pattern}",
                rf"mon-fri\s*{time_pattern}",
                rf"weekday\s*{time_pattern}",
            ],
        ),
        (
            (5,),
            [
                rf"(?:토요일|토)\s*{time_pattern}",
                rf"sat\s*{time_pattern}",
            ],
        ),
        (
            (6,),
            [
                rf"(?:일요일|일)\s*{time_pattern}",
                rf"sun\s*{time_pattern}",
            ],
        ),
    ]
    found_any = False
    matches: list[tuple[int, int]] = []
    for days, options in patterns:
        for option in options:
            match = re.search(option, value, flags=re.IGNORECASE)
            if not match:
                continue
            found_any = True
            time_range = _extract_time_range(match.group(1))
            if time_range:
                start, end = time_range
                if end > start:
                    if weekday in days:
                        matches.append(time_range)
                else:
                    if weekday in days:
                        matches.append((start, 24 * 60))
                    spillover_days = {((day + 1) % 7) for day in days}
                    if weekday in spillover_days:
                        matches.append((0, end))
            break
    return found_any, matches


def _evaluate_open_now(hours_text: str, at: datetime) -> bool | None:
    if not hours_text.strip():
        return None

    compact = hours_text.strip().lower().replace(" ", "")
    if "24시간" in compact or "24hours" in compact:
        return True

    weekday = at.weekday()
    current_minutes = at.hour * 60 + at.minute

    if _is_explicitly_closed_for_day(hours_text, weekday):
        return False

    found_day_rules, day_ranges = _find_day_specific_time_ranges(hours_text, weekday)
    if day_ranges:
        return any(_is_in_time_range(current_minutes, item) for item in day_ranges)
    if found_day_rules:
        return False

    generic_range = _extract_time_range(hours_text)
    if generic_range:
        return _is_in_time_range(current_minutes, generic_range)
    if "휴무" in compact:
        return False
    return None


def _hours_cache_status(fetched_at: str, now: datetime) -> str:
    try:
        fetched = datetime.fromisoformat(fetched_at)
    except ValueError:
        return "expired"
    if fetched.tzinfo is None:
        fetched = fetched.astimezone()
    age_minutes = (now - fetched).total_seconds() / 60
    settings = get_settings()
    if age_minutes <= settings.restaurant_hours_cache_ttl_minutes:
        return "fresh"
    if age_minutes <= settings.restaurant_hours_cache_stale_ttl_minutes:
        return "stale"
    return "expired"


def _library_seat_cache_status(last_synced_at: str, now: datetime) -> str:
    try:
        synced_at = datetime.fromisoformat(last_synced_at)
    except ValueError:
        return "expired"
    if synced_at.tzinfo is None:
        synced_at = synced_at.astimezone()
    age_minutes = (now - synced_at).total_seconds() / 60
    settings = get_settings()
    if age_minutes <= settings.library_seat_cache_ttl_minutes:
        return "fresh"
    if age_minutes <= settings.library_seat_cache_stale_ttl_minutes:
        return "stale"
    return "expired"


def _filter_library_seat_rows(
    rows: list[dict[str, Any]],
    query: str | None,
) -> list[dict[str, Any]]:
    collapsed_query, compact_query = _normalized_query_variants(query)
    if collapsed_query is None:
        return rows

    compact_lower = (compact_query or collapsed_query).lower()
    matched_room_names = {
        canonical_name
        for canonical_name, aliases in LIBRARY_SEAT_ROOM_QUERY_ALIASES.items()
        if any(_compact_text(alias).lower() in compact_lower for alias in aliases)
    }
    if matched_room_names:
        return [item for item in rows if item.get("room_name") in matched_room_names]

    if any(_compact_text(cue).lower() in compact_lower for cue in LIBRARY_SEAT_GENERIC_QUERY_CUES):
        return rows

    filtered: list[dict[str, Any]] = []
    for item in rows:
        room_name = str(item.get("room_name") or "")
        if _matches_exact_text_candidate(
            room_name,
            collapsed_query=collapsed_query,
            compact_query=compact_query,
        ) or _matches_partial_text_candidate(
            room_name,
            collapsed_query=collapsed_query,
            compact_query=compact_query,
        ):
            filtered.append(item)
    return filtered


def _build_library_seat_status_response(
    rows: list[dict[str, Any]],
    *,
    availability_mode: str,
    checked_at: str,
    note: str | None,
    source_url: str | None,
) -> LibrarySeatStatusResponse:
    return LibrarySeatStatusResponse(
        availability_mode=availability_mode,
        checked_at=checked_at,
        note=note,
        source_url=source_url,
        rooms=[LibrarySeatStatus.model_validate(item) for item in rows],
    )


def _coerce_library_seat_status_source(
    source: LibrarySeatStatusSource | Any | None = None,
) -> LibrarySeatStatusSource | Any:
    if source is not None:
        return source
    try:
        return LibrarySeatStatusSource(LIBRARY_SEAT_STATUS_SOURCE_URL)
    except TypeError:
        return LibrarySeatStatusSource()


def refresh_library_seat_status_cache(
    conn: DBConnection,
    *,
    fetched_at: str | None = None,
    source: LibrarySeatStatusSource | Any | None = None,
) -> list[dict[str, Any]]:
    seat_source = _coerce_library_seat_status_source(source)
    checked_at = fetched_at or _now_iso()
    payload = seat_source.fetch()
    live_rows = seat_source.parse(payload, fetched_at=checked_at)
    if not live_rows:
        raise ValueError("library seat source returned no room rows")
    repo.replace_library_seat_status_cache(conn, live_rows)
    return live_rows


def _evaluate_open_now_from_map(opening_hours: dict[str, str], at: datetime) -> bool | None:
    if not opening_hours:
        return None
    day_keys = {
        0: "mon",
        1: "tue",
        2: "wed",
        3: "thu",
        4: "fri",
        5: "sat",
        6: "sun",
    }
    day_key = day_keys[at.weekday()]
    hours_text = opening_hours.get(day_key)
    if not hours_text and at.weekday() < 5:
        hours_text = opening_hours.get("weekday")
    if not hours_text:
        return None

    is_open = _evaluate_open_now(hours_text, at)
    if is_open is not True:
        return is_open

    break_text = opening_hours.get(f"{day_key}_break")
    if break_text and _evaluate_open_now(break_text, at):
        return False
    return True


def _restaurant_open_now(
    conn: DBConnection,
    restaurant_row: dict[str, Any],
    facility_hours: dict[str, str],
    at: datetime,
    *,
    kakao_place_detail_client: KakaoPlaceDetailClient | Any | None = None,
) -> bool | None:
    restaurant_name = str(restaurant_row.get("name") or "")
    hours_text = facility_hours.get(_normalize_facility_name(restaurant_name))
    if hours_text:
        return _evaluate_open_now(hours_text, at)

    if not _is_external_restaurant_route(restaurant_row.get("source_tag")):
        return None

    place_id = restaurant_row.get("kakao_place_id") or extract_kakao_place_id(
        str(restaurant_row.get("source_url") or "")
    )
    if not place_id:
        return None

    current = _now()
    cached = repo.get_restaurant_hours_cache(conn, kakao_place_id=place_id)
    cache_state = (
        _hours_cache_status(str(cached["fetched_at"]), current)
        if cached is not None
        else "expired"
    )
    if cached is not None and cache_state == "fresh":
        _record_hours_cache_decision(
            decision="restaurant_hours_fresh_hit",
            kakao_place_id=place_id,
            source_url=restaurant_row.get("source_url"),
        )
        return _evaluate_open_now_from_map(cached.get("opening_hours", {}), at)

    if kakao_place_detail_client is None:
        kakao_place_detail_client = KakaoPlaceDetailClient()

    try:
        payload = kakao_place_detail_client.fetch_sync(place_id)
        opening_hours = parse_place_detail_opening_hours(payload)
        repo.upsert_restaurant_hours_cache(
            conn,
            kakao_place_id=place_id,
            source_url=restaurant_row.get("source_url"),
            raw_payload=payload,
            opening_hours=opening_hours,
            fetched_at=_now_iso(),
        )
        _record_hours_cache_decision(
            decision="restaurant_hours_live_fetch_success",
            kakao_place_id=place_id,
            source_url=restaurant_row.get("source_url"),
        )
        return _evaluate_open_now_from_map(opening_hours, at)
    except (httpx.HTTPError, ValueError) as exc:
        _record_hours_cache_decision(
            decision="restaurant_hours_live_fetch_error",
            kakao_place_id=place_id,
            source_url=restaurant_row.get("source_url"),
            error_text=str(exc),
        )
        if cached is not None and cache_state == "stale":
            _record_hours_cache_decision(
                decision="restaurant_hours_stale_hit",
                kakao_place_id=place_id,
                source_url=restaurant_row.get("source_url"),
            )
            return _evaluate_open_now_from_map(cached.get("opening_hours", {}), at)
        return None


def _parse_campus_walk_graph(payload: dict[str, Any]) -> dict[str, Any]:
    nodes_raw = payload.get("nodes")
    edges_raw = payload.get("edges")
    if not isinstance(nodes_raw, list):
        raise ValueError("campus walk graph nodes must be a list")
    if not isinstance(edges_raw, list):
        raise ValueError("campus walk graph edges must be a list")

    nodes: list[str] = []
    for item in nodes_raw:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("campus walk graph nodes must be non-empty strings")
        slug = item.strip()
        if slug not in nodes:
            nodes.append(slug)

    adjacency: dict[str, list[tuple[str, int]]] = {slug: [] for slug in nodes}
    node_set = set(nodes)
    for edge in edges_raw:
        if not isinstance(edge, dict):
            raise ValueError("campus walk graph edges must be objects")
        start = str(edge.get("from", "")).strip()
        end = str(edge.get("to", "")).strip()
        if start not in node_set or end not in node_set:
            raise ValueError("campus walk graph edge references unknown node")
        walk_minutes = edge.get("walk_minutes")
        if not isinstance(walk_minutes, int) or isinstance(walk_minutes, bool) or walk_minutes <= 0:
            raise ValueError("campus walk graph edges must use positive walk_minutes")
        adjacency[start].append((end, walk_minutes))

    return {"nodes": frozenset(node_set), "adjacency": adjacency}


@lru_cache(maxsize=1)
def _load_campus_walk_graph() -> dict[str, Any]:
    payload = json.loads(CAMPUS_WALK_GRAPH_PATH.read_text(encoding="utf-8"))
    return _parse_campus_walk_graph(payload)


def _campus_walk_minutes(start_slug: str, end_slug: str) -> int | None:
    if start_slug == end_slug:
        return 0
    graph = _load_campus_walk_graph()
    nodes: frozenset[str] = graph["nodes"]
    if start_slug not in nodes or end_slug not in nodes:
        return None
    adjacency: dict[str, list[tuple[str, int]]] = graph["adjacency"]
    queue: list[tuple[int, str]] = [(0, start_slug)]
    seen: dict[str, int] = {start_slug: 0}
    while queue:
        cost, slug = heapq.heappop(queue)
        if slug == end_slug:
            return cost
        if cost > seen.get(slug, cost):
            continue
        for neighbor, weight in adjacency.get(slug, []):
            next_cost = cost + weight
            if next_cost >= seen.get(neighbor, next_cost + 1):
                continue
            seen[neighbor] = next_cost
            heapq.heappush(queue, (next_cost, neighbor))
    return None


def _direct_walk_minutes_from_coords(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> int:
    return max(1, round(_haversine_meters(lat1, lon1, lat2, lon2) / WALKING_METERS_PER_MINUTE))


def _campus_gate_places(conn: DBConnection) -> list[dict[str, Any]]:
    graph_nodes: frozenset[str] = _load_campus_walk_graph()["nodes"]
    return [
        place
        for place in repo.list_places(conn)
        if place["slug"] in graph_nodes
        and place["category"] == "gate"
        and place.get("latitude") is not None
        and place.get("longitude") is not None
    ]


def _is_external_restaurant_route(source_tag: str | None) -> bool:
    return (source_tag or "").startswith("kakao_local")


def _estimate_place_to_restaurant_walk_minutes(
    conn: DBConnection,
    *,
    origin_place: dict[str, Any],
    restaurant_row: dict[str, Any],
) -> int:
    direct_minutes = _direct_walk_minutes_from_coords(
        origin_place["latitude"],
        origin_place["longitude"],
        restaurant_row["latitude"],
        restaurant_row["longitude"],
    )
    if not _is_external_restaurant_route(restaurant_row.get("source_tag")):
        return direct_minutes

    best_minutes: int | None = None
    for gate in _campus_gate_places(conn):
        internal_minutes = _campus_walk_minutes(origin_place["slug"], gate["slug"])
        if internal_minutes is None:
            continue
        external_minutes = _direct_walk_minutes_from_coords(
            gate["latitude"],
            gate["longitude"],
            restaurant_row["latitude"],
            restaurant_row["longitude"],
        )
        total_minutes = internal_minutes + external_minutes
        if best_minutes is None or total_minutes < best_minutes:
            best_minutes = total_minutes
    return best_minutes or direct_minutes


def _estimate_restaurant_to_place_walk_minutes(
    conn: DBConnection,
    *,
    restaurant_latitude: float,
    restaurant_longitude: float,
    restaurant_source_tag: str | None,
    next_place: Place,
) -> int:
    direct_minutes = _direct_walk_minutes_from_coords(
        restaurant_latitude,
        restaurant_longitude,
        next_place.latitude,
        next_place.longitude,
    )
    if not _is_external_restaurant_route(restaurant_source_tag):
        return direct_minutes

    best_minutes: int | None = None
    for gate in _campus_gate_places(conn):
        internal_minutes = _campus_walk_minutes(gate["slug"], next_place.slug)
        if internal_minutes is None:
            continue
        external_minutes = _direct_walk_minutes_from_coords(
            restaurant_latitude,
            restaurant_longitude,
            gate["latitude"],
            gate["longitude"],
        )
        total_minutes = external_minutes + internal_minutes
        if best_minutes is None or total_minutes < best_minutes:
            best_minutes = total_minutes
    return best_minutes or direct_minutes


def _resolve_place_from_room(conn: DBConnection, room: str | None) -> Place | None:
    place_rows = repo.list_places(conn)
    return _resolve_place_from_room_with_maps(
        room,
        place_lookup=_build_place_slug_lookup(place_rows),
        place_candidates_lookup=_build_place_slug_candidates_lookup(place_rows),
        place_by_slug=_build_place_model_lookup(place_rows),
    )


def _resolve_place_from_room_with_maps(
    room: str | None,
    *,
    place_lookup: dict[str, str],
    place_candidates_lookup: dict[str, list[str]],
    place_by_slug: dict[str, Place],
) -> Place | None:
    if not room:
        return None
    candidates = [room]
    match = re.match(r"([A-Za-z]+)", room)
    if match:
        prefix = match.group(1).upper()
        candidates.extend([prefix, f"{prefix}관"])
    for candidate in candidates:
        preferred_slugs = set(_preferred_place_slugs_for_query(candidate, context="building"))
        if preferred_slugs:
            preferred_candidates = [
                slug
                for slug in place_candidates_lookup.get(_normalize_place_key(candidate), [])
                if slug in preferred_slugs
            ]
            if len(preferred_candidates) == 1:
                return place_by_slug.get(preferred_candidates[0])
        slug = place_lookup.get(_normalize_place_key(candidate))
        if slug:
            return place_by_slug.get(slug)
    return None


def _resolve_places_from_rooms(
    conn: DBConnection,
    rooms: set[str],
) -> dict[str, Place]:
    if not rooms:
        return {}
    place_rows = repo.list_places(conn)
    place_lookup = _build_place_slug_lookup(place_rows)
    place_candidates_lookup = _build_place_slug_candidates_lookup(place_rows)
    place_by_slug = _build_place_model_lookup(place_rows)
    resolved: dict[str, Place] = {}
    for room in sorted(rooms):
        place = _resolve_place_from_room_with_maps(
            room,
            place_lookup=place_lookup,
            place_candidates_lookup=place_candidates_lookup,
            place_by_slug=place_by_slug,
        )
        if place is not None:
            resolved[room] = place
    return resolved


def _ensure_profile(conn: DBConnection, profile_id: str) -> Profile:
    row = repo.get_profile(conn, profile_id)
    if not row:
        raise NotFoundError(f"Profile not found: {profile_id}")
    return Profile.model_validate(row)


def _dedupe_reasons(reasons: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for reason in reasons:
        if reason in seen:
            continue
        seen.add(reason)
        result.append(reason)
    return result


def _normalize_match_text(value: str) -> str:
    return "".join(char for char in value.lower() if not char.isspace())


def _validate_rules_keyword_map(
    payload: object,
    *,
    label: str,
    allow_empty_values: bool = True,
) -> dict[str, list[str]]:
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be an object")
    result: dict[str, list[str]] = {}
    for raw_key, raw_values in payload.items():
        key = str(raw_key).strip()
        if not key:
            raise ValueError(f"{label} keys must be non-empty strings")
        if not isinstance(raw_values, list):
            raise ValueError(f"{label}.{key} must be a list")
        values = _unique_stripped([str(item) for item in raw_values if str(item).strip()])
        if not values and not allow_empty_values:
            raise ValueError(f"{label}.{key} must include at least one keyword")
        result[key] = values
    return result


def _parse_personalization_rules(payload: dict[str, Any]) -> dict[str, Any]:
    departments = _validate_rules_keyword_map(
        payload.get("departments"),
        label="departments",
        allow_empty_values=False,
    )
    student_year_keywords_raw = _validate_rules_keyword_map(
        payload.get("student_year_keywords"),
        label="student_year_keywords",
        allow_empty_values=False,
    )
    student_year_keywords: dict[int, list[str]] = {}
    for raw_year, keywords in student_year_keywords_raw.items():
        if not raw_year.isdigit():
            raise ValueError("student_year_keywords keys must be integers")
        year = int(raw_year)
        if year < 1 or year > 6:
            raise ValueError("student_year_keywords keys must be between 1 and 6")
        student_year_keywords[year] = keywords

    admission_type_keywords = _validate_rules_keyword_map(
        payload.get("admission_type_keywords"),
        label="admission_type_keywords",
        allow_empty_values=True,
    )
    if set(admission_type_keywords) != ALLOWED_ADMISSION_TYPES:
        raise ValueError(
            "admission_type_keywords must define general, freshman, transfer, exchange"
        )

    interests = _validate_rules_keyword_map(
        payload.get("interests"),
        label="interests",
        allow_empty_values=False,
    )
    return {
        "departments": departments,
        "student_year_keywords": student_year_keywords,
        "admission_type_keywords": admission_type_keywords,
        "interests": interests,
    }


@lru_cache(maxsize=1)
def _load_personalization_rules() -> dict[str, Any]:
    payload = json.loads(PERSONALIZATION_RULES_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("personalization rules must be a JSON object")
    return _parse_personalization_rules(payload)


_DEFAULT_PERSONALIZATION_RULES = _load_personalization_rules()
STUDENT_YEAR_KEYWORDS = _DEFAULT_PERSONALIZATION_RULES["student_year_keywords"]
ADMISSION_TYPE_KEYWORDS = _DEFAULT_PERSONALIZATION_RULES["admission_type_keywords"]
INTEREST_KEYWORDS = _DEFAULT_PERSONALIZATION_RULES["interests"]
ALLOWED_PROFILE_INTERESTS = set(INTEREST_KEYWORDS)


def _department_aliases(department: str | None) -> list[str]:
    if not department:
        return []
    rules = _load_personalization_rules()
    normalized = _normalize_match_text(department)
    for canonical, aliases in rules["departments"].items():
        pool = [canonical, *aliases]
        if normalized in {_normalize_match_text(item) for item in pool}:
            return _unique_stripped(pool)
    return [department]


def _contains_keyword(text: str, keyword: str) -> bool:
    return _normalize_match_text(keyword) in _normalize_match_text(text)


def _profile_notice_context_is_empty(
    profile: Profile,
    preferences: ProfileNoticePreferences,
    interests: ProfileInterests,
) -> bool:
    return not any(
        [
            preferences.categories,
            preferences.keywords,
            profile.department,
            profile.student_year,
            profile.admission_type,
            interests.tags,
        ]
    )


def _notice_match_result(
    item: dict[str, Any],
    *,
    preferences: ProfileNoticePreferences,
    profile: Profile,
    interests: ProfileInterests,
) -> tuple[list[str], int]:
    reasons: list[str] = []
    score = 0
    category = _canonical_notice_category(item.get("category")) or ""
    labels = [
        canonical_label
        for label in item.get("labels", [])
        if (canonical_label := _canonical_notice_category(label)) is not None
    ]
    text = _joined_notice_text(item)

    category_matched = False
    for raw_category in preferences.categories:
        normalized = _canonical_notice_category(raw_category)
        if normalized is None:
            continue
        if normalized == category or normalized in labels:
            reasons.append(f"category:{normalized}")
            category_matched = True
    if category_matched:
        score += 4

    keyword_matched = False
    for keyword in preferences.keywords:
        if _contains_keyword(text, keyword):
            reasons.append(f"keyword:{keyword}")
            keyword_matched = True
    if keyword_matched:
        score += 3

    if profile.department and any(
        _contains_keyword(text, alias) for alias in _department_aliases(profile.department)
    ):
        reasons.append(f"department:{profile.department}")
        score += 3

    for keyword in _student_year_keywords(profile.student_year):
        if _contains_keyword(text, keyword):
            reasons.append(f"student_year:{profile.student_year}")
            score += 2
            break

    if profile.admission_type:
        for keyword in ADMISSION_TYPE_KEYWORDS[profile.admission_type]:
            if _contains_keyword(text, keyword):
                reasons.append(f"admission_type:{profile.admission_type}")
                score += 2
                break

    interest_matched = False
    for tag in interests.tags:
        if any(_contains_keyword(text, keyword) for keyword in INTEREST_KEYWORDS[tag]):
            reasons.append(f"interest:{tag}")
            interest_matched = True
    if interest_matched:
        score += 2

    return _dedupe_reasons(reasons), score


def _course_match_result(course: Course, *, profile: Profile) -> tuple[list[str], int]:
    reasons: list[str] = []
    score = 0
    text = _joined_course_text(course)
    if profile.department:
        aliases = _department_aliases(profile.department)
        in_department = any(_contains_keyword(course.department or "", alias) for alias in aliases)
        in_title = any(_contains_keyword(course.title, alias) for alias in aliases)
        if in_department or in_title:
            reasons.append(f"department:{profile.department}")
        if in_department:
            score += 5
        if in_title:
            score += 3
    for keyword in _student_year_keywords(profile.student_year):
        if _contains_keyword(text, keyword):
            reasons.append(f"student_year:{profile.student_year}")
            score += 2
            break
    return _dedupe_reasons(reasons), score


def get_class_periods() -> list[Period]:
    return [Period(period=period, start=start, end=end) for period, start, end in CLASS_PERIODS]


def get_notice_categories() -> list[NoticeCategoryInfo]:
    return [NoticeCategoryInfo.model_validate(item) for item in PUBLIC_NOTICE_CATEGORY_METADATA]


def get_library_seat_status(
    conn: DBConnection,
    query: str | None = None,
    *,
    source: LibrarySeatStatusSource | Any | None = None,
    now: datetime | None = None,
) -> LibrarySeatStatusResponse:
    current = now or _now()
    source = _coerce_library_seat_status_source(source)
    cached_rows = repo.list_library_seat_status_cache(conn)
    cache_state = (
        _library_seat_cache_status(str(cached_rows[0]["last_synced_at"]), current)
        if cached_rows
        else "expired"
    )
    if cached_rows and cache_state == "fresh":
        return _build_library_seat_status_response(
            _filter_library_seat_rows(cached_rows, query),
            availability_mode="live",
            checked_at=str(cached_rows[0]["last_synced_at"]),
            note=None,
            source_url=str(cached_rows[0].get("source_url") or LIBRARY_SEAT_STATUS_SOURCE_URL),
        )

    checked_at = current.isoformat(timespec="seconds")
    try:
        live_rows = refresh_library_seat_status_cache(
            conn,
            fetched_at=checked_at,
            source=source,
        )
        return _build_library_seat_status_response(
            _filter_library_seat_rows(live_rows, query),
            availability_mode="live",
            checked_at=checked_at,
            note=None,
            source_url=str(live_rows[0].get("source_url") or LIBRARY_SEAT_STATUS_SOURCE_URL),
        )
    except (httpx.HTTPError, ValueError):
        if cached_rows and cache_state == "stale":
            return _build_library_seat_status_response(
                _filter_library_seat_rows(cached_rows, query),
                availability_mode="stale_cache",
                checked_at=str(cached_rows[0]["last_synced_at"]),
                note="실시간 열람실 좌석 현황 조회에 실패해 최근 캐시를 대신 보여줍니다.",
                source_url=str(
                    cached_rows[0].get("source_url") or LIBRARY_SEAT_STATUS_SOURCE_URL
                ),
            )
        return _build_library_seat_status_response(
            [],
            availability_mode="unavailable",
            checked_at=checked_at,
            note="실시간 열람실 좌석 현황을 확인하지 못했습니다. 잠시 후 다시 시도해 주세요.",
            source_url=LIBRARY_SEAT_STATUS_SOURCE_URL,
        )


def search_campus_dining_menus(
    conn: DBConnection,
    query: str | None = None,
    *,
    limit: int = 10,
) -> list[CampusDiningMenu]:
    rows = repo.list_campus_dining_menus(conn, limit=max(limit, 10))
    normalized_query, compact_query, is_generic = _normalize_dining_menu_query(query)
    if is_generic or normalized_query is None:
        return [CampusDiningMenu.model_validate(item) for item in rows[:limit]]

    ranked: list[tuple[int, int, dict[str, Any]]] = []
    for index, item in enumerate(rows):
        rank = _rank_campus_dining_menu_candidate(
            item,
            collapsed_query=normalized_query,
            compact_query=compact_query,
        )
        if rank is None:
            continue
        ranked.append((rank, index, item))
    ranked.sort(key=lambda item: (item[0], item[1]))
    return [CampusDiningMenu.model_validate(item) for _, _, item in ranked[:limit]]


def search_places(
    conn: DBConnection,
    query: str = "",
    category: str | None = None,
    limit: int = 10,
) -> list[Place]:
    return place_search_runtime.search_places(
        conn,
        query=query,
        category=category,
        limit=limit,
    )


def search_courses(
    conn: DBConnection,
    query: str = "",
    *,
    year: int | None = None,
    semester: int | None = None,
    period_start: int | None = None,
    limit: int = 20,
) -> list[Course]:
    collapsed_query, compact_query = _normalized_query_variants(query)
    if collapsed_query is None:
        return [
            Course.model_validate(item)
            for item in repo.search_courses(
                conn,
                "",
                year=year,
                semester=semester,
                period_start=period_start,
                limit=limit,
            )
        ]

    queries = [collapsed_query or ""]
    if compact_query is not None and compact_query != queries[0]:
        queries.append(compact_query)

    ranked_items: list[tuple[int, int, int, str, str, str, int, dict[str, Any]]] = []
    seen_ids: set[int] = set()
    order_index = 0
    for candidate_query in queries:
        for item in repo.search_courses(
            conn,
            candidate_query,
            year=year,
            semester=semester,
            period_start=period_start,
            limit=None,
        ):
            item_id = int(item["id"])
            if item_id in seen_ids:
                continue
            seen_ids.add(item_id)
            rank = _rank_course_search_candidate(
                item,
                collapsed_query=collapsed_query,
                compact_query=compact_query,
            )
            if rank is None:
                continue
            ranked_items.append(
                (
                    rank,
                    -int(item.get("year") or 0),
                    -int(item.get("semester") or 0),
                    _collapse_whitespace(str(item.get("title") or "")).lower(),
                    str(item.get("code") or "").lower(),
                    str(item.get("section") or "").lower(),
                    order_index,
                    item,
                )
            )
            order_index += 1
    ranked_items.sort(key=lambda item: item[:-1])
    return [Course.model_validate(item[-1]) for item in ranked_items[:limit]]


def search_restaurants(
    conn: DBConnection,
    query: str = "",
    *,
    origin: str | None = None,
    category: str | None = None,
    limit: int = 10,
    kakao_client: KakaoLocalClient | Any | None = None,
) -> list[RestaurantSearchResult]:
    restaurants = repo.list_restaurants(conn)
    if category is not None:
        restaurants = [item for item in restaurants if item["category"] == category]

    origin_place: dict[str, Any] | None = None
    if origin is not None:
        origin_place = _resolve_origin_place(conn, origin)
        if origin_place.get("latitude") is None or origin_place.get("longitude") is None:
            raise NotFoundError(f"Origin place has no coordinates: {origin}")

    collapsed_query, compact_query = _normalized_query_variants(query)
    canonical_brand_query = (
        _resolve_restaurant_brand_query_token(query)
        if collapsed_query is not None
        else None
    )
    ranking_origin_place = origin_place or _default_restaurant_search_origin(
        conn,
        collapsed_query=collapsed_query,
    )
    snapshot_results = _rank_restaurant_search_results(
        conn,
        restaurants,
        collapsed_query=collapsed_query,
        compact_query=compact_query,
        canonical_brand_query=canonical_brand_query,
        ranking_origin_place=ranking_origin_place,
        origin_place=origin_place,
        limit=limit,
    )
    if snapshot_results or collapsed_query is None:
        return snapshot_results

    internal_origin_place = ranking_origin_place
    if internal_origin_place is None:
        internal_origin_place = _resolve_origin_place(conn, DEFAULT_RESTAURANT_SEARCH_ORIGIN)
        if (
            internal_origin_place.get("latitude") is None
            or internal_origin_place.get("longitude") is None
        ):
            raise NotFoundError(
                f"Origin place has no coordinates: {DEFAULT_RESTAURANT_SEARCH_ORIGIN}"
            )

    canonical_query = _resolve_restaurant_brand_query_token(query)
    settings = get_settings()
    if kakao_client is None and settings.kakao_rest_api_key:
        kakao_client = KakaoLocalClient(settings.kakao_rest_api_key)

    for radius_meters in (
        DEFAULT_RESTAURANT_SEARCH_RADIUS_METERS,
        EXTENDED_RESTAURANT_SEARCH_RADIUS_METERS,
    ):
        origin_slug, cache_query, _ = _restaurant_brand_cache_key(
            internal_origin_place["slug"],
            canonical_query,
            radius_meters,
        )
        snapshot, cached_rows = _cache_rows_for_key(
            conn,
            origin_slug=origin_slug,
            kakao_query=cache_query,
            radius_meters=radius_meters,
            latitude=internal_origin_place["latitude"],
            longitude=internal_origin_place["longitude"],
        )
        cache_state = (
            _cache_status(snapshot["fetched_at"], _now())
            if snapshot is not None
            else "expired"
        )

        raw_restaurants: list[dict[str, Any]]
        if snapshot is not None and cache_state in {"fresh", "stale"}:
            raw_restaurants = cached_rows
        elif kakao_client is not None:
            try:
                raw_restaurants = _live_restaurant_rows(
                    place=internal_origin_place,
                    kakao_query=canonical_query,
                    radius_meters=radius_meters,
                    kakao_client=kakao_client,
                )
                repo.replace_restaurant_cache_snapshot(
                    conn,
                    origin_slug=origin_slug,
                    kakao_query=cache_query,
                    radius_meters=radius_meters,
                    fetched_at=(
                        raw_restaurants[0]["last_synced_at"]
                        if raw_restaurants
                        else _now_iso()
                    ),
                    rows=_cached_kakao_restaurant_rows(raw_restaurants),
                )
            except httpx.HTTPError:
                raw_restaurants = []
        else:
            raw_restaurants = []

        if category is not None:
            raw_restaurants = [item for item in raw_restaurants if item["category"] == category]

        results = _rank_restaurant_search_results(
            conn,
            raw_restaurants,
            collapsed_query=collapsed_query,
            compact_query=compact_query,
            canonical_brand_query=canonical_brand_query,
            ranking_origin_place=internal_origin_place,
            origin_place=origin_place,
            limit=limit,
        )
        if results:
            return results

    return []


def _collect_course_snapshot_rows(
    source: CourseCatalogSource | Any,
    *,
    year: int,
    semester: int,
    fetched_at: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_course_keys: set[tuple[Any, ...]] = set()

    for page_index in range(50):
        offset = page_index * 50
        html = source.fetch(
            year=year,
            semester=semester,
            department="ALL",
            completion_type="ALL",
            query="",
            offset=offset,
        )
        page_rows = source.parse(html, fetched_at=fetched_at)
        if not page_rows:
            break
        for row in page_rows:
            course_key = (
                row.get("code"),
                row.get("section"),
                row.get("raw_schedule"),
                row.get("professor"),
                row.get("title"),
            )
            if course_key in seen_course_keys:
                continue
            seen_course_keys.add(course_key)
            rows.append(row)
        if len(page_rows) < 50:
            break
    return rows


def _course_query_candidates(query: str) -> list[str]:
    collapsed_query, compact_query = _normalized_query_variants(query)
    queries = [collapsed_query or ""]
    if compact_query is not None and compact_query != queries[0]:
        queries.append(compact_query)
    return queries


def _course_row_matches_queries(row: dict[str, Any], queries: list[str]) -> bool:
    text_fields = [
        _normalize_optional_text(row.get("title")),
        _normalize_optional_text(row.get("code")),
        _normalize_optional_text(row.get("professor")),
    ]
    lowered_fields = [field.lower() for field in text_fields if field]
    compacted_fields = [_compact_text(field).lower() for field in text_fields if field]

    for query in queries:
        lowered_query = query.lower()
        compacted_query = _compact_text(query).lower()
        if any(lowered_query in field for field in lowered_fields):
            return True
        if compacted_query and any(compacted_query in field for field in compacted_fields):
            return True
    return False


def _course_match_preview(
    rows: list[dict[str, Any]],
    *,
    limit: int = 5,
) -> list[dict[str, str | None]]:
    return [
        {
            "code": row.get("code"),
            "title": row.get("title"),
            "professor": row.get("professor"),
            "department": row.get("department"),
            "section": row.get("section"),
        }
        for row in rows[:limit]
    ]


def investigate_course_query_coverage(
    conn: DBConnection,
    *,
    queries: list[str],
    source: CourseCatalogSource | Any | None = None,
    year: int | None = None,
    semester: int | None = None,
    fetched_at: str | None = None,
    search_limit: int = 20,
) -> list[dict[str, Any]]:
    source = source or CourseCatalogSource(COURSE_SOURCE_URL)
    synced_at = fetched_at or _now_iso()
    resolved_year, resolved_semester = _current_year_and_semester()
    resolved_year = year or resolved_year
    resolved_semester = semester or resolved_semester

    source_rows = _collect_course_snapshot_rows(
        source,
        year=resolved_year,
        semester=resolved_semester,
        fetched_at=synced_at,
    )
    db_rows = repo.list_courses_snapshot(
        conn,
        year=resolved_year,
        semester=resolved_semester,
    )

    reports: list[dict[str, Any]] = []
    for query in queries:
        candidate_queries = _course_query_candidates(query)
        source_matches = [
            row for row in source_rows if _course_row_matches_queries(row, candidate_queries)
        ]
        db_direct_matches = [
            row for row in db_rows if _course_row_matches_queries(row, candidate_queries)
        ]
        search_matches = search_courses(
            conn,
            query=query,
            year=resolved_year,
            semester=resolved_semester,
            limit=search_limit,
        )

        if search_matches:
            status = "covered"
        elif db_direct_matches:
            status = "search_gap"
        elif source_matches:
            status = "db_gap"
        else:
            status = "source_gap"

        reports.append(
            {
                "query": query,
                "year": resolved_year,
                "semester": resolved_semester,
                "status": status,
                "source_match_count": len(source_matches),
                "db_match_count": len(db_direct_matches),
                "search_match_count": len(search_matches),
                "source_matches": _course_match_preview(source_matches),
                "db_matches": _course_match_preview(db_direct_matches),
                "search_matches": [
                    {
                        "code": course.code,
                        "title": course.title,
                        "professor": course.professor,
                        "department": course.department,
                        "section": course.section,
                    }
                    for course in search_matches[:5]
                ],
            }
        )
    return reports


def list_latest_notices(
    conn: DBConnection,
    category: str | None = None,
    limit: int = 10,
) -> list[Notice]:
    categories = _normalize_notice_category_filter(category)
    return [
        Notice.model_validate(
            {
                **item,
                "category": _normalize_notice_public_category(item.get("category")),
            }
        )
        for item in repo.list_notices(conn, category=categories, limit=limit)
    ]


def list_certificate_guides(
    conn: DBConnection,
    limit: int = 20,
) -> list[CertificateGuide]:
    return [
        CertificateGuide.model_validate(item)
        for item in repo.list_certificate_guides(conn, limit=limit)
    ]


def list_leave_of_absence_guides(
    conn: DBConnection,
    limit: int = 20,
) -> list[LeaveOfAbsenceGuide]:
    normalized_limit = max(1, min(limit, 50))
    return [
        LeaveOfAbsenceGuide.model_validate(item)
        for item in repo.list_leave_of_absence_guides(conn, limit=normalized_limit)
    ]


def list_scholarship_guides(
    conn: DBConnection,
    limit: int = 20,
) -> list[ScholarshipGuide]:
    normalized_limit = max(1, min(limit, 50))
    return [
        ScholarshipGuide.model_validate(item)
        for item in repo.list_scholarship_guides(conn, limit=normalized_limit)
    ]


def list_wifi_guides(
    conn: DBConnection,
    limit: int = 20,
) -> list[WifiGuide]:
    normalized_limit = max(1, min(limit, 50))
    return [
        WifiGuide.model_validate(item)
        for item in repo.list_wifi_guides(conn, limit=normalized_limit)
    ]


def list_academic_support_guides(
    conn: DBConnection,
    limit: int = 20,
) -> list[AcademicSupportGuide]:
    normalized_limit = max(1, min(limit, 50))
    return [
        AcademicSupportGuide.model_validate(item)
        for item in repo.list_academic_support_guides(conn, limit=normalized_limit)
    ]


def list_academic_status_guides(
    conn: DBConnection,
    *,
    status: str | None = None,
    limit: int = 20,
) -> list[AcademicStatusGuide]:
    normalized_limit = max(1, min(limit, 50))
    normalized_status = status.strip() if status else None
    if normalized_status and normalized_status not in ACADEMIC_STATUS_GUIDE_VALUES:
        raise InvalidRequestError(
            "status must be one of return_from_leave, dropout, re_admission."
        )
    return [
        AcademicStatusGuide.model_validate(item)
        for item in repo.list_academic_status_guides(
            conn,
            status=normalized_status,
            limit=normalized_limit,
        )
    ]


def list_registration_guides(
    conn: DBConnection,
    *,
    topic: str | None = None,
    limit: int = 20,
) -> list[RegistrationGuide]:
    normalized_limit = max(1, min(limit, 50))
    normalized_topic = topic.strip() if topic else None
    if normalized_topic and normalized_topic not in REGISTRATION_GUIDE_TOPICS:
        raise InvalidRequestError(
            "topic must be one of bill_lookup, payment_and_return, payment_by_student."
        )
    return [
        RegistrationGuide.model_validate(item)
        for item in repo.list_registration_guides(
            conn,
            topic=normalized_topic,
            limit=normalized_limit,
        )
    ]


def list_academic_calendar(
    conn: DBConnection,
    *,
    academic_year: int | None = None,
    month: int | None = None,
    query: str | None = None,
    limit: int = 20,
) -> list[AcademicCalendarEvent]:
    resolved_year = academic_year or _current_academic_year()
    normalized_query = (query or "").strip() or None
    normalized_limit = max(1, min(limit, 50))
    start_date = None
    end_date = None
    if month is not None:
        start_date, end_date = _academic_month_bounds(resolved_year, month)

    events = [
        AcademicCalendarEvent.model_validate(item)
        for item in repo.list_academic_calendar(
            conn,
            academic_year=resolved_year,
            start_date=start_date,
            end_date=end_date,
            query=normalized_query,
        )
    ]
    events.sort(key=_academic_calendar_priority)
    return events[:normalized_limit]


def list_transport_guides(
    conn: DBConnection,
    mode: str | None = None,
    query: str | None = None,
    limit: int = 20,
) -> list[TransportGuide]:
    normalized_mode = _normalize_transport_mode(mode)
    inferred_mode = normalized_mode or _infer_transport_mode_from_query(query)
    if inferred_mode == "unsupported":
        return []

    guides = [
        TransportGuide.model_validate(item)
        for item in repo.list_transport_guides(conn, mode=inferred_mode, limit=limit)
    ]
    if query is None:
        return guides

    return _rank_transport_guides(guides, query=query, limit=limit)


def list_sync_runs(conn: DBConnection, limit: int = 20) -> list[SyncRun]:
    return [SyncRun.model_validate(item) for item in repo.list_sync_runs(conn, limit=limit)]


def get_sync_dashboard_state(
    conn: DBConnection,
    *,
    runs_limit: int = 20,
) -> dict[str, Any]:
    settings = get_settings()
    dataset_states, _ = ops_runtime.collect_dataset_sync_states(
        conn,
        tables=SYNC_DATASET_TABLES,
        public_readonly=settings.app_mode == "public_readonly",
        dataset_policies=PUBLIC_READY_DATASET_POLICIES,
        capture_errors=False,
    )
    return {
        "datasets": ops_runtime.observability_dataset_payloads(dataset_states),
        "recent_runs": list_sync_runs(conn, limit=runs_limit),
        "automation": get_automation_status(conn),
    }


def _sync_run_params(
    *,
    target: str,
    campus: str | None,
    year: int | None,
    semester: int | None,
    notice_pages: int | None,
) -> dict[str, int | str]:
    params: dict[str, int | str] = {}
    if target in {"snapshot", "places"} and campus:
        params["campus"] = campus
    if target in {"snapshot", "courses"} and year is not None:
        params["year"] = year
    if target in {"snapshot", "courses"} and semester is not None:
        params["semester"] = semester
    if target in {"snapshot", "notices"} and notice_pages is not None:
        params["notice_pages"] = notice_pages
    return params


def _run_admin_sync_target(
    conn: DBConnection,
    *,
    target: str,
    campus: str | None,
    year: int | None,
    semester: int | None,
    notice_pages: int | None,
) -> dict[str, int]:
    settings = get_settings()
    if target == "snapshot":
        return sync_official_snapshot(
            conn,
            campus=campus,
            year=year,
            semester=semester,
            notice_pages=notice_pages,
        )
    if target == "places":
        return {
            "places": len(
                refresh_places_from_campus_map(
                    conn,
                    campus=campus or settings.official_campus_id,
                )
            )
        }
    if target == "campus_facilities":
        return {"campus_facilities": len(refresh_campus_facilities_from_source(conn))}
    if target == "library_hours":
        return {"updated_places": len(refresh_library_hours_from_library_page(conn))}
    if target in {"library_seat_status", "library_seat_prewarm"}:
        return {"library_seat_status": len(refresh_library_seat_status_cache(conn))}
    if target == "facility_hours":
        return {"updated_places": len(refresh_facility_hours_from_facilities_page(conn))}
    if target == "dining_menus":
        return {"dining_menus": len(refresh_campus_dining_menus_from_facilities_page(conn))}
    if target == "courses":
        return {
            "courses": len(
                refresh_courses_from_subject_search(
                    conn,
                    year=year,
                    semester=semester,
                )
            )
        }
    if target == "notices":
        return {
            "notices": len(
                refresh_notices_from_notice_board(
                    conn,
                    pages=notice_pages or settings.official_notice_pages,
                )
            )
        }
    if target == "academic_calendar":
        return {"academic_calendar": len(refresh_academic_calendar_from_source(conn))}
    if target == "leave_of_absence_guides":
        return {"leave_of_absence_guides": len(refresh_leave_of_absence_guides_from_source(conn))}
    if target == "academic_status_guides":
        return {"academic_status_guides": len(refresh_academic_status_guides_from_source(conn))}
    if target == "registration_guides":
        return {"registration_guides": len(refresh_registration_guides_from_source(conn))}
    if target == "scholarship_guides":
        return {"scholarship_guides": len(refresh_scholarship_guides_from_source(conn))}
    if target == "wifi_guides":
        return {"wifi_guides": len(refresh_wifi_guides_from_source(conn))}
    if target == "transport_guides":
        return {"transport_guides": len(refresh_transport_guides_from_location_page(conn))}
    if target == "academic_support_guides":
        return {
            "academic_support_guides": len(refresh_academic_support_guides_from_source(conn))
        }
    if target == "cache_cleanup":
        return cleanup_stale_restaurant_caches(conn)
    raise InvalidRequestError(f"Unsupported admin sync target: {target}")


def run_admin_sync(
    *,
    target: str = "snapshot",
    trigger: str = "manual",
    campus: str | None = None,
    year: int | None = None,
    semester: int | None = None,
    notice_pages: int | None = None,
) -> SyncRun:
    if target not in SYNC_RUN_TARGETS:
        raise InvalidRequestError(f"Unsupported admin sync target: {target}")

    params = _sync_run_params(
        target=target,
        campus=campus,
        year=year,
        semester=semester,
        notice_pages=notice_pages,
    )
    started_at = _now_iso()
    run_conn = get_connection()
    try:
        run_id = repo.create_sync_run(
            run_conn,
            target=target,
            status="running",
            trigger=trigger,
            params=params,
            summary={},
            error_text=None,
            started_at=started_at,
            finished_at=None,
        )
        run_conn.commit()
    finally:
        run_conn.close()

    summary: dict[str, int] = {}
    error_text: str | None = None
    status = "success"
    sync_conn = get_connection()
    try:
        summary = _run_admin_sync_target(
            sync_conn,
            target=target,
            campus=campus,
            year=year,
            semester=semester,
            notice_pages=notice_pages,
        )
        sync_conn.commit()
    except Exception as exc:
        sync_conn.rollback()
        status = "failed"
        error_text = str(exc)
        summary = {}
    finally:
        sync_conn.close()

    finished_at = _now_iso()
    update_conn = get_connection()
    try:
        repo.update_sync_run(
            update_conn,
            run_id,
            status=status,
            summary=summary,
            error_text=error_text,
            finished_at=finished_at,
        )
        update_conn.commit()
        row = repo.get_sync_run(update_conn, run_id)
    finally:
        update_conn.close()

    if not row:
        raise RuntimeError(f"Sync run not found after update: {run_id}")
    _record_sync_result(
        target=target,
        trigger=trigger,
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        summary=summary,
        error_text=error_text,
    )
    return SyncRun.model_validate(row)


def cleanup_stale_restaurant_caches(
    conn: DBConnection,
    *,
    now: datetime | None = None,
) -> dict[str, int]:
    settings = get_settings()
    current = _coerce_datetime(now)
    restaurant_cache_cutoff = (
        current - timedelta(minutes=settings.restaurant_cache_stale_ttl_minutes)
    ).isoformat(timespec="seconds")
    restaurant_hours_cutoff = (
        current - timedelta(minutes=settings.restaurant_hours_cache_stale_ttl_minutes)
    ).isoformat(timespec="seconds")
    summary = repo.delete_stale_restaurant_cache_snapshots(
        conn,
        older_than=restaurant_cache_cutoff,
    )
    summary["restaurant_hours_cache_deleted"] = repo.delete_stale_restaurant_hours_cache(
        conn,
        older_than=restaurant_hours_cutoff,
    )
    return summary


def run_automation_tick(
    *,
    job_names: set[str] | None = None,
    now: datetime | None = None,
) -> list[SyncRun]:
    settings = get_settings()
    if not settings.automation_enabled:
        logger.info("event=automation_tick_skipped reason=disabled")
        return []

    selected = job_names or AUTOMATION_SYNC_TARGETS
    unknown = set(selected) - AUTOMATION_SYNC_TARGETS
    if unknown:
        raise InvalidRequestError(f"Unsupported automation job(s): {', '.join(sorted(unknown))}")

    lock_conn = None
    acquired_leader = False
    if not bool(_OBSERVABILITY_STATE["automation"]["leader"]):
        lock_conn = get_connection()
        try:
            if not try_acquire_automation_leader(lock_conn):
                set_automation_leader(False)
                logger.info("event=automation_tick_skipped reason=not_leader")
                lock_conn.close()
                return []
            acquired_leader = True
        except Exception:
            lock_conn.close()
            raise

    current = _coerce_datetime(now)
    due_targets: list[str] = []
    try:
        with connection() as conn:
            for target in ("snapshot", "library_seat_prewarm", "cache_cleanup"):
                if target not in selected:
                    continue
                if _is_automation_job_due(conn, target=target, now=current):
                    due_targets.append(target)

        runs: list[SyncRun] = []
        for target in due_targets:
            runs.append(run_admin_sync(target=target, trigger="automation"))
        return runs
    finally:
        if acquired_leader and lock_conn is not None:
            try:
                release_automation_leader(lock_conn)
            finally:
                set_automation_leader(False)
                lock_conn.close()


def create_profile(conn: DBConnection, display_name: str = "") -> Profile:
    created_at = _now_iso()
    profile_id = uuid.uuid4().hex
    repo.create_profile(
        conn,
        profile_id=profile_id,
        display_name=_normalize_profile_display_name(display_name),
        created_at=created_at,
        updated_at=created_at,
    )
    return _ensure_profile(conn, profile_id)


def update_profile(
    conn: DBConnection,
    profile_id: str,
    payload: ProfileUpdateRequest,
) -> Profile:
    _ensure_profile(conn, profile_id)
    fields = set(payload.model_fields_set)
    if not fields:
        return _ensure_profile(conn, profile_id)
    repo.update_profile(
        conn,
        profile_id,
        display_name=_normalize_profile_display_name(payload.display_name),
        department=_normalize_optional_text(payload.department),
        student_year=_validate_student_year(payload.student_year),
        admission_type=_validate_admission_type(payload.admission_type),
        updated_at=_now_iso(),
        fields=fields,
    )
    return _ensure_profile(conn, profile_id)


def set_profile_timetable(
    conn: DBConnection,
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
    conn: DBConnection,
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
    conn: DBConnection,
    profile_id: str,
    preferences: ProfileNoticePreferences,
) -> ProfileNoticePreferences:
    _ensure_profile(conn, profile_id)
    categories = _normalize_notice_preference_categories(preferences.categories)
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


def set_profile_interests(
    conn: DBConnection,
    profile_id: str,
    interests: ProfileInterests,
) -> ProfileInterests:
    _ensure_profile(conn, profile_id)
    tags = _normalize_interest_tags(interests.tags)
    repo.save_profile_interests(
        conn,
        profile_id,
        tags=tags,
        updated_at=_now_iso(),
    )
    return ProfileInterests(tags=tags)


def get_profile_interests(conn: DBConnection, profile_id: str) -> ProfileInterests:
    _ensure_profile(conn, profile_id)
    row = repo.get_profile_interests(conn, profile_id)
    return ProfileInterests(tags=(row["tags"] if row else []))


def list_profile_notices(
    conn: DBConnection,
    profile_id: str,
    *,
    limit: int = 10,
) -> list[MatchedNotice]:
    profile = _ensure_profile(conn, profile_id)
    loaded_preferences = ProfileNoticePreferences.model_validate(
        repo.get_profile_notice_preferences(conn, profile_id)
        or {"categories": [], "keywords": []}
    )
    preferences = ProfileNoticePreferences(
        categories=_normalize_notice_preference_categories(loaded_preferences.categories),
        keywords=loaded_preferences.keywords,
    )
    interests = get_profile_interests(conn, profile_id)
    if _profile_notice_context_is_empty(profile, preferences, interests):
        raise InvalidRequestError("Profile has no personalization context.")

    matched: list[tuple[int, MatchedNotice]] = []
    for item in repo.list_notices(conn, limit=max(limit * 20, 200)):
        reasons, score = _notice_match_result(
            item,
            preferences=preferences,
            profile=profile,
            interests=interests,
        )
        if reasons and score > 0:
            matched.append(
                (
                    score,
                    MatchedNotice(
                        notice=Notice.model_validate(
                            {
                                **item,
                                "category": _canonical_notice_category(item.get("category"))
                                or "general",
                            }
                        ),
                        matched_reasons=reasons,
                    ),
                )
            )
    return _sort_matched_notices(matched)[:limit]


def get_profile_course_recommendations(
    conn: DBConnection,
    profile_id: str,
    *,
    year: int | None = None,
    semester: int | None = None,
    query: str = "",
    limit: int = 10,
) -> list[MatchedCourse]:
    profile = _ensure_profile(conn, profile_id)
    if not profile.department and profile.student_year is None:
        raise InvalidRequestError("Profile has no course recommendation context.")

    resolved_year, resolved_semester = _current_year_and_semester()
    selected_year = year or resolved_year
    selected_semester = semester or resolved_semester
    excluded_codes = {
        item["code"]
        for item in repo.list_profile_courses(
            conn,
            profile_id,
            year=selected_year,
            semester=selected_semester,
        )
    }
    grouped: dict[str, tuple[int, MatchedCourse]] = {}
    for item in repo.search_courses(
        conn,
        query=query,
        year=selected_year,
        semester=selected_semester,
        limit=max(limit * 20, 500),
    ):
        course = Course.model_validate(item)
        if course.code in excluded_codes:
            continue
        reasons, score = _course_match_result(course, profile=profile)
        if not reasons or score <= 0:
            continue
        current = grouped.get(course.code)
        candidate = (score, MatchedCourse(course=course, matched_reasons=reasons))
        if current is None:
            grouped[course.code] = candidate
            continue
        current_score, current_item = current
        current_section = current_item.course.section or ""
        candidate_section = course.section or ""
        if (
            score > current_score
            or (
                score == current_score
                and (candidate_section, course.title, course.code)
                < (current_section, current_item.course.title, current_item.course.code)
            )
        ):
            grouped[course.code] = candidate

    matched = sorted(
        grouped.values(),
        key=lambda item: (-item[0], item[1].course.title, item[1].course.code),
    )
    return [item for _, item in matched[:limit]]


def get_profile_meal_recommendations(
    conn: DBConnection,
    profile_id: str,
    *,
    origin: str,
    at: datetime | None = None,
    year: int | None = None,
    semester: int | None = None,
    budget_max: int | None = None,
    category: str | None = None,
    limit: int = 10,
    open_now: bool = False,
    kakao_place_detail_client: KakaoPlaceDetailClient | Any | None = None,
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
        at=current,
        open_now=open_now,
        kakao_place_detail_client=kakao_place_detail_client,
    )

    items: list[MealRecommendation] = []
    for restaurant in nearby:
        total_walk_minutes = restaurant.estimated_walk_minutes
        if (
            next_place is not None
            and next_place.latitude is not None
            and next_place.longitude is not None
        ):
            second_leg = _estimate_restaurant_to_place_walk_minutes(
                conn,
                restaurant_latitude=restaurant.latitude,
                restaurant_longitude=restaurant.longitude,
                restaurant_source_tag=restaurant.source_tag,
                next_place=next_place,
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
        reason=(
            "No currently open restaurants matched the filters."
            if open_now and not items
            else None
        ),
    )


def list_estimated_empty_classrooms(
    conn: DBConnection,
    *,
    building: str,
    at: datetime | None = None,
    year: int | None = None,
    semester: int | None = None,
    limit: int = 10,
) -> EstimatedEmptyClassroomResponse:
    current = _coerce_datetime(at)
    resolved_year, resolved_semester = _current_year_and_semester(current)
    target_building = _resolve_building_place(conn, building)
    effective_year = year or resolved_year
    effective_semester = semester or resolved_semester
    course_rows = repo.list_courses_with_rooms(
        conn,
        year=effective_year,
        semester=effective_semester,
    )
    rooms = {
        str(row["room"]).strip()
        for row in course_rows
        if row.get("room") is not None and str(row["room"]).strip()
    }
    room_places = _resolve_places_from_rooms(conn, rooms)
    matching_rooms = {
        room
        for room, place in room_places.items()
        if place.slug == target_building.slug
    }
    by_room: dict[str, list[Course]] = {}
    for row in course_rows:
        room = str(row.get("room") or "").strip()
        if not room or room not in matching_rooms:
            continue
        course = Course.model_validate(row)
        by_room.setdefault(room, []).append(course)

    room_states = _build_empty_classroom_room_states(by_room, current=current)
    realtime_source = _get_official_classroom_availability_source()
    realtime_failed = False
    realtime_rows: dict[str, dict[str, Any]] = {}
    if realtime_source is not None:
        try:
            realtime_rows = _normalize_official_classroom_availability(
                realtime_source.fetch_availability(
                    building=target_building,
                    at=current,
                    year=effective_year,
                    semester=effective_semester,
                )
            )
        except Exception:
            realtime_failed = True
            logger.warning(
                "official classroom availability source failed",
                exc_info=True,
                extra={
                    "building": target_building.slug,
                    "year": effective_year,
                    "semester": effective_semester,
                },
            )

    items: list[EstimatedEmptyClassroom] = []
    if realtime_rows:
        for room_key in sorted(set(room_states) | set(realtime_rows)):
            realtime_row = realtime_rows.get(room_key)
            room_state = room_states.get(room_key)
            if realtime_row is not None:
                if not realtime_row["available_now"]:
                    continue
                items.append(
                    EstimatedEmptyClassroom(
                        room=str(realtime_row["room"]),
                        available_now=True,
                        availability_mode="realtime",
                        source_observed_at=realtime_row["source_observed_at"],
                        next_occupied_at=(
                            room_state["next_occupied_at"] if room_state is not None else None
                        ),
                        next_course_summary=(
                            room_state["next_course_summary"] if room_state is not None else None
                        ),
                    )
                )
                continue
            if room_state is not None and room_state["estimated_available_now"]:
                items.append(
                    EstimatedEmptyClassroom(
                        room=room_state["room"],
                        available_now=True,
                        availability_mode="estimated",
                        source_observed_at=None,
                        next_occupied_at=room_state["next_occupied_at"],
                        next_course_summary=room_state["next_course_summary"],
                    )
                )
    else:
        for room_state in room_states.values():
            if not room_state["estimated_available_now"]:
                continue
            items.append(
                EstimatedEmptyClassroom(
                    room=room_state["room"],
                    available_now=True,
                    availability_mode="estimated",
                    source_observed_at=None,
                    next_occupied_at=room_state["next_occupied_at"],
                    next_course_summary=room_state["next_course_summary"],
                )
            )

    items = _sort_empty_classroom_items(items)
    used_realtime = bool(realtime_rows)
    used_estimated = (
        bool(room_states)
        and (
            realtime_failed
            or not realtime_rows
            or any(room_key not in realtime_rows for room_key in room_states)
        )
    )
    observed_at_values = [
        row["source_observed_at"]
        for row in realtime_rows.values()
        if row.get("source_observed_at") is not None
    ]
    estimate_note = _build_classroom_availability_note(
        room_states=room_states,
        items=items,
        used_realtime=used_realtime,
        used_estimated=used_estimated,
        realtime_failed=realtime_failed,
    )
    return EstimatedEmptyClassroomResponse(
        building=_serialize_empty_classroom_building(target_building),
        evaluated_at=current.isoformat(timespec="seconds"),
        year=effective_year,
        semester=effective_semester,
        availability_mode=_response_availability_mode(
            used_realtime=used_realtime,
            used_estimated=used_estimated,
        ),
        observed_at=max(observed_at_values) if observed_at_values else None,
        estimate_note=estimate_note,
        items=items[:limit],
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
        "kakao_place_id": place.place_id or extract_kakao_place_id(place.place_url),
        "source_url": place.place_url or None,
        "tags": [segment.strip() for segment in place.category.split(">") if segment.strip()][-2:],
        "description": place.address,
        "source_tag": "kakao_local",
        "last_synced_at": fetched_at,
    }


def _cached_kakao_restaurant_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{**row, "source_tag": "kakao_local_cache"} for row in rows]


def _restaurant_cache_key(
    origin_slug: str,
    category: str | None,
    walk_minutes: int,
) -> tuple[str, str, int]:
    return (
        origin_slug,
        _category_to_kakao_query(category),
        walk_minutes * WALKING_METERS_PER_MINUTE,
    )


def _restaurant_brand_cache_key(
    origin_slug: str,
    canonical_query: str,
    radius_meters: int,
) -> tuple[str, str, int]:
    normalized_query = _normalize_facility_name(canonical_query) or canonical_query.strip()
    return (origin_slug, f"brand:{normalized_query}", radius_meters)


def _rank_restaurant_search_results(
    conn: DBConnection,
    rows: list[dict[str, Any]],
    *,
    collapsed_query: str | None,
    compact_query: str | None,
    canonical_brand_query: str | None,
    ranking_origin_place: dict[str, Any] | None,
    origin_place: dict[str, Any] | None,
    limit: int,
) -> list[RestaurantSearchResult]:
    ranked: list[
        tuple[
            int,
            int,
            int,
            int,
            int,
            str,
            dict[str, Any],
            int | None,
            int | None,
        ]
    ] = []
    for item in rows:
        if _is_restaurant_search_noise_candidate(item):
            continue
        if collapsed_query is None:
            rank = 0
        else:
            rank = _rank_restaurant_search_candidate(
                item,
                collapsed_query=collapsed_query,
                compact_query=compact_query,
            )
            if rank is None:
                continue
        brand_exactness = _restaurant_brand_exactness(
            item,
            canonical_query=canonical_brand_query,
        )

        hidden_distance_meters: int | None = None
        hidden_walk_minutes: int | None = None
        distance_meters: int | None = None
        estimated_walk_minutes: int | None = None
        if (
            ranking_origin_place is not None
            and item.get("latitude") is not None
            and item.get("longitude") is not None
        ):
            hidden_distance_meters = _haversine_meters(
                ranking_origin_place["latitude"],
                ranking_origin_place["longitude"],
                item["latitude"],
                item["longitude"],
            )
            hidden_walk_minutes = _estimate_place_to_restaurant_walk_minutes(
                conn,
                origin_place=ranking_origin_place,
                restaurant_row=item,
            )
            if origin_place is not None:
                distance_meters = hidden_distance_meters
                estimated_walk_minutes = hidden_walk_minutes

        campus_bucket = 0
        if origin_place is None:
            campus_bucket = (
                0
                if hidden_walk_minutes is not None and hidden_walk_minutes <= 15
                else 1
            )

        ranked.append(
            (
                rank,
                brand_exactness,
                campus_bucket,
                hidden_walk_minutes if hidden_walk_minutes is not None else 999,
                hidden_distance_meters if hidden_distance_meters is not None else 999999,
                str(item.get("name") or ""),
                item,
                distance_meters,
                estimated_walk_minutes,
            )
        )

    ranked.sort(key=lambda item: (item[0], item[1], item[2], item[3], item[4], item[5]))
    return [
        RestaurantSearchResult.model_validate(
            {
                **item,
                "distance_meters": distance_meters,
                "estimated_walk_minutes": estimated_walk_minutes,
            }
        )
        for _, _, _, _, _, _, item, distance_meters, estimated_walk_minutes in ranked[:limit]
    ]


def _resolve_origin_place(conn: DBConnection, origin: str) -> dict[str, Any]:
    try:
        return place_search_runtime.resolve_origin_place(conn, origin)
    except place_search_runtime.NotFoundError as exc:
        raise NotFoundError(str(exc)) from exc
    except place_search_runtime.InvalidRequestError as exc:
        raise InvalidRequestError(str(exc)) from exc


def _default_restaurant_search_origin(
    conn: DBConnection,
    *,
    collapsed_query: str | None,
) -> dict[str, Any] | None:
    return place_search_runtime.default_restaurant_search_origin(
        conn,
        collapsed_query=collapsed_query,
    )


def _resolve_building_place(conn: DBConnection, building: str) -> Place:
    try:
        return place_search_runtime.resolve_building_place(conn, building)
    except place_search_runtime.NotFoundError as exc:
        raise NotFoundError(str(exc)) from exc
    except place_search_runtime.InvalidRequestError as exc:
        raise InvalidRequestError(str(exc)) from exc


def _combine_date_and_minutes(current: datetime, minutes: int | None) -> datetime | None:
    if minutes is None:
        return None
    return current.replace(
        hour=minutes // 60,
        minute=minutes % 60,
        second=0,
        microsecond=0,
    )


def _course_schedule_summary(course: Course) -> str:
    summary = course.title
    if course.section:
        summary += f" ({course.code}-{course.section})"
    elif course.code:
        summary += f" ({course.code})"
    if course.raw_schedule:
        summary += f" / {course.raw_schedule}"
    return summary


def _get_official_classroom_availability_source() -> OfficialClassroomAvailabilitySource | None:
    return None


def _normalize_official_classroom_availability(
    rows: list[dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}
    for row in rows or []:
        room = str(row.get("room") or "").strip()
        if not room:
            continue
        available_now = row.get("available_now")
        if not isinstance(available_now, bool):
            continue
        source_observed_at = row.get("source_observed_at")
        normalized[room.upper()] = {
            "room": room,
            "available_now": available_now,
            "source_observed_at": (
                str(source_observed_at).strip() if source_observed_at is not None else None
            ),
        }
    return normalized


def _build_empty_classroom_room_states(
    by_room: dict[str, list[Course]],
    *,
    current: datetime,
) -> dict[str, dict[str, Any]]:
    current_day = _day_label_from_datetime(current)
    current_minutes = current.hour * 60 + current.minute
    room_states: dict[str, dict[str, Any]] = {}
    for room, room_courses in by_room.items():
        same_day_courses = [course for course in room_courses if course.day_of_week == current_day]
        is_occupied = False
        next_course: Course | None = None
        next_start_minutes: int | None = None

        for course in same_day_courses:
            start_minutes = _period_start_minutes(course.period_start)
            end_minutes = _period_end_minutes(course.period_end)
            if (
                start_minutes is not None
                and end_minutes is not None
                and start_minutes <= current_minutes <= end_minutes
            ):
                is_occupied = True
            if (
                start_minutes is not None
                and start_minutes > current_minutes
                and (next_start_minutes is None or start_minutes < next_start_minutes)
            ):
                next_start_minutes = start_minutes
                next_course = course

        next_occupied_at = _combine_date_and_minutes(current, next_start_minutes)
        room_states[room.upper()] = {
            "room": room,
            "estimated_available_now": not is_occupied,
            "next_occupied_at": (
                next_occupied_at.isoformat(timespec="seconds")
                if next_occupied_at is not None
                else None
            ),
            "next_course_summary": (
                _course_schedule_summary(next_course) if next_course is not None else None
            ),
        }
    return room_states


def _sort_empty_classroom_items(
    items: list[EstimatedEmptyClassroom],
) -> list[EstimatedEmptyClassroom]:
    items.sort(
        key=lambda item: (
            0 if item.next_occupied_at is None else 1,
            (
                -datetime.fromisoformat(item.next_occupied_at).timestamp()
                if item.next_occupied_at is not None
                else 0
            ),
            item.room,
        )
    )
    return items


def _response_availability_mode(*, used_realtime: bool, used_estimated: bool) -> str:
    if used_realtime and used_estimated:
        return "mixed"
    if used_realtime:
        return "realtime"
    return "estimated"


def _build_classroom_availability_note(
    *,
    room_states: dict[str, dict[str, Any]],
    items: list[EstimatedEmptyClassroom],
    used_realtime: bool,
    used_estimated: bool,
    realtime_failed: bool,
) -> str:
    if not room_states and not items and not used_realtime and not realtime_failed:
        return (
            f"{EMPTY_CLASSROOM_ESTIMATE_NOTE} "
            "해당 건물의 강의실 시간표 데이터를 찾지 못했습니다."
        )
    if realtime_failed:
        base = "공식 실시간 공실 조회에 실패해 시간표 기준 예상 공실로 안내합니다."
    elif used_realtime and used_estimated:
        base = "공식 실시간 공실 데이터와 시간표 기준 예상 공실을 함께 사용합니다."
    elif used_realtime:
        base = "공식 실시간 공실 데이터를 우선 사용합니다."
    else:
        base = EMPTY_CLASSROOM_ESTIMATE_NOTE

    if not items:
        return f"{base} 현재 기준으로 비어 있는 강의실이 없습니다."
    return base


def _serialize_empty_classroom_building(place: Place) -> EmptyClassroomBuilding:
    return EmptyClassroomBuilding(
        slug=place.slug,
        name=place.name,
        canonical_name=place.canonical_name or place.name,
        category=place.category,
        aliases=place.aliases,
    )


def _cache_status(fetched_at: str, now: datetime) -> str:
    try:
        fetched = datetime.fromisoformat(fetched_at)
    except ValueError:
        return "expired"
    if fetched.tzinfo is None:
        fetched = fetched.astimezone()
    age_minutes = (now - fetched).total_seconds() / 60
    settings = get_settings()
    if age_minutes <= settings.restaurant_cache_ttl_minutes:
        return "fresh"
    if age_minutes <= settings.restaurant_cache_stale_ttl_minutes:
        return "stale"
    return "expired"


def _cache_rows_for_key(
    conn: DBConnection,
    *,
    origin_slug: str,
    kakao_query: str,
    radius_meters: int,
    latitude: float,
    longitude: float,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    snapshot = repo.get_restaurant_cache_snapshot(
        conn,
        origin_slug=origin_slug,
        kakao_query=kakao_query,
        radius_meters=radius_meters,
    )
    if not snapshot:
        return None, []
    return snapshot, repo.list_restaurant_cache_items(
        conn,
        int(snapshot["id"]),
        latitude=latitude,
        longitude=longitude,
        radius_meters=radius_meters,
    )


def _live_restaurant_rows(
    *,
    place: dict[str, Any],
    kakao_query: str,
    radius_meters: int,
    kakao_client: KakaoLocalClient | Any,
) -> list[dict[str, Any]]:
    fetched_at = _now_iso()
    items = kakao_client.search_sync(
        kakao_query,
        x=place["longitude"],
        y=place["latitude"],
        radius=radius_meters,
    )
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        row = _normalize_kakao_restaurant(item, fetched_at=fetched_at)
        row["id"] = -index
        rows.append(row)
    return rows


def find_nearby_restaurants(
    conn: DBConnection,
    *,
    origin: str,
    category: str | None = None,
    budget_max: int | None = None,
    walk_minutes: int = 15,
    limit: int = 10,
    at: datetime | None = None,
    open_now: bool = False,
    kakao_client: KakaoLocalClient | Any | None = None,
    kakao_place_detail_client: KakaoPlaceDetailClient | Any | None = None,
) -> list[NearbyRestaurant]:
    current = _coerce_datetime(at)
    cache_now = _now()
    place = _resolve_origin_place(conn, origin)
    if place.get("latitude") is None or place.get("longitude") is None:
        raise NotFoundError(f"Origin place has no coordinates: {origin}")

    settings = get_settings()
    origin_slug, kakao_query, radius_meters = _restaurant_cache_key(
        place["slug"],
        category,
        walk_minutes,
    )
    snapshot, cached_rows = _cache_rows_for_key(
        conn,
        origin_slug=origin_slug,
        kakao_query=kakao_query,
        radius_meters=radius_meters,
        latitude=place["latitude"],
        longitude=place["longitude"],
    )
    cache_state = (
        _cache_status(snapshot["fetched_at"], cache_now)
        if snapshot is not None
        else "expired"
    )

    if snapshot is not None and cache_state == "fresh":
        raw_restaurants = cached_rows
        _record_cache_decision(
            decision="fresh_hit",
            origin_slug=origin_slug,
            kakao_query=kakao_query,
            radius_meters=radius_meters,
        )
    elif snapshot is not None and cache_state == "stale":
        raw_restaurants = cached_rows
        _record_cache_decision(
            decision="stale_hit",
            origin_slug=origin_slug,
            kakao_query=kakao_query,
            radius_meters=radius_meters,
        )
    else:
        if kakao_client is None and settings.kakao_rest_api_key:
            kakao_client = KakaoLocalClient(settings.kakao_rest_api_key)
        if kakao_client is not None:
            try:
                live_rows = _live_restaurant_rows(
                    place=place,
                    kakao_query=kakao_query,
                    radius_meters=radius_meters,
                    kakao_client=kakao_client,
                )
                snapshot_id = repo.replace_restaurant_cache_snapshot(
                    conn,
                    origin_slug=origin_slug,
                    kakao_query=kakao_query,
                    radius_meters=radius_meters,
                    fetched_at=live_rows[0]["last_synced_at"] if live_rows else _now_iso(),
                    rows=_cached_kakao_restaurant_rows(live_rows),
                )
                raw_restaurants = [
                    {**row, "source_tag": "kakao_local"}
                    for row in repo.list_restaurant_cache_items(
                        conn,
                        snapshot_id,
                        latitude=place["latitude"],
                        longitude=place["longitude"],
                        radius_meters=radius_meters,
                    )
                ]
                _record_cache_decision(
                    decision="live_fetch_success",
                    origin_slug=origin_slug,
                    kakao_query=kakao_query,
                    radius_meters=radius_meters,
                )
            except httpx.HTTPError:
                _record_cache_decision(
                    decision="live_fetch_error",
                    origin_slug=origin_slug,
                    kakao_query=kakao_query,
                    radius_meters=radius_meters,
                    error_text="kakao_fetch_failed",
                )
                raw_restaurants = repo.list_restaurants_nearby(
                    conn,
                    latitude=place["latitude"],
                    longitude=place["longitude"],
                    radius_meters=radius_meters,
                )
                _record_cache_decision(
                    decision="local_fallback",
                    origin_slug=origin_slug,
                    kakao_query=kakao_query,
                    radius_meters=radius_meters,
                )
        else:
            raw_restaurants = repo.list_restaurants_nearby(
                conn,
                latitude=place["latitude"],
                longitude=place["longitude"],
                radius_meters=radius_meters,
            )
            _record_cache_decision(
                decision="local_fallback",
                origin_slug=origin_slug,
                kakao_query=kakao_query,
                radius_meters=radius_meters,
            )
    facility_hours = _facility_hours_index(conn)

    results: list[NearbyRestaurant] = []
    for raw in raw_restaurants:
        if category and raw["category"] != category:
            continue
        if budget_max is not None:
            min_price = raw.get("min_price")
            max_price = raw.get("max_price")
            if min_price is not None:
                if min_price > budget_max:
                    continue
            elif max_price is not None:
                if max_price > budget_max:
                    continue
            else:
                continue
        if raw.get("latitude") is None or raw.get("longitude") is None:
            continue

        distance = raw.get("distance_meters") or _haversine_meters(
            place["latitude"],
            place["longitude"],
            raw["latitude"],
            raw["longitude"],
        )
        estimated_walk_minutes = _estimate_place_to_restaurant_walk_minutes(
            conn,
            origin_place=place,
            restaurant_row=raw,
        )
        if estimated_walk_minutes > walk_minutes:
            continue
        current_open_now = _restaurant_open_now(
            conn,
            raw,
            facility_hours,
            current,
            kakao_place_detail_client=kakao_place_detail_client,
        )
        if open_now and current_open_now is not True:
            continue

        results.append(
            NearbyRestaurant.model_validate(
                {
                    **raw,
                    "distance_meters": distance,
                    "estimated_walk_minutes": estimated_walk_minutes,
                    "origin": place["slug"],
                    "open_now": current_open_now,
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
    conn: DBConnection,
    *,
    source: CampusMapSource | Any | None = None,
    campus: str = "1",
    fetched_at: str | None = None,
) -> list[Place]:
    source = source or CampusMapSource(CAMPUS_MAP_SOURCE_URL)
    synced_at = fetched_at or _now_iso()
    payload = source.fetch_place_list(campus=campus)
    rows = apply_place_alias_overrides(source.parse_place_list(payload, fetched_at=synced_at))
    repo.replace_places(conn, rows)
    return [
        Place.model_validate(item)
        for item in repo.search_places(conn, limit=max(len(rows), 1))
    ]


def refresh_library_hours_from_library_page(
    conn: DBConnection,
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


def refresh_campus_facilities_from_source(
    conn: DBConnection,
    *,
    source: CampusFacilitiesSource | Any | None = None,
    fetched_at: str | None = None,
) -> list[dict[str, Any]]:
    source = source or CampusFacilitiesSource(FACILITIES_SOURCE_URL)
    synced_at = fetched_at or _now_iso()
    rows = source.parse(source.fetch(), fetched_at=synced_at)
    place_rows = repo.list_places(conn)
    prepared_rows: list[dict[str, Any]] = []
    for row in rows:
        slug = _resolve_campus_facility_place_slug(
            str(row.get("location") or ""),
            place_rows=place_rows,
        )
        prepared_rows.append(
            {
                "facility_name": str(row.get("facility_name") or ""),
                "category": _normalize_optional_text(row.get("category")),
                "phone": _normalize_campus_facility_phone(row.get("phone")),
                "location_text": _normalize_campus_facility_location(row.get("location")),
                "hours_text": _normalize_optional_text(row.get("hours_text")),
                "place_slug": slug,
                "source_url": FACILITIES_SOURCE_URL,
                "source_tag": row.get("source_tag", "cuk_facilities"),
                "last_synced_at": row.get("last_synced_at", synced_at),
            }
        )
    repo.replace_campus_facilities(conn, prepared_rows)
    return repo.list_campus_facilities(conn, limit=max(len(prepared_rows), 1))


def refresh_facility_hours_from_facilities_page(
    conn: DBConnection,
    *,
    source: CampusFacilitiesSource | Any | None = None,
    fetched_at: str | None = None,
) -> list[Place]:
    source = source or CampusFacilitiesSource(FACILITIES_SOURCE_URL)
    synced_at = fetched_at or _now_iso()
    rows = source.parse(source.fetch(), fetched_at=synced_at)
    place_rows = repo.list_places(conn)
    touched: list[Place] = []
    seen_slugs: set[str] = set()
    for row in rows:
        slug = _resolve_campus_facility_place_slug(
            str(row.get("location") or ""),
            place_rows=place_rows,
        )
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


def refresh_campus_dining_menus_from_facilities_page(
    conn: DBConnection,
    *,
    source: CampusFacilitiesSource | Any | None = None,
    fetched_at: str | None = None,
) -> list[CampusDiningMenu]:
    source = source or CampusFacilitiesSource(FACILITIES_SOURCE_URL)
    synced_at = fetched_at or _now_iso()
    rows = source.parse(source.fetch(), fetched_at=synced_at)
    menu_rows: list[dict[str, Any]] = []
    for row in rows:
        source_url = row.get("menu_source_url")
        if not source_url:
            continue
        place = _resolve_campus_dining_menu_place(
            conn,
            facility_name=str(row.get("facility_name") or ""),
            location=str(row.get("location") or ""),
        )
        menu_text: str | None = None
        week_start: str | None = None
        week_end: str | None = None
        try:
            pdf_bytes = source.fetch_menu_document(source_url)
            menu_text = _extract_campus_dining_menu_text(pdf_bytes)
            week_start, week_end = _extract_campus_dining_menu_week_range(menu_text)
        except Exception:
            menu_text = None
            week_start = None
            week_end = None

        menu_rows.append(
            {
                "venue_slug": _slugify_text(str(row.get("facility_name") or "")),
                "venue_name": str(row.get("facility_name") or ""),
                "place_slug": place.slug if place is not None else None,
                "place_name": place.name if place is not None else None,
                "week_label": _normalize_optional_text(row.get("menu_week_label")),
                "week_start": week_start,
                "week_end": week_end,
                "menu_text": menu_text,
                "source_url": source_url,
                "source_tag": "cuk_facilities_menu",
                "last_synced_at": row.get("last_synced_at", synced_at),
            }
        )

    repo.replace_campus_dining_menus(conn, menu_rows)
    return search_campus_dining_menus(conn, limit=max(len(menu_rows), 1))


def refresh_courses_from_subject_search(
    conn: DBConnection,
    *,
    source: CourseCatalogSource | Any | None = None,
    year: int | None = None,
    semester: int | None = None,
    fetched_at: str | None = None,
) -> list[Course]:
    source = source or CourseCatalogSource(COURSE_SOURCE_URL)
    synced_at = fetched_at or _now_iso()
    resolved_year, resolved_semester = _current_year_and_semester()
    resolved_year = year or resolved_year
    resolved_semester = semester or resolved_semester
    rows = _collect_course_snapshot_rows(
        source,
        year=resolved_year,
        semester=resolved_semester,
        fetched_at=synced_at,
    )

    repo.replace_courses(conn, rows)
    return [
        Course.model_validate(item)
        for item in repo.search_courses(
            conn,
            year=resolved_year,
            semester=resolved_semester,
            limit=max(len(rows), 1),
        )
    ]


def refresh_notices_from_notice_board(
    conn: DBConnection,
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
                detail = _canonicalize_notice_detail(item=item, detail=detail)
            except httpx.HTTPError:
                detail = {
                    "title": item["title"],
                    "published_at": item.get("published_at"),
                    "summary": "",
                    "labels": [],
                    "category": classify_notice_category(
                        item["title"],
                        "",
                        item.get("board_category", ""),
                    ),
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


def refresh_academic_calendar_from_source(
    conn: DBConnection,
    *,
    source: AcademicCalendarSource | Any | None = None,
    academic_year: int | None = None,
    fetched_at: str | None = None,
) -> list[AcademicCalendarEvent]:
    source = source or AcademicCalendarSource(ACADEMIC_CALENDAR_SOURCE_URL)
    synced_at = fetched_at or _now_iso()
    resolved_year = academic_year or _current_academic_year()
    start_date, end_date = _academic_year_bounds(resolved_year)
    rows = source.parse(
        source.fetch_range(start_date=start_date, end_date=end_date),
        fetched_at=synced_at,
    )
    repo.replace_academic_calendar(conn, rows)
    return [
        AcademicCalendarEvent.model_validate(item)
        for item in repo.list_academic_calendar(conn, academic_year=resolved_year)
    ]


def refresh_transport_guides_from_location_page(
    conn: DBConnection,
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


def refresh_certificate_guides_from_certificate_page(
    conn: DBConnection,
    *,
    source: CertificateGuideSource | Any | None = None,
    fetched_at: str | None = None,
) -> list[CertificateGuide]:
    source = source or CertificateGuideSource(CERTIFICATE_SOURCE_URL)
    synced_at = fetched_at or _now_iso()
    rows = source.parse(source.fetch(), fetched_at=synced_at)
    repo.replace_certificate_guides(conn, rows)
    return [
        CertificateGuide.model_validate(item)
        for item in repo.list_certificate_guides(conn, limit=max(len(rows), 1))
    ]


def refresh_leave_of_absence_guides_from_source(
    conn: DBConnection,
    *,
    source: LeaveOfAbsenceGuideSource | Any | None = None,
    fetched_at: str | None = None,
) -> list[LeaveOfAbsenceGuide]:
    source = source or LeaveOfAbsenceGuideSource(LEAVE_OF_ABSENCE_SOURCE_URL)
    synced_at = fetched_at or _now_iso()
    rows = source.parse(source.fetch(), fetched_at=synced_at)
    repo.replace_leave_of_absence_guides(conn, rows)
    return [
        LeaveOfAbsenceGuide.model_validate(item)
        for item in repo.list_leave_of_absence_guides(conn, limit=max(len(rows), 1))
    ]


def refresh_scholarship_guides_from_source(
    conn: DBConnection,
    *,
    source: ScholarshipGuideSource | Any | None = None,
    fetched_at: str | None = None,
) -> list[ScholarshipGuide]:
    source = source or ScholarshipGuideSource(SCHOLARSHIP_GUIDE_SOURCE_URL)
    synced_at = fetched_at or _now_iso()
    rows = source.parse(source.fetch(), fetched_at=synced_at)
    repo.replace_scholarship_guides(conn, rows)
    return [
        ScholarshipGuide.model_validate(item)
        for item in repo.list_scholarship_guides(conn, limit=max(len(rows), 1))
    ]


def refresh_wifi_guides_from_source(
    conn: DBConnection,
    *,
    source: WifiGuideSource | Any | None = None,
    fetched_at: str | None = None,
) -> list[WifiGuide]:
    source = source or WifiGuideSource(WIFI_GUIDE_SOURCE_URL)
    synced_at = fetched_at or _now_iso()
    rows = source.parse(source.fetch(), fetched_at=synced_at)
    repo.replace_wifi_guides(conn, rows)
    return [
        WifiGuide.model_validate(item)
        for item in repo.list_wifi_guides(conn, limit=max(len(rows), 1))
    ]


def refresh_academic_support_guides_from_source(
    conn: DBConnection,
    *,
    source: AcademicSupportGuideSource | Any | None = None,
    fetched_at: str | None = None,
) -> list[AcademicSupportGuide]:
    source = source or AcademicSupportGuideSource(ACADEMIC_SUPPORT_GUIDE_SOURCE_URL)
    synced_at = fetched_at or _now_iso()
    rows = source.parse(source.fetch(), fetched_at=synced_at)
    repo.replace_academic_support_guides(conn, rows)
    return [
        AcademicSupportGuide.model_validate(item)
        for item in repo.list_academic_support_guides(conn, limit=max(len(rows), 1))
    ]


def refresh_academic_status_guides_from_source(
    conn: DBConnection,
    *,
    sources: list[Any] | None = None,
    fetched_at: str | None = None,
) -> list[AcademicStatusGuide]:
    synced_at = fetched_at or _now_iso()
    resolved_sources = sources or [
        ReturnFromLeaveOfAbsenceGuideSource(RETURN_FROM_LEAVE_SOURCE_URL),
        DropoutGuideSource(DROPOUT_GUIDE_SOURCE_URL),
        ReAdmissionGuideSource(RE_ADMISSION_GUIDE_SOURCE_URL),
    ]
    rows: list[dict[str, Any]] = []
    for source in resolved_sources:
        rows.extend(source.parse(source.fetch(), fetched_at=synced_at))
    repo.replace_academic_status_guides(conn, rows)
    return [
        AcademicStatusGuide.model_validate(item)
        for item in repo.list_academic_status_guides(conn, limit=max(len(rows), 1))
    ]


def refresh_registration_guides_from_source(
    conn: DBConnection,
    *,
    sources: list[Any] | None = None,
    fetched_at: str | None = None,
) -> list[RegistrationGuide]:
    synced_at = fetched_at or _now_iso()
    resolved_sources = sources or [
        RegistrationBillLookupGuideSource(REGISTRATION_BILL_LOOKUP_SOURCE_URL),
        RegistrationPaymentAndReturnGuideSource(REGISTRATION_PAYMENT_AND_RETURN_SOURCE_URL),
        RegistrationPaymentByStudentGuideSource(REGISTRATION_PAYMENT_BY_STUDENT_SOURCE_URL),
    ]
    rows: list[dict[str, Any]] = []
    for source in resolved_sources:
        rows.extend(source.parse(source.fetch(), fetched_at=synced_at))
    repo.replace_registration_guides(conn, rows)
    return [
        RegistrationGuide.model_validate(item)
        for item in repo.list_registration_guides(conn, limit=max(len(rows), 1))
    ]


def sync_official_snapshot(
    conn: DBConnection,
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
    campus_facilities = refresh_campus_facilities_from_source(conn)
    refresh_library_hours_from_library_page(conn)
    refresh_facility_hours_from_facilities_page(conn)
    dining_menus = refresh_campus_dining_menus_from_facilities_page(conn)
    courses = refresh_courses_from_subject_search(
        conn,
        year=resolved_year,
        semester=resolved_semester,
    )
    notices = refresh_notices_from_notice_board(
        conn,
        pages=notice_pages or settings.official_notice_pages,
    )
    academic_calendar = refresh_academic_calendar_from_source(conn)
    certificate_guides = refresh_certificate_guides_from_certificate_page(conn)
    leave_of_absence_guides = refresh_leave_of_absence_guides_from_source(conn)
    academic_status_guides = refresh_academic_status_guides_from_source(conn)
    registration_guides = refresh_registration_guides_from_source(conn)
    scholarship_guides = refresh_scholarship_guides_from_source(conn)
    academic_support_guides = refresh_academic_support_guides_from_source(conn)
    wifi_guides = refresh_wifi_guides_from_source(conn)
    transport_guides = refresh_transport_guides_from_location_page(conn)
    return {
        "places": len(places),
        "campus_facilities": len(campus_facilities),
        "dining_menus": len(dining_menus),
        "courses": len(courses),
        "notices": len(notices),
        "academic_calendar": len(academic_calendar),
        "certificate_guides": len(certificate_guides),
        "leave_of_absence_guides": len(leave_of_absence_guides),
        "academic_status_guides": len(academic_status_guides),
        "registration_guides": len(registration_guides),
        "scholarship_guides": len(scholarship_guides),
        "academic_support_guides": len(academic_support_guides),
        "wifi_guides": len(wifi_guides),
        "transport_guides": len(transport_guides),
    }


def get_place(conn: DBConnection, identifier: str) -> Place:
    place = repo.get_place_by_slug_or_name(conn, identifier)
    if not place:
        raise NotFoundError(f"Place not found: {identifier}")
    return Place.model_validate(place)


def list_restaurants(conn: DBConnection) -> list[Restaurant]:
    return [Restaurant.model_validate(item) for item in repo.list_restaurants(conn)]
