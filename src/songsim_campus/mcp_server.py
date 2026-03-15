from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import MethodType
from typing import Annotated

from pydantic import Field
from starlette.responses import JSONResponse

from .db import connection, init_db
from .mcp_oauth import (
    Auth0TokenVerifier,
    attach_optional_bearer_auth,
    build_mcp_tool_meta,
    build_protected_resource_metadata,
    build_protected_resource_metadata_path,
    ensure_authenticated_tool_access,
    is_public_mcp_oauth_enabled,
)
from .schemas import (
    Course,
    McpCoordinates,
    McpNearbyRestaurantResult,
    McpNoticeResult,
    McpPlaceResult,
    McpRestaurantSearchResult,
    McpToolError,
    NearbyRestaurant,
    Notice,
    Place,
    ProfileCourseRef,
    ProfileInterests,
    ProfileNoticePreferences,
    ProfileUpdateRequest,
    TransportGuide,
)
from .seed import seed_demo
from .services import (
    InvalidRequestError,
    NotFoundError,
    create_profile,
    find_nearby_restaurants,
    get_class_periods,
    get_place,
    get_profile_course_recommendations,
    get_profile_interests,
    get_profile_meal_recommendations,
    get_profile_timetable,
    list_estimated_empty_classrooms,
    list_latest_notices,
    list_profile_notices,
    list_transport_guides,
    search_courses,
    search_places,
    search_restaurants,
    set_profile_interests,
    set_profile_notice_preferences,
    set_profile_timetable,
    sync_official_snapshot,
    update_profile,
)
from .settings import get_settings

DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"

NOTICE_CATEGORY_DISPLAY = {
    "academic": "학사",
    "scholarship": "장학",
    "employment": "취업",
    "career": "취업",
    "event": "행사",
    "facility": "시설",
    "library": "도서관",
    "general": "일반",
    "place": "일반",
}

RESTAURANT_CATEGORY_DISPLAY = {
    "korean": "한식",
    "western": "양식",
    "japanese": "일식",
    "chinese": "중식",
    "cafe": "카페",
}

PLACE_CATEGORY_GUIDE = {
    "library": "도서관, 열람실, 자료 이용 중심 장소",
    "building": "강의동, 행정동 등 일반 건물",
    "facility": "학생식당, 편의점, 카페 같은 편의시설",
    "gate": "정문, 북문 같은 캠퍼스 출입구",
    "stop": "버스 정류장 같은 기준 위치",
}


def _truncate_preview(text: str, limit: int = 140) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: max(0, limit - 3)].rstrip() + "..."


def _format_opening_hours_preview(opening_hours: dict[str, str]) -> str | None:
    if not opening_hours:
        return None
    preview_items = []
    for key, value in opening_hours.items():
        preview_items.append(f"{key}: {value}")
        if len(preview_items) == 2:
            break
    return " / ".join(preview_items)


def _serialize_public_error(exc: Exception) -> dict[str, str]:
    error_type = "not_found" if isinstance(exc, NotFoundError) else "invalid_request"
    message = str(exc)
    return McpToolError(error=message, type=error_type, message=message).model_dump()


def _serialize_public_place(place: Place) -> dict[str, object]:
    highlights: list[str] = []
    if place.aliases:
        highlights.append(f"별칭: {', '.join(place.aliases[:3])}")
    if place.description:
        highlights.append(_truncate_preview(place.description, limit=80))
    opening_preview = _format_opening_hours_preview(place.opening_hours)
    if opening_preview:
        highlights.append(f"운영: {opening_preview}")
    coordinates = None
    if place.latitude is not None and place.longitude is not None:
        coordinates = McpCoordinates(latitude=place.latitude, longitude=place.longitude)
    return McpPlaceResult(
        slug=place.slug,
        name=place.name,
        canonical_name=place.name,
        category=place.category,
        aliases=place.aliases,
        short_location=(
            _truncate_preview(place.description, limit=80)
            if place.description
            else None
        ),
        coordinates=coordinates,
        highlights=highlights,
    ).model_dump(exclude_none=True)


def _serialize_public_notice(notice: Notice) -> dict[str, object]:
    return McpNoticeResult(
        title=notice.title,
        category_display=NOTICE_CATEGORY_DISPLAY.get(notice.category, "일반"),
        published_at=notice.published_at,
        summary=_truncate_preview(notice.summary, limit=160),
        source_url=notice.source_url,
    ).model_dump(exclude_none=True)


def _restaurant_price_hint(restaurant: NearbyRestaurant) -> str | None:
    if restaurant.min_price is not None and restaurant.max_price is not None:
        if restaurant.min_price == restaurant.max_price:
            return f"{restaurant.min_price:,}원"
        return f"{restaurant.min_price:,}~{restaurant.max_price:,}원"
    if restaurant.min_price is not None:
        return f"{restaurant.min_price:,}원부터"
    if restaurant.max_price is not None:
        return f"{restaurant.max_price:,}원 이하"
    return None


