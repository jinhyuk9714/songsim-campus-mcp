from __future__ import annotations

import asyncio
import json

import pytest

from songsim_campus.db import connection, init_db
from songsim_campus.mcp_server import build_mcp
from songsim_campus.repo import replace_courses, replace_restaurants, update_place_opening_hours
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
        return json.loads(result[0].text)

    payload = asyncio.run(main())

    assert payload['name'] == '알수없음식당'
    assert payload['open_now'] is None


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
