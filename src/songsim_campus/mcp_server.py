from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import MethodType

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
    ProfileCourseRef,
    ProfileInterests,
    ProfileNoticePreferences,
    ProfileUpdateRequest,
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
    list_latest_notices,
    list_profile_notices,
    list_transport_guides,
    search_courses,
    search_places,
    set_profile_interests,
    set_profile_notice_preferences,
    set_profile_timetable,
    sync_official_snapshot,
    update_profile,
)
from .settings import get_settings

DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"


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

    @mcp.tool(
        description=(
            "성심교정 건물, 도서관, 기준 위치를 한국어 이름이나 별칭으로 찾습니다."
        ),
        meta=tool_meta,
    )
    def tool_search_places(query: str = "", category: str | None = None, limit: int = 10):
        with connection() as conn:
            return [
                item.model_dump()
                for item in search_places(conn, query=query, category=category, limit=limit)
            ]

    @mcp.tool(
        description=(
            "이미 목적지를 알고 있을 때 장소 slug 또는 정확한 이름으로 한 곳을 가져옵니다."
        ),
        meta=tool_meta,
    )
    def tool_get_place(identifier: str):
        with connection() as conn:
            try:
                return get_place(conn, identifier).model_dump()
            except NotFoundError as exc:
                return {"error": str(exc)}

    @mcp.tool(
        description=(
            "현재 공개된 성심교정 개설과목을 과목명, 코드, 교수, 학기 조건으로 찾습니다."
        ),
        meta=tool_meta,
    )
    def tool_search_courses(
        query: str = "",
        year: int | None = None,
        semester: int | None = None,
        limit: int = 20,
    ):
        with connection() as conn:
            return [
                item.model_dump()
                for item in search_courses(
                    conn,
                    query=query,
                    year=year,
                    semester=semester,
                    limit=limit,
                )
            ]

    @mcp.tool(
        description=(
            "성심교정 교시 번호를 실제 시간으로 바꿀 수 있도록 고정 교시표를 반환합니다."
        ),
        meta=tool_meta,
    )
    def tool_get_class_periods():
        return [item.model_dump() for item in get_class_periods()]

    @mcp.tool(
        description=(
            "캠퍼스 출발지 기준으로 걸어갈 수 있는 주변 식당을 예산과 카테고리 조건으로 찾습니다."
        ),
        meta=tool_meta,
    )
    def tool_find_nearby_restaurants(
        origin: str,
        at: str | None = None,
        category: str | None = None,
        budget_max: int | None = None,
        open_now: bool = False,
        walk_minutes: int = 15,
        limit: int = 10,
    ):
        with connection() as conn:
            try:
                from datetime import datetime

                parsed_at = datetime.fromisoformat(at) if at else None
                return [
                    item.model_dump()
                    for item in find_nearby_restaurants(
                        conn,
                        origin=origin,
                        at=parsed_at,
                        category=category,
                        budget_max=budget_max,
                        open_now=open_now,
                        walk_minutes=walk_minutes,
                        limit=limit,
                    )
                ]
            except (NotFoundError, ValueError) as exc:
                return {"error": str(exc)}

    @mcp.tool(
        description=(
            "최신 성심교정 공지를 가져오고, 필요하면 academic이나 scholarship 같은 범주로 좁힙니다."
        ),
        meta=tool_meta,
    )
    def tool_list_latest_notices(category: str | None = None, limit: int = 10):
        with connection() as conn:
            return [
                item.model_dump()
                for item in list_latest_notices(conn, category=category, limit=limit)
            ]

    @mcp.tool(
        description=(
            "성심교정 지하철·버스 접근 안내를 가져오고, 필요하면 교통수단 모드로 좁힙니다."
        ),
        meta=tool_meta,
    )
    def tool_list_transport_guides(mode: str | None = None, limit: int = 20):
        with connection() as conn:
            return [
                item.model_dump()
                for item in list_transport_guides(conn, mode=mode, limit=limit)
            ]

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
