from __future__ import annotations

import asyncio
import json

import pytest

from songsim_campus.db import connection, init_db
from songsim_campus.mcp_server import build_mcp
from songsim_campus.repo import (
    replace_courses,
    replace_notices,
    replace_places,
    replace_restaurants,
    replace_transport_guides,
    update_place_opening_hours,
)
from songsim_campus.seed import seed_demo
from songsim_campus.services import refresh_transport_guides_from_location_page
from songsim_campus.settings import clear_settings_cache


class McpTransportSource:
    def fetch(self):
        return '<transport></transport>'

    def parse(self, html: str, *, fetched_at: str):
        assert html == '<transport></transport>'
        return [
            {
                'mode': 'subway',
                'title': '1호선',
                'summary': '역곡역 2번 출구에서 도보 10분',
                'steps': ['인천역 ↔ 역곡역 : 35분 소요'],
                'source_url': 'https://www.catholic.ac.kr/ko/about/location_songsim.do',
                'source_tag': 'cuk_transport',
                'last_synced_at': fetched_at,
            }
        ]


def _tool_payloads(result) -> list[dict[str, object]]:
    return [json.loads(item.text) for item in result]


def test_mcp_transport_tool_and_resource_share_service_data(app_env):
    pytest.importorskip('mcp.server.fastmcp')
    init_db()
    seed_demo(force=True)
    with connection() as conn:
        refresh_transport_guides_from_location_page(conn, source=McpTransportSource())

    async def main():
        mcp = build_mcp()
        tool_result = await mcp.call_tool('tool_list_transport_guides', {'limit': 10})
        resource_result = await mcp.read_resource('songsim://transport-guide')
        return tool_result, list(resource_result)

    tool_result, resource_result = asyncio.run(main())

    tool_payload = json.loads(tool_result[0].text)
    resource_payload = json.loads(resource_result[0].content)

    assert tool_payload['title'] == '1호선'
    assert resource_payload[0]['title'] == '1호선'