def _restaurant_category_label(restaurant: NearbyRestaurant) -> str:
    if restaurant.tags:
        return restaurant.tags[-1]
    return RESTAURANT_CATEGORY_DISPLAY.get(restaurant.category, "식당")


def _serialize_public_nearby_restaurant(restaurant: NearbyRestaurant) -> dict[str, object]:
    payload = McpNearbyRestaurantResult(
        name=restaurant.name,
        category_display=_restaurant_category_label(restaurant),
        distance_meters=restaurant.distance_meters,
        estimated_walk_minutes=restaurant.estimated_walk_minutes,
        price_hint=_restaurant_price_hint(restaurant),
        open_now=restaurant.open_now,
        location_hint=(
            _truncate_preview(restaurant.description, limit=80)
            if restaurant.description
            else None
        ),
    ).model_dump(exclude_none=True)
    payload["price_hint"] = _restaurant_price_hint(restaurant)
    payload["open_now"] = restaurant.open_now
    return payload


def _serialize_public_restaurant_search(restaurant) -> dict[str, object]:
    payload = McpRestaurantSearchResult(
        name=restaurant.name,
        category_display=RESTAURANT_CATEGORY_DISPLAY.get(restaurant.category, "식당"),
        distance_meters=restaurant.distance_meters,
        estimated_walk_minutes=restaurant.estimated_walk_minutes,
        price_hint=_restaurant_price_hint(restaurant),
        location_hint=(
            _truncate_preview(restaurant.description, limit=80)
            if restaurant.description
            else None
        ),
    ).model_dump(exclude_none=True)
    payload["distance_meters"] = restaurant.distance_meters
    payload["estimated_walk_minutes"] = restaurant.estimated_walk_minutes
    payload["price_hint"] = _restaurant_price_hint(restaurant)
    return payload


def _serialize_public_course(course: Course) -> dict[str, object]:
    payload = course.model_dump()
    summary_parts = [course.title]
    if course.professor:
        summary_parts.append(course.professor)
    if course.raw_schedule:
        summary_parts.append(course.raw_schedule)
    elif course.day_of_week and course.period_start is not None and course.period_end is not None:
        summary_parts.append(f"{course.day_of_week}{course.period_start}~{course.period_end}")
    payload["course_summary"] = " / ".join(summary_parts)
    return payload


def _serialize_public_transport_guide(guide: TransportGuide) -> dict[str, object]:
    payload = guide.model_dump()
    payload["guide_summary"] = guide.summary or (guide.steps[0] if guide.steps else "")
    return payload


def _public_usage_guide() -> str:
    return "\n".join(
        [
            "Songsim public MCP usage guide",
            "",
            "This server is read-only.",
            "Available: places, courses, notices, nearby restaurants, transport guides.",
            "Unavailable: profile, timetable, notice preferences, meal personalization, admin.",
            "",
            "Recommended flow:",
            "1. Read songsim://usage-guide when you need the public MCP capability overview.",
            (
                "2. Use a prompt such as prompt_find_place or "
                "prompt_find_nearby_restaurants to choose the first tool."
            ),
            (
                "3. Use tool_search_places for fuzzy building/facility queries such as "
                "트러스트짐, 헬스장, 편의점, ATM, 복사실, K관, or 정문, then "
                "tool_get_place when you know the slug."
            ),
            (
                "4. Use tool_list_estimated_empty_classrooms for classroom availability "
                "in a lecture building like 니콜스관, N관, or 김수환관. 공식 실시간 "
                "데이터가 있으면 먼저 사용하고, 없으면 시간표 기반 예상 공실로 "
                "폴백합니다."
            ),
            (
                "5. Use tool_find_nearby_restaurants for walkable food "
                "recommendations from a campus origin. You can pass a slug, 대표 이름, "
                "or a clear alias like 중도 or 학생식당. If you set budget_max, only "
                "restaurants with explicit price evidence remain."
            ),
            (
                "6. Use tool_search_restaurants for direct brand-name searches such as "
                "매머드커피, 메가커피, or 이디야. origin이 없어도 캠퍼스 주변에서 "
                "브랜드를 직접 찾을 수 있고, 캠퍼스에 가까운 후보를 먼저 보여줍니다."
            ),
            "7. Use tool_list_latest_notices for latest notices; category is optional.",
            (
                "8. Use tool_list_transport_guides for static subway or bus access "
                "guidance. You can pass query with natural-language cues like 지하철, "
                "1호선, 역곡역, or 버스. 셔틀은 현재 지원하지 않아 빈 결과가 정상입니다."
            ),
            "",
            "Example questions:",
            "- 성심교정 중앙도서관 위치 알려줘",
            "- K관 어디야?",
            "- 정문 위치 알려줘",
            "- 트러스트짐 어디야?",
            "- 헬스장 어디야?",
            "- 편의점 어디 있어?",
            "- 최신 장학 공지 3개 보여줘",
            "- 니콜스관인데 지금 예상 빈 강의실 있어?",
            "- 매머드커피 어디 있어?",
            "- 중앙도서관 근처 밥집 추천해줘",
            "- 중도 근처 밥집 추천해줘",
        ]
    )


