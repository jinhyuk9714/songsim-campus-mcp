from __future__ import annotations

import asyncio

import pytest


def test_register_shared_tools_public_mode_exposes_expected_tool_names_and_metadata():
    fastmcp = pytest.importorskip("mcp.server.fastmcp")

    from songsim_campus.mcp_tool_catalog import register_shared_tools

    async def main():
        mcp = fastmcp.FastMCP("Tool Catalog Test")
        register_shared_tools(
            mcp,
            connection_factory=lambda: None,
            public_readonly=True,
            tool_meta={"securitySchemes": [{"type": "oauth2", "scopes": ["songsim.read"]}]},
        )
        tools = await mcp.list_tools()
        payloads = {tool.name: tool.model_dump(by_alias=True) for tool in tools}
        return {tool.name for tool in tools}, payloads

    tool_names, payloads = asyncio.run(main())

    assert tool_names == {
        "tool_search_places",
        "tool_get_place",
        "tool_search_courses",
        "tool_list_academic_calendar",
        "tool_list_academic_support_guides",
        "tool_list_academic_status_guides",
        "tool_list_registration_guides",
        "tool_list_class_guides",
        "tool_list_seasonal_semester_guides",
        "tool_list_certificate_guides",
        "tool_list_leave_of_absence_guides",
        "tool_list_scholarship_guides",
        "tool_list_wifi_guides",
        "tool_get_class_periods",
        "tool_get_library_seat_status",
        "tool_list_estimated_empty_classrooms",
        "tool_search_dining_menus",
        "tool_search_restaurants",
        "tool_find_nearby_restaurants",
        "tool_list_latest_notices",
        "tool_list_transport_guides",
    }
    assert "건물명" in payloads["tool_search_places"]["description"]
    assert "별칭" in payloads["tool_search_places"]["description"]
    assert "교내 입점명" in payloads["tool_search_places"]["description"]
    assert "브랜드" in payloads["tool_search_restaurants"]["description"]
    assert "매머드커피" in payloads["tool_search_restaurants"]["description"]
    assert "실시간" in payloads["tool_list_estimated_empty_classrooms"]["description"]
    assert "예상 공실" in payloads["tool_list_estimated_empty_classrooms"]["description"]
    assert "등록금 고지서" in payloads["tool_list_registration_guides"]["description"]
    assert "초과학기생" in payloads["tool_list_registration_guides"]["description"]
    assert "수업평가" in payloads["tool_list_class_guides"]["description"]
    assert "외국어강의" in payloads["tool_list_class_guides"]["description"]
    assert "계절학기" in payloads["tool_list_seasonal_semester_guides"]["description"]
    assert "신청절차" in payloads["tool_list_seasonal_semester_guides"]["description"]
    assert "securitySchemes" in payloads["tool_search_places"]["_meta"]
    assert "K관" in (
        payloads["tool_search_places"]["inputSchema"]["properties"]["query"]["description"]
    )
    assert "walk_minutes" in payloads["tool_find_nearby_restaurants"]["description"]
    assert "payment_and_return" in (
        payloads["tool_list_registration_guides"]["inputSchema"]["properties"]["topic"]["description"]
    )
    assert "course_evaluation" in (
        payloads["tool_list_class_guides"]["inputSchema"]["properties"]["topic"]["description"]
    )
    assert "seasonal_semester" in (
        payloads["tool_list_seasonal_semester_guides"]["inputSchema"]["properties"]["topic"][
            "description"
        ]
    )


def test_register_local_profile_tools_exposes_expected_tool_names():
    fastmcp = pytest.importorskip("mcp.server.fastmcp")

    from songsim_campus.mcp_tool_catalog import register_local_profile_tools

    async def main():
        mcp = fastmcp.FastMCP("Tool Catalog Test")
        register_local_profile_tools(mcp, connection_factory=lambda: None)
        tools = await mcp.list_tools()
        return {tool.name for tool in tools}

    tool_names = asyncio.run(main())

    assert tool_names == {
        "tool_create_profile",
        "tool_update_profile",
        "tool_set_profile_timetable",
        "tool_get_profile_timetable",
        "tool_set_profile_notice_preferences",
        "tool_set_profile_interests",
        "tool_get_profile_interests",
        "tool_get_profile_notices",
        "tool_get_profile_course_recommendations",
        "tool_get_profile_meal_recommendations",
    }


def test_register_shared_and_local_tools_do_not_conflict():
    fastmcp = pytest.importorskip("mcp.server.fastmcp")

    from songsim_campus.mcp_tool_catalog import (
        register_local_profile_tools,
        register_shared_tools,
    )

    async def main():
        mcp = fastmcp.FastMCP("Tool Catalog Test")
        register_shared_tools(
            mcp,
            connection_factory=lambda: None,
            public_readonly=False,
            tool_meta=None,
        )
        register_local_profile_tools(mcp, connection_factory=lambda: None)
        tools = await mcp.list_tools()
        return [tool.name for tool in tools]

    tool_names = asyncio.run(main())

    assert len(tool_names) == len(set(tool_names))
    assert "tool_search_places" in tool_names
    assert "tool_create_profile" in tool_names
