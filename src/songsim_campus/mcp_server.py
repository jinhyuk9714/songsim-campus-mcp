from __future__ import annotations

import argparse
import json
from pathlib import Path

from .db import connection, init_db
from .schemas import ProfileCourseRef, ProfileNoticePreferences
from .seed import seed_demo
from .services import (
    InvalidRequestError,
    NotFoundError,
    create_profile,
    find_nearby_restaurants,
    get_class_periods,
    get_place,
    get_profile_meal_recommendations,
    get_profile_timetable,
    list_latest_notices,
    list_profile_notices,
    list_transport_guides,
    search_courses,
    search_places,
    set_profile_notice_preferences,
    set_profile_timetable,
    sync_official_snapshot,
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

    mcp = FastMCP("Songsim Campus Assistant", json_response=True)

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
            "Search Songsim campus buildings and landmarks "
            "by Korean name, alias, or category."
        )
    )
    def tool_search_places(query: str = "", category: str | None = None, limit: int = 10):
        with connection() as conn:
            return [
                item.model_dump()
                for item in search_places(conn, query=query, category=category, limit=limit)
            ]

    @mcp.tool(
        description=(
            "Get one campus place by slug or exact Korean name "
            "when you already know the destination."
        )
    )
    def tool_get_place(identifier: str):
        with connection() as conn:
            try:
                return get_place(conn, identifier).model_dump()
            except NotFoundError as exc:
                return {"error": str(exc)}

    @mcp.tool(
        description=(
            "Search public course offerings by course title, "
            "code, professor, year, and semester."
        )
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
            "Return the fixed Songsim class-period timetable "
            "so period numbers can be converted to clock times."
        )
    )
    def tool_get_class_periods():
        return [item.model_dump() for item in get_class_periods()]

    @mcp.tool(
        description=(
            "Find walkable nearby restaurants from a campus place "
            "with optional cuisine and budget filters."
        )
    )
    def tool_find_nearby_restaurants(
        origin: str,
        category: str | None = None,
        budget_max: int | None = None,
        walk_minutes: int = 15,
        limit: int = 10,
    ):
        with connection() as conn:
            try:
                return [
                    item.model_dump()
                    for item in find_nearby_restaurants(
                        conn,
                        origin=origin,
                        category=category,
                        budget_max=budget_max,
                        walk_minutes=walk_minutes,
                        limit=limit,
                    )
                ]
            except NotFoundError as exc:
                return {"error": str(exc)}

    @mcp.tool(
        description=(
            "List the latest campus notices, optionally narrowed "
            "to categories such as academic or scholarship."
        )
    )
    def tool_list_latest_notices(category: str | None = None, limit: int = 10):
        with connection() as conn:
            return [
                item.model_dump()
                for item in list_latest_notices(conn, category=category, limit=limit)
            ]

    @mcp.tool(
        description=(
            "List static Songsim campus transit guides for subway and bus access, "
            "optionally filtered by mode."
        )
    )
    def tool_list_transport_guides(mode: str | None = None, limit: int = 20):
        with connection() as conn:
            return [
                item.model_dump()
                for item in list_transport_guides(conn, mode=mode, limit=limit)
            ]

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
        description="List notices that match one profile's saved categories or keywords."
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
                ).model_dump()
            except (NotFoundError, InvalidRequestError, ValueError) as exc:
                return {"error": str(exc)}

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