def test_mcp_transport_tool_accepts_query_and_mode_precedence(app_env, monkeypatch):
    pytest.importorskip('mcp.server.fastmcp')
    init_db()
    seed_demo(force=True)
    with connection() as conn:
        replace_transport_guides(
            conn,
            [
                {
                    "mode": "bus",
                    "title": "마을버스",
                    "summary": "51번, 51-1번, 51-2번 버스",
                    "steps": ["[가톨릭대학교, 역곡도서관] 정류장 하차"],
                    "source_url": "https://www.catholic.ac.kr/ko/about/location_songsim.do",
                    "source_tag": "cuk_transport",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
                {
                    "mode": "subway",
                    "title": "1호선",
                    "summary": "역곡역 2번 출구 또는 소사역 3번 출구에서 도보 10분",
                    "steps": ["인천역 ↔ 역곡역 : 35분 소요"],
                    "source_url": "https://www.catholic.ac.kr/ko/about/location_songsim.do",
                    "source_tag": "cuk_transport",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
            ],
        )
    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    clear_settings_cache()

    async def main():
        mcp = build_mcp()
        subway = await mcp.call_tool("tool_list_transport_guides", {"query": "지하철"})
        shuttle = await mcp.call_tool("tool_list_transport_guides", {"query": "셔틀"})
        explicit_bus = await mcp.call_tool(
            "tool_list_transport_guides",
            {"mode": "bus", "query": "지하철"},
        )
        return subway, shuttle, explicit_bus

    subway_result, shuttle_result, explicit_bus_result = asyncio.run(main())

    assert _tool_payloads(subway_result)[0]["mode"] == "subway"
    assert _tool_payloads(shuttle_result) == []
    assert _tool_payloads(explicit_bus_result)[0]["mode"] == "bus"

    clear_settings_cache()


def test_mcp_profile_tools_share_timetable_service_data(app_env):
    pytest.importorskip('mcp.server.fastmcp')
    init_db()
    seed_demo(force=True)
    with connection() as conn:
        replace_courses(
            conn,
            [
                {
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

    async def main():
        mcp = build_mcp()
        created = await mcp.call_tool('tool_create_profile', {'display_name': '성심학생'})
        profile = json.loads(created[0].text)
        await mcp.call_tool(
            'tool_set_profile_timetable',
            {
                'profile_id': profile['id'],
                'courses': [
                    {'year': 2026, 'semester': 1, 'code': 'CSE101', 'section': '01'}
                ],
            },
        )
        timetable = await mcp.call_tool(
            'tool_get_profile_timetable',
            {'profile_id': profile['id'], 'year': 2026, 'semester': 1},
        )
        return json.loads(timetable[0].text)

    timetable_payload = asyncio.run(main())

    assert timetable_payload['title'] == '자료구조'


def test_mcp_profile_personalization_tools_share_service_data(app_env):
    pytest.importorskip('mcp.server.fastmcp')
    init_db()
    seed_demo(force=True)
    with connection() as conn:
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

    async def main():
        mcp = build_mcp()
        created = await mcp.call_tool('tool_create_profile', {'display_name': '성심학생'})
        profile = json.loads(created[0].text)
        updated = await mcp.call_tool(
            'tool_update_profile',
            {
                'profile_id': profile['id'],
                'department': '컴퓨터정보공학부',
                'student_year': 1,
                'admission_type': 'freshman',
            },
        )
        interests = await mcp.call_tool(
            'tool_set_profile_interests',
            {'profile_id': profile['id'], 'tags': ['scholarship', 'language']},
        )
        courses = await mcp.call_tool(
            'tool_get_profile_course_recommendations',
            {'profile_id': profile['id'], 'year': 2026, 'semester': 1},
        )
        return (
            json.loads(updated[0].text),
            json.loads(interests[0].text),
            json.loads(courses[0].text),
        )

    updated_payload, interests_payload, course_payload = asyncio.run(main())

    assert updated_payload['department'] == '컴퓨터정보공학부'
    assert interests_payload['tags'] == ['scholarship', 'language']
    assert course_payload['course']['code'] == 'CSE201'
    assert course_payload['course']['section'] == '02'
    assert course_payload['matched_reasons'] == ['department:컴퓨터정보공학부', 'student_year:1']


def test_mcp_nearby_restaurant_tool_supports_open_now_filter(app_env):
    pytest.importorskip('mcp.server.fastmcp')
    init_db()
    seed_demo(force=True)
    with connection() as conn:
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
                },
                {
                    "slug": "unknown-bap",
                    "name": "알수없음식당",
                    "category": "korean",
                    "min_price": 7000,
                    "max_price": 9000,
                    "latitude": 37.4869,
                    "longitude": 126.7999,
                    "tags": ["한식"],
                    "description": "테스트 식당",
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
            ],
        )
        update_place_opening_hours(
            conn,
            "central-library",
            {"카페드림": "평일 08:00~19:00 토 10:00~16:00 (일/공휴일휴무)"},
            last_synced_at="2026-03-13T09:00:00+09:00",
        )

    async def main():
        mcp = build_mcp()
        result = await mcp.call_tool(
            'tool_find_nearby_restaurants',
            {
                'origin': 'central-library',
                'open_now': True,
                'at': '2026-03-15T11:00:00+09:00',
            },
        )
        if not result:
            return []
        return json.loads(result[0].text)

    payload = asyncio.run(main())

    assert payload == []


def test_mcp_nearby_restaurant_tool_reuses_kakao_cache(app_env, monkeypatch):
    pytest.importorskip('mcp.server.fastmcp')
    init_db()
    seed_demo(force=True)
    monkeypatch.setenv("SONGSIM_KAKAO_REST_API_KEY", "test-key")
    clear_settings_cache()

    class McpCacheKakaoClient:
        calls = 0

        def __init__(self, api_key: str):
            assert api_key == "test-key"

        def search_sync(self, query: str, *, x=None, y=None, radius: int = 1000):
            type(self).calls += 1
            from songsim_campus.services import KakaoPlace

            return [
                KakaoPlace(
                    name="가톨릭백반",
                    category="음식점 > 한식",
                    address="경기 부천시 원미구",
                    latitude=37.48674,
                    longitude=126.80182,
                    place_id="1",
                    place_url="https://place.map.kakao.com/1",
                )
            ]

    monkeypatch.setattr('songsim_campus.services.KakaoLocalClient', McpCacheKakaoClient)

    async def main():
        mcp = build_mcp()
        first = await mcp.call_tool(
            'tool_find_nearby_restaurants',
            {'origin': 'central-library', 'category': 'korean', 'walk_minutes': 15},
        )
        second = await mcp.call_tool(
            'tool_find_nearby_restaurants',
            {'origin': 'central-library', 'category': 'korean', 'walk_minutes': 15},
        )
        return json.loads(first[0].text), json.loads(second[0].text)

    first_payload, second_payload = asyncio.run(main())

    assert McpCacheKakaoClient.calls == 1
    assert first_payload['source_tag'] == 'kakao_local'
    assert second_payload['source_tag'] == 'kakao_local_cache'


def test_mcp_public_readonly_mode_registers_only_read_only_tools(app_env, monkeypatch):
    pytest.importorskip('mcp.server.fastmcp')
    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    clear_settings_cache()

    async def main():
        mcp = build_mcp()
        tools = await mcp.list_tools()
        resources = await mcp.list_resources()
        return [tool.name for tool in tools], [str(resource.uri) for resource in resources]

    tool_names, resource_uris = asyncio.run(main())

    assert set(tool_names) == {
        "tool_search_places",
        "tool_get_place",
        "tool_search_courses",
        "tool_get_class_periods",
        "tool_list_estimated_empty_classrooms",
        "tool_search_restaurants",
        "tool_find_nearby_restaurants",
        "tool_list_latest_notices",
        "tool_list_transport_guides",
    }
    assert "tool_create_profile" not in tool_names
    assert "tool_get_profile_notices" not in tool_names
    assert "songsim://source-registry" in resource_uris
    assert "songsim://transport-guide" in resource_uris

    clear_settings_cache()


def test_mcp_public_readonly_mode_registers_prompts_and_extended_resources(app_env, monkeypatch):
    pytest.importorskip('mcp.server.fastmcp')
    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    clear_settings_cache()

    async def main():
        mcp = build_mcp()
        prompts = await mcp.list_prompts()
        resources = await mcp.list_resources()
        return [prompt.name for prompt in prompts], [str(resource.uri) for resource in resources]

    prompt_names, resource_uris = asyncio.run(main())

    assert set(prompt_names) == {
        "prompt_find_place",
        "prompt_search_courses",
        "prompt_notice_categories",
        "prompt_latest_notices",
        "prompt_class_periods",
        "prompt_find_empty_classrooms",
        "prompt_search_restaurants",
        "prompt_find_nearby_restaurants",
        "prompt_transport_guide",
    }
    assert set(resource_uris) >= {
        "songsim://source-registry",
        "songsim://transport-guide",
        "songsim://usage-guide",
        "songsim://place-categories",
        "songsim://notice-categories",
        "songsim://class-periods",
    }

    clear_settings_cache()


def test_mcp_local_full_mode_does_not_register_public_prompts(app_env, monkeypatch):
    pytest.importorskip('mcp.server.fastmcp')
    monkeypatch.delenv("SONGSIM_APP_MODE", raising=False)
    clear_settings_cache()

    async def main():
        mcp = build_mcp()
        prompts = await mcp.list_prompts()
        return [prompt.name for prompt in prompts]

    prompt_names = asyncio.run(main())

    assert prompt_names == []

    clear_settings_cache()


def test_mcp_public_readonly_mode_exposes_agent_friendly_tool_metadata(app_env, monkeypatch):
    pytest.importorskip('mcp.server.fastmcp')
    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    clear_settings_cache()

    async def main():
        mcp = build_mcp()
        tools = await mcp.list_tools()
        return {tool.name: tool.model_dump(by_alias=True) for tool in tools}

    tools = asyncio.run(main())

    assert "건물명" in tools["tool_search_places"]["description"]
    assert "별칭" in tools["tool_search_places"]["description"]
    assert "tool_get_place" in tools["tool_search_places"]["description"]
    assert "교내 입점명" in tools["tool_search_places"]["description"]
    assert "slug" in tools["tool_get_place"]["description"]
    assert "과목명" in tools["tool_search_courses"]["description"]
    assert "교수" in tools["tool_search_courses"]["description"]
    assert "브랜드" in tools["tool_search_restaurants"]["description"]
    assert "매머드커피" in tools["tool_search_restaurants"]["description"]
    assert "실시간" in tools["tool_list_estimated_empty_classrooms"]["description"]
    assert "예상 공실" in tools["tool_list_estimated_empty_classrooms"]["description"]
    assert "니콜스관" in tools["tool_list_estimated_empty_classrooms"]["description"]
    assert "김수환관" in tools["tool_list_estimated_empty_classrooms"]["description"]
    assert "출발지" in tools["tool_find_nearby_restaurants"]["description"]
    assert "alias" in tools["tool_find_nearby_restaurants"]["description"]
    assert "학생식당" in tools["tool_find_nearby_restaurants"]["description"]
    assert "예산" in tools["tool_find_nearby_restaurants"]["description"]
    assert "가격 정보가 없는" in tools["tool_find_nearby_restaurants"]["description"]
    assert "open_now" in tools["tool_find_nearby_restaurants"]["description"]
    assert "walk_minutes" in tools["tool_find_nearby_restaurants"]["description"]
    assert "카테고리" in tools["tool_list_latest_notices"]["description"]
    assert "optional" in tools["tool_list_latest_notices"]["description"]
    assert "지하철" in tools["tool_list_transport_guides"]["description"]
    assert "버스" in tools["tool_list_transport_guides"]["description"]

    place_query_description = (
        tools["tool_search_places"]["inputSchema"]["properties"]["query"]["description"]
    )
    assert "건물명" in place_query_description
    assert "트러스트짐" in place_query_description
    assert "헬스장" in place_query_description
    assert "편의점" in place_query_description
    assert "K관" in place_query_description
    assert "정문" in place_query_description
    assert "브랜드 상호" in (
        tools["tool_search_restaurants"]["inputSchema"]["properties"]["query"]["description"]
    )
    assert "출발 장소" in (
        tools["tool_find_nearby_restaurants"]["inputSchema"]["properties"]["origin"]["description"]
    )
    assert "중도" in (
        tools["tool_find_nearby_restaurants"]["inputSchema"]["properties"]["origin"]["description"]
    )
    assert "김수환관" in (
        tools["tool_list_estimated_empty_classrooms"]["inputSchema"]["properties"]["building"]["description"]
    )
    assert "역곡역" in (
        tools["tool_list_transport_guides"]["inputSchema"]["properties"]["query"]["description"]
    )
    assert "셔틀" in tools["tool_list_transport_guides"]["description"]

    clear_settings_cache()


def test_mcp_public_prompts_explain_tool_selection_flow(app_env, monkeypatch):
    pytest.importorskip('mcp.server.fastmcp')
    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    clear_settings_cache()

    async def main():
        mcp = build_mcp()
        prompt = await mcp.get_prompt(
            "prompt_find_place",
            {"query": "K관"},
        )
        return prompt

    prompt = asyncio.run(main())
    message = prompt.messages[0].content.text

    assert "tool_search_places" in message
    assert "query=K관" in message
    assert "tool_get_place" in message
    assert "songsim://place-categories" in message

    clear_settings_cache()


def test_mcp_public_empty_classroom_prompt_explains_estimate_flow(app_env, monkeypatch):
    pytest.importorskip('mcp.server.fastmcp')
    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    clear_settings_cache()

    async def main():
        mcp = build_mcp()
        prompt = await mcp.get_prompt(
            "prompt_find_empty_classrooms",
            {"building": "니콜스관"},
        )
        return prompt

    prompt = asyncio.run(main())
    message = prompt.messages[0].content.text

    assert "tool_list_estimated_empty_classrooms" in message
    assert "building=니콜스관" in message
    assert "실시간" in message
    assert "예상 공실" in message
    assert "tool_search_places" in message

    clear_settings_cache()

    async def main():
        mcp = build_mcp()
        prompt = await mcp.get_prompt(
            "prompt_find_nearby_restaurants",
            {"origin": "central-library", "category": "korean"},
        )
        return prompt

    prompt = asyncio.run(main())
    message = prompt.messages[0].content.text

    assert "tool_find_nearby_restaurants" in message
    assert "origin=central-library" in message
    assert "category=korean" in message
    assert "songsim://usage-guide" in message
    assert "alias" in message

    clear_settings_cache()

    async def main():
        mcp = build_mcp()
        prompt = await mcp.get_prompt(
            "prompt_search_restaurants",
            {"query": "매머드커피"},
        )
        return prompt

    prompt = asyncio.run(main())
    message = prompt.messages[0].content.text

    assert "tool_search_restaurants" in message
    assert "query=매머드커피" in message
    assert "campus-nearest matches first" in message
    assert "tool_find_nearby_restaurants" not in message

    clear_settings_cache()

    async def main():
        mcp = build_mcp()
        prompt = await mcp.get_prompt(
            "prompt_transport_guide",
            {"query": "지하철", "mode": "subway"},
        )
        return prompt

    prompt = asyncio.run(main())
    message = prompt.messages[0].content.text

    assert "tool_list_transport_guides" in message
    assert "query=지하철" in message
    assert "mode=subway" in message
    assert "셔틀" in message
    assert "빈 결과" in message

    clear_settings_cache()


def test_mcp_public_usage_and_class_period_resources_are_readable(app_env, monkeypatch):
    pytest.importorskip('mcp.server.fastmcp')
    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    clear_settings_cache()

    async def main():
        mcp = build_mcp()
        usage = list(await mcp.read_resource('songsim://usage-guide'))
        periods = list(await mcp.read_resource('songsim://class-periods'))
        return usage[0].content, periods[0].content

    usage_content, periods_content = asyncio.run(main())
    periods_payload = json.loads(periods_content)

    assert "read-only" in usage_content
    assert "tool_search_places" in usage_content
    assert "tool_search_restaurants" in usage_content
    assert "tool_list_estimated_empty_classrooms" in usage_content
    assert "실시간" in usage_content
    assert "tool_find_nearby_restaurants" in usage_content
    assert "예상 공실" in usage_content
    assert "profile" in usage_content
    assert "중도" in usage_content
    assert "가까운 후보를 먼저" in usage_content
    assert "매머드커피" in usage_content
    assert "헬스장" in usage_content
    assert "편의점" in usage_content
    assert periods_payload[0]["period"] == 1
    assert {"period", "start", "end"} <= set(periods_payload[0].keys())

    clear_settings_cache()


def test_mcp_public_notice_category_resource_returns_canonical_metadata(app_env, monkeypatch):
    pytest.importorskip('mcp.server.fastmcp')
    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    clear_settings_cache()

    async def main():
        mcp = build_mcp()
        categories = list(await mcp.read_resource('songsim://notice-categories'))
        return categories[0].content

    payload = json.loads(asyncio.run(main()))

    assert payload == [
        {"category": "academic", "category_display": "학사", "aliases": []},
        {"category": "scholarship", "category_display": "장학", "aliases": []},
        {"category": "employment", "category_display": "취업", "aliases": ["career"]},
        {"category": "general", "category_display": "일반", "aliases": ["place"]},
    ]

    clear_settings_cache()


def test_mcp_public_metadata_prompts_explain_direct_metadata_flow(app_env, monkeypatch):
    pytest.importorskip('mcp.server.fastmcp')
    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    clear_settings_cache()

    async def main():
        mcp = build_mcp()
        categories_prompt = await mcp.get_prompt("prompt_notice_categories", {})
        periods_prompt = await mcp.get_prompt("prompt_class_periods", {})
        notices_prompt = await mcp.get_prompt(
            "prompt_latest_notices",
            {"limit": 5},
        )
        courses_prompt = await mcp.get_prompt(
            "prompt_search_courses",
            {"query": "7교시"},
        )
        return (
            categories_prompt.messages[0].content.text,
            periods_prompt.messages[0].content.text,
            notices_prompt.messages[0].content.text,
            courses_prompt.messages[0].content.text,
        )

    categories_message, periods_message, notices_message, courses_message = asyncio.run(main())

    assert "songsim://notice-categories" in categories_message
    assert "/notice-categories" in categories_message
    assert "employment" in categories_message
    assert "career" in categories_message
    assert "songsim://class-periods" in periods_message
    assert "tool_get_class_periods" in periods_message
    assert "/periods" in periods_message
    assert "/gpt/periods" in periods_message
    assert "songsim://notice-categories" in notices_message
    assert "/notice-categories" in notices_message
    assert "songsim://class-periods" in courses_message
    assert "/periods" in courses_message
    assert "/gpt/periods" in courses_message

    clear_settings_cache()


def test_mcp_public_search_places_returns_condensed_place_payload(app_env, monkeypatch):
    pytest.importorskip('mcp.server.fastmcp')
    init_db()
    seed_demo(force=True)
    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    clear_settings_cache()

    async def main():
        mcp = build_mcp()
        result = await mcp.call_tool('tool_search_places', {'query': '중앙도서관', 'limit': 1})
        return _tool_payloads(result)[0]

    payload = asyncio.run(main())

    assert payload["slug"] == "central-library"
    assert payload["name"] == "중앙도서관"
    assert payload["canonical_name"] == "중앙도서관"
    assert payload["aliases"] == ["도서관", "중도"]
    assert payload["coordinates"] == {"latitude": 37.48643, "longitude": 126.80164}
    assert payload["short_location"] == "자료 열람과 시험기간 공부에 쓰는 중심 공간"
    assert payload["highlights"][0] == "별칭: 도서관, 중도"
    assert "description" not in payload
    assert "opening_hours" not in payload

    clear_settings_cache()


def test_mcp_public_search_places_supports_facility_tenant_alias(app_env, monkeypatch):
    pytest.importorskip('mcp.server.fastmcp')
    init_db()
    seed_demo(force=True)
    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    clear_settings_cache()

    async def main():
        mcp = build_mcp()
        result = await mcp.call_tool('tool_search_places', {'query': '트러스트짐', 'limit': 1})
        return _tool_payloads(result)[0]

    payload = asyncio.run(main())

    assert payload["slug"] == "student-center"
    assert payload["name"] == "학생회관"

    clear_settings_cache()


def test_mcp_public_search_places_supports_generic_facility_nouns(app_env, monkeypatch):
    pytest.importorskip('mcp.server.fastmcp')
    init_db()
    with connection() as conn:
        replace_places(
            conn,
            [
                {
                    "slug": "student-center",
                    "name": "학생회관",
                    "category": "facility",
                    "aliases": ["학회관"],
                    "description": "학생 편의시설이 많은 건물",
                    "latitude": 37.48652,
                    "longitude": 126.80216,
                    "opening_hours": {
                        "트러스트짐": "평일 07:00~22:30",
                        "편의점": "상시 07:00~24:00",
                        "교내복사실": "평일 08:50~19:00",
                        "우리은행": "평일 09:00~16:00",
                    },
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
                {
                    "slug": "dormitory-stephen",
                    "name": "스테파노기숙사",
                    "category": "dormitory",
                    "aliases": ["K관"],
                    "description": "기숙사 생활시설 건물",
                    "latitude": 37.48516,
                    "longitude": 126.80323,
                    "opening_hours": {
                        "이마트24 K관점": "상시 07:00~24:00",
                    },
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
            ],
        )
    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    clear_settings_cache()

    async def main():
        mcp = build_mcp()
        gym = await mcp.call_tool('tool_search_places', {'query': '헬스장', 'limit': 5})
        store = await mcp.call_tool('tool_search_places', {'query': '편의점', 'limit': 5})
        return _tool_payloads(gym), _tool_payloads(store)

    gym_payloads, store_payloads = asyncio.run(main())

    assert [item["slug"] for item in gym_payloads] == ["student-center"]
    assert [item["slug"] for item in store_payloads[:2]] == [
        "student-center",
        "dormitory-stephen",
    ]

    clear_settings_cache()


def test_mcp_public_search_places_prefers_short_query_place_preference_for_k_hall(
    app_env,
    monkeypatch,
):
    pytest.importorskip('mcp.server.fastmcp')
    init_db()
    with connection() as conn:
        replace_places(
            conn,
            [
                {
                    "slug": "dormitory-stephen",
                    "name": "스테파노기숙사",
                    "category": "dormitory",
                    "aliases": ["K관"],
                    "description": "기숙사 생활시설 건물",
                    "latitude": 37.48516,
                    "longitude": 126.80323,
                    "opening_hours": {},
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
                {
                    "slug": "kim-sou-hwan-hall",
                    "name": "김수환관",
                    "category": "building",
                    "aliases": ["김수환", "K관"],
                    "description": "강의실과 연구실이 있는 건물",
                    "latitude": 37.48630,
                    "longitude": 126.80120,
                    "opening_hours": {},
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
            ],
        )
    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    clear_settings_cache()

    async def main():
        mcp = build_mcp()
        result = await mcp.call_tool("tool_search_places", {"query": "K관", "limit": 10})
        return _tool_payloads(result)

    payloads = asyncio.run(main())

    assert [item["slug"] for item in payloads] == ["kim-sou-hwan-hall"]

    clear_settings_cache()


def test_mcp_public_search_restaurants_returns_compact_brand_match(app_env, monkeypatch):
    pytest.importorskip('mcp.server.fastmcp')
    init_db()
    with connection() as conn:
        replace_restaurants(
            conn,
            [
                {
                    "slug": "mammoth",
                    "name": "매머드익스프레스 부천가톨릭대학교점",
                    "category": "cafe",
                    "min_price": None,
                    "max_price": None,
                    "latitude": 37.48556,
                    "longitude": 126.80379,
                    "tags": ["커피전문점", "매머드익스프레스"],
                    "description": "경기 부천시 원미구 지봉로 43",
                    "source_tag": "kakao_local_cache",
                    "last_synced_at": "2026-03-15T01:19:14+00:00",
                }
            ],
        )
    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    clear_settings_cache()

    async def main():
        mcp = build_mcp()
        result = await mcp.call_tool('tool_search_restaurants', {'query': '매머드커피', 'limit': 5})
        return _tool_payloads(result)

    payload = asyncio.run(main())

    assert payload == [
        {
            "name": "매머드익스프레스 부천가톨릭대학교점",
            "category_display": "카페",
            "distance_meters": None,
            "estimated_walk_minutes": None,
            "price_hint": None,
            "location_hint": "경기 부천시 원미구 지봉로 43",
        }
    ]

    clear_settings_cache()


def test_mcp_public_search_restaurants_uses_live_fallback(app_env, monkeypatch):
    pytest.importorskip("mcp.server.fastmcp")
    init_db()
    seed_demo(force=True)
    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    monkeypatch.setenv("SONGSIM_KAKAO_REST_API_KEY", "test-key")
    clear_settings_cache()

    class McpBrandKakaoClient:
        def __init__(self, api_key: str):
            assert api_key == "test-key"

        def search_sync(self, query: str, *, x=None, y=None, radius: int = 1000):
            assert query == "매머드익스프레스"
            from songsim_campus.services import KakaoPlace

            return [
                KakaoPlace(
                    name="매머드익스프레스 가상의외부점",
                    category="음식점 > 카페 > 커피전문점",
                    address="경기 부천시 소사구 경인옛로 37",
                    latitude=37.48186,
                    longitude=126.79612,
                    place_id="201",
                    place_url="https://place.map.kakao.com/201",
                ),
                KakaoPlace(
                    name="매머드익스프레스 부천가톨릭대학교점",
                    category="음식점 > 카페 > 커피전문점",
                    address="경기 부천시 원미구 지봉로 43",
                    latitude=37.48556,
                    longitude=126.80379,
                    place_id="101",
                    place_url="https://place.map.kakao.com/101",
                )
            ]

    monkeypatch.setattr("songsim_campus.services.KakaoLocalClient", McpBrandKakaoClient)

    async def main():
        mcp = build_mcp()
        result = await mcp.call_tool("tool_search_restaurants", {"query": "매머드커피", "limit": 5})
        return _tool_payloads(result)

    payload = asyncio.run(main())

    assert payload[:2] == [
        {
            "name": "매머드익스프레스 부천가톨릭대학교점",
            "category_display": "카페",
            "distance_meters": None,
            "estimated_walk_minutes": None,
            "price_hint": None,
            "location_hint": "경기 부천시 원미구 지봉로 43",
        },
        {
            "name": "매머드익스프레스 가상의외부점",
            "category_display": "카페",
            "distance_meters": None,
            "estimated_walk_minutes": None,
            "price_hint": None,
            "location_hint": "경기 부천시 소사구 경인옛로 37",
        }
    ]

    clear_settings_cache()


def test_mcp_public_search_restaurants_expands_radius_for_long_tail_brand(
    app_env,
    monkeypatch,
):
    pytest.importorskip("mcp.server.fastmcp")
    init_db()
    seed_demo(force=True)
    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    monkeypatch.setenv("SONGSIM_KAKAO_REST_API_KEY", "test-key")
    clear_settings_cache()
    calls: list[int] = []

    class McpBrandKakaoClient:
        def __init__(self, api_key: str):
            assert api_key == "test-key"

        def search_sync(self, query: str, *, x=None, y=None, radius: int = 1000):
            assert query == "커피빈"
            assert x is not None and y is not None
            calls.append(radius)
            from songsim_campus.services import KakaoPlace

            if radius == 15 * 75:
                return []
            assert radius == 5000
            return [
                KakaoPlace(
                    name="커피빈 역곡점",
                    category="음식점 > 카페 > 커피전문점",
                    address="경기 부천시 원미구 지봉로 70",
                    latitude=37.48621,
                    longitude=126.80491,
                    place_id="904",
                    place_url="https://place.map.kakao.com/904",
                )
            ]

    monkeypatch.setattr("songsim_campus.services.KakaoLocalClient", McpBrandKakaoClient)

    async def main():
        mcp = build_mcp()
        result = await mcp.call_tool("tool_search_restaurants", {"query": "커피빈", "limit": 5})
        return _tool_payloads(result)

    payload = asyncio.run(main())

    assert calls == [15 * 75, 5000]
    assert payload == [
        {
            "name": "커피빈 역곡점",
            "category_display": "카페",
            "distance_meters": None,
            "estimated_walk_minutes": None,
            "price_hint": None,
            "location_hint": "경기 부천시 원미구 지봉로 70",
        }
    ]

    clear_settings_cache()


def test_mcp_public_search_restaurants_filters_brand_noise_candidates(app_env, monkeypatch):
    pytest.importorskip("mcp.server.fastmcp")
    init_db()
    seed_demo(force=True)
    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    monkeypatch.setenv("SONGSIM_KAKAO_REST_API_KEY", "test-key")
    clear_settings_cache()

    class McpBrandKakaoClient:
        def __init__(self, api_key: str):
            assert api_key == "test-key"

        def search_sync(self, query: str, *, x=None, y=None, radius: int = 1000):
            assert query == "스타벅스"
            from songsim_campus.services import KakaoPlace

            return [
                KakaoPlace(
                    name="스타벅스 역곡역DT점 주차장",
                    category="교통시설 > 주차장",
                    address="경기 부천시 소사구 괴안동 112-25",
                    latitude=37.48345,
                    longitude=126.80935,
                    place_id="902",
                    place_url="https://place.map.kakao.com/902",
                ),
                KakaoPlace(
                    name="스타벅스 역곡역DT점",
                    category="음식점 > 카페 > 커피전문점",
                    address="경기 부천시 소사구 경인로 485",
                    latitude=37.48354,
                    longitude=126.80929,
                    place_id="903",
                    place_url="https://place.map.kakao.com/903",
                ),
            ]

    monkeypatch.setattr("songsim_campus.services.KakaoLocalClient", McpBrandKakaoClient)

    async def main():
        mcp = build_mcp()
        result = await mcp.call_tool("tool_search_restaurants", {"query": "스타벅스", "limit": 5})
        return _tool_payloads(result)

    payload = asyncio.run(main())

    assert payload == [
        {
            "name": "스타벅스 역곡역DT점",
            "category_display": "카페",
            "distance_meters": None,
            "estimated_walk_minutes": None,
            "price_hint": None,
            "location_hint": "경기 부천시 소사구 경인로 485",
        }
    ]

    clear_settings_cache()


def test_mcp_public_notices_return_category_display_and_summary_preview(app_env, monkeypatch):
    pytest.importorskip('mcp.server.fastmcp')
    init_db()
    seed_demo(force=True)
    with connection() as conn:
        replace_notices(
            conn,
            [
                {
                    "title": "2026학년도 1학기 장학 신청 안내",
                    "category": "scholarship",
                    "published_at": "2026-03-13",
                    "summary": "장학 신청 대상, 제출 서류, 신청 기한을 자세히 안내합니다. " * 10,
                    "labels": ["장학", "학부"],
                    "source_url": "https://example.com/notices/1",
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                }
            ],
        )
    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    clear_settings_cache()

    async def main():
        mcp = build_mcp()
        result = await mcp.call_tool('tool_list_latest_notices', {'limit': 1})
        return _tool_payloads(result)[0]

    payload = asyncio.run(main())

    assert payload["title"] == "2026학년도 1학기 장학 신청 안내"
    assert payload["category_display"] == "장학"
    assert payload["source_url"] == "https://example.com/notices/1"
    assert len(payload["summary"]) <= 160
    assert payload["summary"].endswith("...")
    assert "category" not in payload
    assert "labels" not in payload

    clear_settings_cache()


def test_mcp_public_notices_display_legacy_career_as_employment(app_env, monkeypatch):
    pytest.importorskip('mcp.server.fastmcp')
    init_db()
    with connection() as conn:
        replace_notices(
            conn,
            [
                {
                    "title": "진로취업상담 안내",
                    "category": "career",
                    "published_at": "2026-03-13",
                    "summary": "취업 상담 일정",
                    "labels": ["취업"],
                    "source_url": "https://example.com/notices/career",
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                }
            ],
        )
    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    clear_settings_cache()

    async def main():
        mcp = build_mcp()
        result = await mcp.call_tool(
            'tool_list_latest_notices',
            {'category': 'employment', 'limit': 1},
        )
        return _tool_payloads(result)[0]

    payload = asyncio.run(main())

    assert payload["title"] == "진로취업상담 안내"
    assert payload["category_display"] == "취업"

    clear_settings_cache()


def test_mcp_public_notices_display_place_as_general(app_env, monkeypatch):
    pytest.importorskip('mcp.server.fastmcp')
    init_db()
    with connection() as conn:
        replace_notices(
            conn,
            [
                {
                    "title": "중앙도서관 자리 안내",
                    "category": "place",
                    "published_at": "2026-03-13",
                    "summary": "도서관 좌석 안내",
                    "labels": ["도서관"],
                    "source_url": "https://example.com/notices/place",
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                }
            ],
        )
    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    clear_settings_cache()

    async def main():
        mcp = build_mcp()
        result = await mcp.call_tool('tool_list_latest_notices', {'limit': 1})
        return _tool_payloads(result)[0]

    payload = asyncio.run(main())

    assert payload["title"] == "중앙도서관 자리 안내"
    assert payload["category_display"] == "일반"

    clear_settings_cache()


def test_mcp_public_search_places_normalizes_spacing_variants(app_env, monkeypatch):
    pytest.importorskip('mcp.server.fastmcp')
    init_db()
    seed_demo(force=True)
    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    clear_settings_cache()

    async def main():
        mcp = build_mcp()
        result = await mcp.call_tool('tool_search_places', {'query': '중앙 도서관', 'limit': 1})
        return _tool_payloads(result)[0]

    payload = asyncio.run(main())

    assert payload["slug"] == "central-library"
    assert payload["name"] == "중앙도서관"

    clear_settings_cache()


def test_mcp_public_nearby_restaurants_return_condensed_payload(app_env, monkeypatch):
    pytest.importorskip('mcp.server.fastmcp')
    init_db()
    seed_demo(force=True)
    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    clear_settings_cache()

    async def main():
        mcp = build_mcp()
        result = await mcp.call_tool(
            'tool_find_nearby_restaurants',
            {'origin': 'central-library', 'limit': 1},
        )
        return _tool_payloads(result)[0]

    payload = asyncio.run(main())

    assert isinstance(payload["category_display"], str)
    assert payload["category_display"]
    assert "distance_meters" in payload
    assert "estimated_walk_minutes" in payload
    assert "open_now" in payload
    assert "location_hint" in payload
    assert "description" not in payload
    assert "tags" not in payload

    clear_settings_cache()


def test_mcp_public_nearby_restaurants_accept_origin_alias(app_env, monkeypatch):
    pytest.importorskip('mcp.server.fastmcp')
    init_db()
    seed_demo(force=True)
    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    clear_settings_cache()

    async def main():
        mcp = build_mcp()
        alias_result = await mcp.call_tool(
            'tool_find_nearby_restaurants',
            {'origin': '중도', 'limit': 1},
        )
        slug_result = await mcp.call_tool(
            'tool_find_nearby_restaurants',
            {'origin': 'central-library', 'limit': 1},
        )
        return _tool_payloads(alias_result)[0], _tool_payloads(slug_result)[0]

    alias_payload, slug_payload = asyncio.run(main())

    assert alias_payload["name"] == slug_payload["name"]
    assert alias_payload["category_display"] == slug_payload["category_display"]

    clear_settings_cache()


def test_mcp_public_nearby_restaurants_accept_facility_alias_origin(app_env, monkeypatch):
    pytest.importorskip('mcp.server.fastmcp')
    init_db()
    seed_demo(force=True)
    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    clear_settings_cache()

    async def main():
        mcp = build_mcp()
        alias_result = await mcp.call_tool(
            'tool_find_nearby_restaurants',
            {'origin': '학생식당', 'limit': 1},
        )
        slug_result = await mcp.call_tool(
            'tool_find_nearby_restaurants',
            {'origin': 'student-center', 'limit': 1},
        )
        return _tool_payloads(alias_result)[0], _tool_payloads(slug_result)[0]

    alias_payload, slug_payload = asyncio.run(main())

    assert alias_payload["name"] == slug_payload["name"]
    assert alias_payload["category_display"] == slug_payload["category_display"]

    clear_settings_cache()


def test_mcp_public_nearby_restaurants_prefers_short_query_origin_preference_for_k_hall(
    app_env,
    monkeypatch,
):
    pytest.importorskip('mcp.server.fastmcp')
    init_db()
    with connection() as conn:
        replace_places(
            conn,
            [
                {
                    "slug": "dormitory-stephen",
                    "name": "스테파노기숙사",
                    "category": "dormitory",
                    "aliases": ["K관"],
                    "description": "기숙사 생활시설 건물",
                    "latitude": 37.48516,
                    "longitude": 126.80323,
                    "opening_hours": {},
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
                {
                    "slug": "kim-sou-hwan-hall",
                    "name": "김수환관",
                    "category": "building",
                    "aliases": ["김수환", "K관"],
                    "description": "강의실과 연구실이 있는 건물",
                    "latitude": 37.48630,
                    "longitude": 126.80120,
                    "opening_hours": {},
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
            ],
        )
        replace_restaurants(
            conn,
            [
                {
                    "slug": "k-hall-cafe",
                    "name": "K관카페",
                    "category": "cafe",
                    "min_price": 5000,
                    "max_price": 6000,
                    "latitude": 37.48631,
                    "longitude": 126.80121,
                    "tags": ["카페"],
                    "description": "김수환관 앞",
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                }
            ],
        )
    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    clear_settings_cache()

    async def main():
        mcp = build_mcp()
        result = await mcp.call_tool(
            "tool_find_nearby_restaurants",
            {"origin": "K관", "walk_minutes": 5, "limit": 3},
        )
        return _tool_payloads(result)

    payloads = asyncio.run(main())

    assert [item["name"] for item in payloads] == ["K관카페"]

    clear_settings_cache()


def test_mcp_public_nearby_restaurants_budget_max_requires_price_evidence(app_env, monkeypatch):
    pytest.importorskip('mcp.server.fastmcp')
    init_db()
    seed_demo(force=True)
    with connection() as conn:
        replace_restaurants(
            conn,
            [
                {
                    "slug": "budget-kimbap",
                    "name": "버짓김밥",
                    "category": "korean",
                    "min_price": 7000,
                    "max_price": 9000,
                    "latitude": 37.48653,
                    "longitude": 126.80174,
                    "tags": ["한식"],
                    "description": "가격 정보가 있는 김밥집",
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
                {
                    "slug": "mystery-price-cafe",
                    "name": "가격미상카페",
                    "category": "cafe",
                    "min_price": None,
                    "max_price": None,
                    "latitude": 37.48663,
                    "longitude": 126.80184,
                    "tags": ["카페"],
                    "description": "가격 정보가 없는 후보",
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
            ],
        )
    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    clear_settings_cache()

    async def main():
        mcp = build_mcp()
        result = await mcp.call_tool(
            'tool_find_nearby_restaurants',
            {'origin': 'central-library', 'budget_max': 10000, 'walk_minutes': 15},
        )
        return _tool_payloads(result)

    payload = asyncio.run(main())

    assert [item["name"] for item in payload] == ["버짓김밥"]

    clear_settings_cache()


def test_mcp_public_empty_classrooms_tool_supports_building_alias(app_env, monkeypatch):
    pytest.importorskip('mcp.server.fastmcp')
    init_db()
    seed_demo(force=True)
    with connection() as conn:
        replace_courses(
            conn,
            [
                {
                    "year": 2026,
                    "semester": 1,
                    "code": "CSE332",
                    "title": "데이터베이스",
                    "professor": "김가톨",
                    "department": "컴퓨터정보공학부",
                    "section": "01",
                    "day_of_week": "월",
                    "period_start": 5,
                    "period_end": 6,
                    "room": "N201",
                    "raw_schedule": "월5~6(N201)",
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                }
            ],
        )
    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    clear_settings_cache()

    async def main():
        mcp = build_mcp()
        result = await mcp.call_tool(
            'tool_list_estimated_empty_classrooms',
            {'building': 'N관', 'at': '2026-03-16T10:15:00+09:00'},
        )
        return _tool_payloads(result)[0]

    payload = asyncio.run(main())

    assert payload["building"]["slug"] == "nichols-hall"
    assert payload["availability_mode"] == "estimated"
    assert payload["estimate_note"].startswith("공식 시간표 기준 예상 공실입니다.")
    assert payload["items"][0]["room"] == "N201"
    assert payload["items"][0]["availability_mode"] == "estimated"
    assert payload["items"][0]["next_occupied_at"] == "2026-03-16T13:00:00+09:00"

    clear_settings_cache()


def test_mcp_public_empty_classrooms_tool_accepts_kim_sou_hwan_hall(app_env, monkeypatch):
    pytest.importorskip('mcp.server.fastmcp')
    init_db()
    seed_demo(force=True)
    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    clear_settings_cache()

    async def main():
        mcp = build_mcp()
        result = await mcp.call_tool(
            'tool_list_estimated_empty_classrooms',
            {'building': '김수환관', 'at': '2026-03-16T10:15:00+09:00'},
        )
        return _tool_payloads(result)[0]

    payload = asyncio.run(main())

    assert payload["building"]["slug"] == "kim-sou-hwan-hall"
    assert payload["availability_mode"] == "estimated"
    assert payload["items"]
    assert all(item["room"].startswith("K") for item in payload["items"])

    clear_settings_cache()


def test_mcp_public_empty_classrooms_tool_prefers_official_realtime_when_available(
    app_env,
    monkeypatch,
):
    pytest.importorskip('mcp.server.fastmcp')
    init_db()
    seed_demo(force=True)
    with connection() as conn:
        replace_courses(
            conn,
            [
                {
                    "year": 2026,
                    "semester": 1,
                    "code": "CSE110",
                    "title": "컴퓨팅사고",
                    "professor": "테스트교수",
                    "department": "컴퓨터정보공학부",
                    "section": "01",
                    "day_of_week": "월",
                    "period_start": 2,
                    "period_end": 3,
                    "room": "N101",
                    "raw_schedule": "월2~3(N101)",
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
                {
                    "year": 2026,
                    "semester": 1,
                    "code": "CSE332",
                    "title": "데이터베이스",
                    "professor": "김가톨",
                    "department": "컴퓨터정보공학부",
                    "section": "01",
                    "day_of_week": "월",
                    "period_start": 5,
                    "period_end": 6,
                    "room": "N201",
                    "raw_schedule": "월5~6(N201)",
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                },
            ],
        )

    class RealtimeSource:
        def fetch_availability(self, *, building, at, year, semester):
            return [
                {
                    "room": "N101",
                    "available_now": True,
                    "source_observed_at": "2026-03-16T10:10:00+09:00",
                },
                {
                    "room": "N201",
                    "available_now": False,
                    "source_observed_at": "2026-03-16T10:10:00+09:00",
                },
            ]

    monkeypatch.setattr(
        "songsim_campus.services._get_official_classroom_availability_source",
        lambda: RealtimeSource(),
    )
    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    clear_settings_cache()

    async def main():
        mcp = build_mcp()
        result = await mcp.call_tool(
            'tool_list_estimated_empty_classrooms',
            {'building': '니콜스관', 'at': '2026-03-16T10:15:00+09:00'},
        )
        return _tool_payloads(result)[0]

    payload = asyncio.run(main())

    assert payload["availability_mode"] == "realtime"
    assert payload["observed_at"] == "2026-03-16T10:10:00+09:00"
    assert "공식 실시간 공실" in payload["estimate_note"]
    assert [item["room"] for item in payload["items"]] == ["N101"]
    assert payload["items"][0]["availability_mode"] == "realtime"
    assert payload["items"][0]["source_observed_at"] == "2026-03-16T10:10:00+09:00"

    clear_settings_cache()


def test_mcp_public_readonly_tools_return_structured_errors(app_env, monkeypatch):
    pytest.importorskip('mcp.server.fastmcp')
    init_db()
    seed_demo(force=True)
    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    clear_settings_cache()

    async def main():
        mcp = build_mcp()
        missing_place = await mcp.call_tool('tool_get_place', {'identifier': 'missing-place'})
        invalid_timestamp = await mcp.call_tool(
            'tool_find_nearby_restaurants',
            {'origin': 'central-library', 'at': 'not-a-timestamp'},
        )
        return _tool_payloads(missing_place)[0], _tool_payloads(invalid_timestamp)[0]

    missing_place_payload, invalid_timestamp_payload = asyncio.run(main())

    assert missing_place_payload["type"] == "not_found"
    assert missing_place_payload["error"] == missing_place_payload["message"]
    assert "missing-place" in missing_place_payload["message"]

    assert invalid_timestamp_payload["type"] == "invalid_request"
    assert invalid_timestamp_payload["error"] == invalid_timestamp_payload["message"]
    assert "ISO 8601" in invalid_timestamp_payload["message"]

    clear_settings_cache()
