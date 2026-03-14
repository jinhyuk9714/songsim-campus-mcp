from __future__ import annotations

import asyncio
import json

import pytest

from songsim_campus.db import connection, init_db
from songsim_campus.mcp_server import build_mcp
from songsim_campus.repo import replace_courses
from songsim_campus.seed import seed_demo
from songsim_campus.services import refresh_transport_guides_from_location_page


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