def build_mcp():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - optional dependency path
        raise SystemExit(
            "MCP dependency is not installed. "
            "Run `uv sync --extra mcp` or `pip install -e '.[mcp]'`."
        ) from exc

    settings = get_settings()
    public_readonly = settings.app_mode == "public_readonly"
    tool_meta = build_mcp_tool_meta(settings)
    public_mcp_oauth_enabled = is_public_mcp_oauth_enabled(settings)
    token_verifier = None
    if public_mcp_oauth_enabled and settings.resolved_mcp_oauth_audience is not None:
        token_verifier = Auth0TokenVerifier(
            issuer_url=settings.mcp_oauth_issuer or "",
            audience=settings.resolved_mcp_oauth_audience,
            required_scopes=settings.mcp_oauth_scopes,
        )
    mcp = FastMCP(
        "Songsim Campus MCP",
        instructions=(
            "Use this server to answer Songsim campus questions about places, courses, "
            "notices, nearby restaurants, and transport."
        ),
        website_url=settings.public_http_url or None,
        host=settings.app_host,
        port=settings.app_port,
        streamable_http_path="/mcp",
        json_response=True,
    )

    protected_resource_metadata = build_protected_resource_metadata(settings)
    if protected_resource_metadata is not None:
        @mcp.custom_route("/.well-known/oauth-protected-resource", methods=["GET"])
        async def oauth_protected_resource_alias(_request):
            return JSONResponse(protected_resource_metadata)

        protected_resource_metadata_path = build_protected_resource_metadata_path(settings)
        if (
            protected_resource_metadata_path is not None
            and protected_resource_metadata_path != "/.well-known/oauth-protected-resource"
        ):
            @mcp.custom_route(protected_resource_metadata_path, methods=["GET"])
            async def oauth_protected_resource(_request):
                return JSONResponse(protected_resource_metadata)

    @mcp.resource("songsim://source-registry")
    def source_registry() -> str:
        """Return the current source registry and ingestion plan."""
        return (DOCS_DIR / "source_registry.md").read_text(encoding="utf-8")

    @mcp.resource("songsim://transport-guide")
    def transport_guide_resource() -> str:
        """Return the latest static transport guides as JSON."""
        with connection() as conn:
            return json.dumps(
                [item.model_dump() for item in list_transport_guides(conn, limit=50)],
                ensure_ascii=False,
                indent=2,
            )

    if public_readonly:
        @mcp.resource("songsim://usage-guide")
        def usage_guide_resource() -> str:
            """Return the public MCP usage guide."""
            return _public_usage_guide()

        @mcp.resource("songsim://place-categories")
        def place_categories_resource() -> str:
            """Return public place category descriptions as JSON."""
            return json.dumps(PLACE_CATEGORY_GUIDE, ensure_ascii=False, indent=2)

        @mcp.resource("songsim://notice-categories")
        def notice_categories_resource() -> str:
            """Return public notice category labels as JSON."""
            return json.dumps(NOTICE_CATEGORY_DISPLAY, ensure_ascii=False, indent=2)

        @mcp.resource("songsim://class-periods")
        def class_periods_resource() -> str:
            """Return the static class period table as JSON."""
            return json.dumps(
                [item.model_dump() for item in get_class_periods()],
                ensure_ascii=False,
                indent=2,
            )

        @mcp.prompt(
            name="prompt_find_place",
            description="Explain how to search for a place, building, alias, or facility.",
        )
        def prompt_find_place(
            query: Annotated[
                str,
                Field(
                    description=(
                        "건물명, 별칭, 시설명, 교내 입점명. "
                        "예: 중앙도서관, 중도, K관, 정문, 학생회관, 트러스트짐, 헬스장, 편의점"
                    )
                ),
            ]
        ):
            return (
                "Use songsim://usage-guide first if you need the public MCP rules.\n"
                f"Then call tool_search_places with query={query}.\n"
                "Short campus queries like K관 or 정문 are okay; the canonical campus "
                "place should be ranked first.\n"
                "If the result narrows to one clear candidate, call tool_get_place with the "
                "slug from tool_search_places.\n"
                "Use songsim://place-categories if you need to explain category labels."
            )

        @mcp.prompt(
            name="prompt_search_courses",
            description=(
                "Explain how to search Songsim courses by title, code, professor, "
                "year, or semester."
            ),
        )
        def prompt_search_courses(
            query: Annotated[str, Field(description="과목명, 코드, 교수명 등 검색어")] = "",
            year: Annotated[int | None, Field(description="학년도 필터")] = None,
            semester: Annotated[int | None, Field(description="학기 필터")] = None,
        ):
            return (
                "Use tool_search_courses for public course lookup.\n"
                f"query={query or '<empty>'}, year={year}, semester={semester}.\n"
                "If a user asks about period numbers, read songsim://class-periods or call "
                "tool_get_class_periods."
            )

        @mcp.prompt(
            name="prompt_latest_notices",
            description=(
                "Explain how to fetch latest public notices, optionally filtered "
                "by category."
            ),
        )
        def prompt_latest_notices(
            category: Annotated[
                str | None,
                Field(description="optional notice category like scholarship or academic"),
            ] = None,
            limit: Annotated[int, Field(description="가져올 공지 수")] = 10,
        ):
            return (
                "Use tool_list_latest_notices for latest public notices.\n"
                f"category={category or '<optional>'}, limit={limit}.\n"
                "Category is optional. Use songsim://notice-categories if you need to explain "
                "display labels before answering."
            )

        @mcp.prompt(
            name="prompt_find_nearby_restaurants",
            description="Explain how to find walkable nearby restaurants from a campus origin.",
        )
        def prompt_find_nearby_restaurants(
            origin: Annotated[
                str,
                Field(
                    description=(
                        "출발 장소 대표 이름 또는 alias. "
                        "예: 중앙도서관, 중도, 학생식당, K관, 정문"
                    )
                ),
            ],
            category: Annotated[
                str | None,
                Field(description="optional category like korean or cafe"),
            ] = None,
            budget_max: Annotated[int | None, Field(description="optional maximum budget")] = None,
            open_now: Annotated[bool, Field(description="영업 중 후보만 원하면 true")] = False,
            walk_minutes: Annotated[int, Field(description="도보 허용 시간(분)")] = 15,
        ):
            return (
                "Use songsim://usage-guide first if you need the public MCP rules.\n"
                f"Then call tool_find_nearby_restaurants with origin={origin}, "
                f"category={category or '<optional>'}, budget_max={budget_max}, "
                f"open_now={open_now}, walk_minutes={walk_minutes}.\n"
                "A clear alias such as 중도 or 학생식당 can be used directly.\n"
                "Use tool_search_places first only if the origin is ambiguous."
            )

        @mcp.prompt(
            name="prompt_search_restaurants",
            description="Explain how to search restaurant or cafe brands directly by name.",
        )
        def prompt_search_restaurants(
            query: Annotated[
                str,
                Field(
                    description=(
                        "브랜드 또는 상호 직접 검색어. "
                        "예: 매머드커피, 메가커피, 이디야"
                    )
                ),
            ],
            origin: Annotated[
                str | None,
                Field(description="optional campus origin for distance sorting"),
            ] = None,
            category: Annotated[
                str | None,
                Field(description="optional category like cafe or korean"),
            ] = None,
            limit: Annotated[int, Field(description="최대 결과 수")] = 10,
        ):
            return (
                "Use songsim://usage-guide first if you need the public MCP rules.\n"
                f"Then call tool_search_restaurants with query={query}, "
                f"origin={origin or '<optional>'}, category={category or '<optional>'}, "
                f"limit={limit}.\n"
                "Use this for direct brand searches like 매머드커피, 메가커피, or 이디야.\n"
                "If origin is omitted, search around the campus center first and show "
                "campus-nearest matches first.\n"
                "For recommendation-style questions from a campus origin, use the nearby "
                "restaurant flow instead."
            )

        @mcp.prompt(
            name="prompt_find_empty_classrooms",
            description=(
                "Explain how to find current empty classrooms in a building "
                "with realtime-first fallback."
            ),
        )
        def prompt_find_empty_classrooms(
            building: Annotated[
                str,
                Field(
                    description=(
                        "강의실을 확인할 건물 대표 이름 또는 alias. "
                        "예: 니콜스관, 니콜스, N관, 김수환관"
                    )
                ),
            ],
            at: Annotated[
                str | None,
                Field(description="optional ISO 8601 timestamp for the evaluation time"),
            ] = None,
            year: Annotated[int | None, Field(description="optional academic year")] = None,
            semester: Annotated[int | None, Field(description="optional semester")] = None,
            limit: Annotated[int, Field(description="최대 결과 수")] = 10,
        ):
            return (
                "Use songsim://usage-guide first if you need the public MCP rules.\n"
                f"Then call tool_list_estimated_empty_classrooms with building={building}, "
                f"at={at or '<optional>'}, year={year}, semester={semester}, limit={limit}.\n"
                "This flow prefers 공식 실시간 classroom availability when available, "
                "and otherwise falls back to timetable-based 예상 공실.\n"
                "If the building name is unclear, use tool_search_places first."
            )

        @mcp.prompt(
            name="prompt_transport_guide",
            description="Explain how to fetch subway or bus transport guidance for Songsim campus.",
        )
        def prompt_transport_guide(
            mode: Annotated[
                str | None,
                Field(description="optional transport mode like subway or bus"),
            ] = None,
            query: Annotated[
                str | None,
                Field(
                    description=(
                        "optional natural-language transport cue like 지하철, "
                        "1호선, 역곡역, bus"
                    )
                ),
            ] = None,
            limit: Annotated[int, Field(description="가져올 가이드 수")] = 20,
        ):
            return (
                "Use tool_list_transport_guides for static transit guidance.\n"
                f"mode={mode or '<optional>'}, query={query or '<optional>'}, limit={limit}.\n"
                "If mode is explicit, it wins over query. query can be natural-language cues "
                "like 지하철, 1호선, 역곡역, bus, or 버스.\n"
                "This tool is for subway and bus access guidance, not live routing. "
                "셔틀 is not currently supported, so an empty result (빈 결과) is normal."
            )

    @mcp.tool(
        description=(
            (
                "사용자가 성심교정 건물명, 별칭, 시설명, "
                "교내 입점명, 생활 시설명으로 장소를 찾을 때 사용합니다. "
                "질문이 모호하면 먼저 이 tool을 쓰고, 단일 slug가 정해지면 "
                "tool_get_place로 넘어갑니다."
            )
            if public_readonly
            else "성심교정 건물, 도서관, 기준 위치를 한국어 이름이나 별칭으로 찾습니다."
        ),
        meta=tool_meta,
    )
    def tool_search_places(
        query: Annotated[
            str,
            Field(
                description=(
                    "찾고 싶은 건물명, 별칭, 시설명, 교내 입점명, 생활 시설명. "
                    "예: 중앙도서관, 중도, K관, 정문, 트러스트짐, 헬스장, 편의점, ATM"
                )
            ),
        ] = "",
        category: Annotated[
            str | None,
            Field(description="장소 카테고리 필터. 예: library, building, facility"),
        ] = None,
        limit: Annotated[int, Field(description="최대 결과 수. 기본값은 10입니다.")] = 10,
    ):
        with connection() as conn:
            places = search_places(conn, query=query, category=category, limit=limit)
            if public_readonly:
                return [_serialize_public_place(item) for item in places]
            return [item.model_dump() for item in places]

    @mcp.tool(
        description=(
            (
                "이미 장소 slug 또는 정확한 이름을 알고 있을 때 한 곳의 요약 정보를 가져옵니다. "
                "보통 tool_search_places 다음 단계에서 사용합니다."
            )
            if public_readonly
            else "이미 목적지를 알고 있을 때 장소 slug 또는 정확한 이름으로 한 곳을 가져옵니다."
        ),
        meta=tool_meta,
    )
    def tool_get_place(
        identifier: Annotated[
            str,
            Field(description="장소 slug 또는 정확한 이름. 예: central-library, 중앙도서관"),
        ]
    ):
        with connection() as conn:
            try:
                place = get_place(conn, identifier)
                if public_readonly:
                    return _serialize_public_place(place)
                return place.model_dump()
            except NotFoundError as exc:
                if public_readonly:
                    return _serialize_public_error(exc)
                return {"error": str(exc)}

    @mcp.tool(
        description=(
            "과목명, 코드, 교수, 학기 조건으로 현재 공개된 성심교정 개설과목을 찾을 때 사용합니다."
            if public_readonly
            else "현재 공개된 성심교정 개설과목을 과목명, 코드, 교수, 학기 조건으로 찾습니다."
        ),
        meta=tool_meta,
    )
    def tool_search_courses(
        query: Annotated[
            str,
            Field(description="과목명, 과목 코드, 교수명으로 검색할 문자열"),
        ] = "",
        year: Annotated[int | None, Field(description="학년도 필터. 예: 2026")] = None,
        semester: Annotated[int | None, Field(description="학기 필터. 예: 1, 2")] = None,
        limit: Annotated[int, Field(description="최대 결과 수. 기본값은 20입니다.")] = 20,
    ):
        with connection() as conn:
            courses = search_courses(
                conn,
                query=query,
                year=year,
                semester=semester,
                limit=limit,
            )
            if public_readonly:
                return [_serialize_public_course(item) for item in courses]
            return [item.model_dump() for item in courses]

    @mcp.tool(
        description=(
            "교시 번호를 실제 수업 시간으로 바꾸고 싶을 때 고정 교시표를 반환합니다."
            if public_readonly
            else "성심교정 교시 번호를 실제 시간으로 바꿀 수 있도록 고정 교시표를 반환합니다."
        ),
        meta=tool_meta,
    )
    def tool_get_class_periods():
        return [item.model_dump() for item in get_class_periods()]

    @mcp.tool(
        description=(
            (
                "강의동에서 지금 비어 있을 가능성이 높은 강의실을 "
                "찾을 때 사용합니다. "
                "building은 대표 이름과 alias를 받을 수 있습니다. "
                "예: 니콜스관, 니콜스, N관, 김수환관. "
                "공식 실시간 데이터가 있으면 우선 사용하고, "
                "없으면 시간표 기준 예상 공실로 폴백합니다. "
                "결과에는 availability_mode와 다음 점유 시각을 함께 보여줍니다."
            )
            if public_readonly
            else (
                "특정 건물의 현재 공실을 조회하고, 실시간 소스가 없으면 "
                "시간표 기준 예상 공실로 폴백합니다."
            )
        ),
        meta=tool_meta,
    )
    def tool_list_estimated_empty_classrooms(
        building: Annotated[
            str,
            Field(
                description=(
                    "강의실을 확인할 건물 대표 이름 또는 alias. "
                    "예: 니콜스관, 니콜스, N관, K관, 김수환관"
                )
            ),
        ],
        at: Annotated[
            str | None,
            Field(description="기준 시각 ISO 8601 문자열. 없으면 현재 시각을 사용합니다."),
        ] = None,
        year: Annotated[
            int | None,
            Field(description="학년도. 없으면 기준 시각의 현재 학기를 사용합니다."),
        ] = None,
        semester: Annotated[
            int | None,
            Field(description="학기. 없으면 기준 시각의 현재 학기를 사용합니다."),
        ] = None,
        limit: Annotated[int, Field(description="최대 결과 수. 기본값은 10입니다.")] = 10,
    ):
        with connection() as conn:
            try:
                from datetime import datetime

                parsed_at = datetime.fromisoformat(at) if at else None
                payload = list_estimated_empty_classrooms(
                    conn,
                    building=building,
                    at=parsed_at,
                    year=year,
                    semester=semester,
                    limit=limit,
                )
                return payload.model_dump()
            except NotFoundError as exc:
                if public_readonly:
                    return _serialize_public_error(exc)
                return {"error": str(exc)}
            except ValueError:
                exc = InvalidRequestError(
                    "Invalid 'at' timestamp. Use ISO 8601, for example 2026-03-16T10:15:00+09:00."
                )
                if public_readonly:
                    return _serialize_public_error(exc)
                return {"error": str(exc)}

    @mcp.tool(
        description=(
            (
                "캠퍼스 출발지 기준으로 주변 식당을 찾을 때 사용합니다. "
                "origin, 예산(budget_max), open_now, walk_minutes를 함께 줄 수 있습니다. "
                "origin은 slug, 대표 이름, alias(예: 중도, 학생식당)를 받을 수 있습니다. "
                "출발지가 모호하면 tool_search_places를 먼저 사용합니다. budget_max를 "
                "주면 가격 정보가 없는 후보는 제외합니다. open_now=true면 "
                "영업중이 확인된 후보만 남깁니다."
            )
            if public_readonly
            else (
                "캠퍼스 출발지 기준으로 걸어갈 수 있는 주변 식당을 "
                "예산과 카테고리 조건으로 찾습니다."
            )
        ),
        meta=tool_meta,
    )
    def tool_find_nearby_restaurants(
        origin: Annotated[
            str,
            Field(
                description=(
                    "식당을 찾을 출발 장소 대표 이름 또는 alias. "
                    "예: 중앙도서관, 중도, 학생식당"
                )
            ),
        ],
        at: Annotated[
            str | None,
            Field(description="기준 시각 ISO 8601 문자열. open_now 판단에 사용합니다."),
        ] = None,
        category: Annotated[
            str | None,
            Field(description="식당 카테고리 필터. 예: korean, cafe, western"),
        ] = None,
        budget_max: Annotated[
            int | None,
            Field(description="최대 예산(원). 가격 정보가 확인된 후보만 남깁니다."),
        ] = None,
        open_now: Annotated[
            bool,
            Field(description="지금 영업 중인 후보만 보고 싶으면 true. 확인된 후보만 남깁니다."),
        ] = False,
        walk_minutes: Annotated[
            int,
            Field(description="도보 허용 시간(분). 기본값은 15분입니다."),
        ] = 15,
        limit: Annotated[int, Field(description="최대 결과 수. 기본값은 10입니다.")] = 10,
    ):
        with connection() as conn:
            try:
                from datetime import datetime

                parsed_at = datetime.fromisoformat(at) if at else None
                restaurants = find_nearby_restaurants(
                    conn,
                    origin=origin,
                    at=parsed_at,
                    category=category,
                    budget_max=budget_max,
                    open_now=open_now,
                    walk_minutes=walk_minutes,
                    limit=limit,
                )
                if public_readonly:
                    return [_serialize_public_nearby_restaurant(item) for item in restaurants]
                return [item.model_dump() for item in restaurants]
            except NotFoundError as exc:
                if public_readonly:
                    return _serialize_public_error(exc)
                return {"error": str(exc)}
            except ValueError:
                exc = InvalidRequestError(
                    "Invalid 'at' timestamp. Use ISO 8601, for example 2026-03-15T11:00:00+09:00."
                )
                if public_readonly:
                    return _serialize_public_error(exc)
                return {"error": str(exc)}

    @mcp.tool(
        description=(
            (
                "브랜드나 상호를 직접 검색할 때 사용합니다. "
                "매머드커피, 메가커피, 이디야처럼 nearby 추천이 아니라 "
                "이름으로 특정 매장을 찾고 싶을 때 적합합니다."
            )
            if public_readonly
            else (
                "브랜드 또는 상호를 직접 검색해 특정 카페/식당 후보를 찾습니다."
            )
        ),
        meta=tool_meta,
    )
    def tool_search_restaurants(
        query: Annotated[
            str,
            Field(
                description=(
                    "브랜드 상호 또는 직접 검색어. "
                    "예: 매머드커피, 메가커피, 이디야"
                )
            ),
        ] = "",
        origin: Annotated[
            str | None,
            Field(description="거리 정렬 보조용 출발 장소. 예: 중앙도서관, 중도"),
        ] = None,
        category: Annotated[
            str | None,
            Field(description="식당 카테고리 필터. 예: cafe, korean"),
        ] = None,
        limit: Annotated[int, Field(description="최대 결과 수. 기본값은 10입니다.")] = 10,
    ):
        with connection() as conn:
            try:
                restaurants = search_restaurants(
                    conn,
                    query=query,
                    origin=origin,
                    category=category,
                    limit=limit,
                )
                if public_readonly:
                    return [_serialize_public_restaurant_search(item) for item in restaurants]
                return [item.model_dump() for item in restaurants]
            except NotFoundError as exc:
                if public_readonly:
                    return _serialize_public_error(exc)
                return {"error": str(exc)}
            except InvalidRequestError as exc:
                if public_readonly:
                    return _serialize_public_error(exc)
                return {"error": str(exc)}

    @mcp.tool(
        description=(
            (
                "최신 공지를 최신순으로 가져오거나 카테고리로 좁힐 때 사용합니다. "
                "category filter는 optional입니다."
            )
            if public_readonly
            else (
                "최신 성심교정 공지를 가져오고, 필요하면 academic이나 "
                "scholarship 같은 범주로 좁힙니다."
            )
        ),
        meta=tool_meta,
    )
    def tool_list_latest_notices(
        category: Annotated[
            str | None,
            Field(
                description=(
                    "공지 카테고리 필터. 예: academic, scholarship, employment. "
                    "career도 employment와 동일하게 처리합니다."
                )
            ),
        ] = None,
        limit: Annotated[int, Field(description="최대 결과 수. 기본값은 10입니다.")] = 10,
    ):
        with connection() as conn:
            notices = list_latest_notices(conn, category=category, limit=limit)
            if public_readonly:
                return [_serialize_public_notice(item) for item in notices]
            return [item.model_dump() for item in notices]

    @mcp.tool(
        description=(
            "성심교정 지하철·버스 접근 안내를 찾을 때 사용합니다. "
            "정적 subway/bus 안내용이며, query에 지하철·1호선·역곡역·bus 같은 "
            "자연어 cue를 넣을 수 있습니다. 셔틀은 현재 지원하지 않아 빈 결과가 정상입니다."
            if public_readonly
            else "성심교정 지하철·버스 접근 안내를 가져오고, 필요하면 교통수단 모드로 좁힙니다."
        ),
        meta=tool_meta,
    )
    def tool_list_transport_guides(
        mode: Annotated[
            str | None,
            Field(description="교통수단 모드 필터. 예: subway, bus"),
        ] = None,
        query: Annotated[
            str | None,
            Field(description="자연어 교통 cue. 예: 지하철, 1호선, 역곡역, bus, 버스"),
        ] = None,
        limit: Annotated[int, Field(description="최대 결과 수. 기본값은 20입니다.")] = 20,
    ):
        with connection() as conn:
            guides = list_transport_guides(conn, mode=mode, query=query, limit=limit)
            if public_readonly:
                return [_serialize_public_transport_guide(item) for item in guides]
            return [item.model_dump() for item in guides]

    if not public_readonly:
        @mcp.tool(
            description=(
                "Create a local profile id for timetable, notice, "
                "and meal-personalization flows."
            )
        )
        def tool_create_profile(display_name: str = ""):
            with connection() as conn:
                return create_profile(conn, display_name=display_name).model_dump()

        @mcp.tool(
            description=(
                "Update one local profile's display name, department, student year, "
                "or admission type."
            )
        )
        def tool_update_profile(
            profile_id: str,
            display_name: str | None = None,
            department: str | None = None,
            student_year: int | None = None,
            admission_type: str | None = None,
        ):
            with connection() as conn:
                try:
                    payload: dict[str, object] = {}
                    if display_name is not None:
                        payload["display_name"] = display_name
                    if department is not None:
                        payload["department"] = department
                    if student_year is not None:
                        payload["student_year"] = student_year
                    if admission_type is not None:
                        payload["admission_type"] = admission_type
                    return update_profile(
                        conn,
                        profile_id,
                        ProfileUpdateRequest(**payload),
                    ).model_dump()
                except (NotFoundError, InvalidRequestError) as exc:
                    return {"error": str(exc)}

        @mcp.tool(
            description=(
                "Replace a profile timetable using official course keys: "
                "year, semester, code, section."
            )
        )
        def tool_set_profile_timetable(profile_id: str, courses: list[dict[str, int | str]]):
            with connection() as conn:
                try:
                    refs = [ProfileCourseRef.model_validate(item) for item in courses]
                    return [
                        item.model_dump()
                        for item in set_profile_timetable(conn, profile_id, refs)
                    ]
                except (NotFoundError, InvalidRequestError) as exc:
                    return {"error": str(exc)}

        @mcp.tool(
            description="Get the current stored timetable for one local profile id."
        )
        def tool_get_profile_timetable(
            profile_id: str,
            year: int | None = None,
            semester: int | None = None,
        ):
            with connection() as conn:
                try:
                    return [
                        item.model_dump()
                        for item in get_profile_timetable(
                            conn,
                            profile_id,
                            year=year,
                            semester=semester,
                        )
                    ]
                except NotFoundError as exc:
                    return {"error": str(exc)}

        @mcp.tool(
            description="Save notice categories and keywords for one local profile id."
        )
        def tool_set_profile_notice_preferences(
            profile_id: str,
            categories: list[str] | None = None,
            keywords: list[str] | None = None,
        ):
            with connection() as conn:
                try:
                    return set_profile_notice_preferences(
                        conn,
                        profile_id,
                        ProfileNoticePreferences(
                            categories=categories or [],
                            keywords=keywords or [],
                        ),
                    ).model_dump()
                except (NotFoundError, InvalidRequestError) as exc:
                    return {"error": str(exc)}

        @mcp.tool(
            description="Save normalized interest tags for one local profile id."
        )
        def tool_set_profile_interests(profile_id: str, tags: list[str] | None = None):
            with connection() as conn:
                try:
                    return set_profile_interests(
                        conn,
                        profile_id,
                        ProfileInterests(tags=tags or []),
                    ).model_dump()
                except (NotFoundError, InvalidRequestError) as exc:
                    return {"error": str(exc)}

        @mcp.tool(
            description="Get the current stored interest tags for one local profile id."
        )
        def tool_get_profile_interests(profile_id: str):
            with connection() as conn:
                try:
                    return get_profile_interests(conn, profile_id).model_dump()
                except NotFoundError as exc:
                    return {"error": str(exc)}

        @mcp.tool(
            description=(
                "List notices that match one profile's saved preferences "
                "and profile context."
            )
        )
        def tool_get_profile_notices(profile_id: str, limit: int = 10):
            with connection() as conn:
                try:
                    return [
                        item.model_dump()
                        for item in list_profile_notices(conn, profile_id, limit=limit)
                    ]
                except (NotFoundError, InvalidRequestError) as exc:
                    return {"error": str(exc)}

        @mcp.tool(
            description=(
                "Recommend courses for one profile using department and student-year context, "
                "excluding courses already in the timetable."
            )
        )
        def tool_get_profile_course_recommendations(
            profile_id: str,
            year: int | None = None,
            semester: int | None = None,
            query: str = "",
            limit: int = 10,
        ):
            with connection() as conn:
                try:
                    return [
                        item.model_dump()
                        for item in get_profile_course_recommendations(
                            conn,
                            profile_id,
                            year=year,
                            semester=semester,
                            query=query,
                            limit=limit,
                        )
                    ]
                except (NotFoundError, InvalidRequestError) as exc:
                    return {"error": str(exc)}

        @mcp.tool(
            description=(
                "Recommend meals from an origin place using one profile's timetable, budget, "
                "and optional category filters."
            )
        )
        def tool_get_profile_meal_recommendations(
            profile_id: str,
            origin: str,
            at: str | None = None,
            year: int | None = None,
            semester: int | None = None,
            budget_max: int | None = None,
            category: str | None = None,
            open_now: bool = False,
            limit: int = 10,
        ):
            with connection() as conn:
                try:
                    from datetime import datetime

                    parsed_at = datetime.fromisoformat(at) if at else None
                    return get_profile_meal_recommendations(
                        conn,
                        profile_id,
                        origin=origin,
                        at=parsed_at,
                        year=year,
                        semester=semester,
                        budget_max=budget_max,
                        category=category,
                        limit=limit,
                        open_now=open_now,
                    ).model_dump()
                except (NotFoundError, InvalidRequestError, ValueError) as exc:
                    return {"error": str(exc)}

    if public_mcp_oauth_enabled and token_verifier is not None:
        original_streamable_http_app = mcp.streamable_http_app
        original_call_tool = mcp.call_tool

        def streamable_http_app_with_optional_auth(self):
            app = original_streamable_http_app()
            return attach_optional_bearer_auth(app, token_verifier)

        async def call_tool_with_mixed_auth(self, name: str, arguments: dict[str, object]):
            try:
                request_context = self.get_context().request_context
            except ValueError:
                request_context = None
            if request_context is not None and request_context.request is not None:
                ensure_authenticated_tool_access(settings)
            return await original_call_tool(name, arguments)

        mcp.streamable_http_app = MethodType(streamable_http_app_with_optional_auth, mcp)
        mcp.call_tool = MethodType(call_tool_with_mixed_auth, mcp)
        mcp._mcp_server.call_tool(validate_input=False)(mcp.call_tool)

    return mcp


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Songsim MCP server")
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    args = parser.parse_args()

    init_db()
    settings = get_settings()
    if settings.sync_official_on_start:
        with connection() as conn:
            sync_official_snapshot(conn)
    elif settings.seed_demo_on_start:
        seed_demo(force=False)

    mcp = build_mcp()
    if args.transport == "streamable-http":
        mcp.run(transport="streamable-http")
    else:
        mcp.run()


if __name__ == "__main__":
    main()
