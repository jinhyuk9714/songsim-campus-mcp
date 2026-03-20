from __future__ import annotations

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from songsim_campus import repo
from songsim_campus.api import create_app
from songsim_campus.db import connection, init_db
from songsim_campus.mcp_server import build_mcp
from songsim_campus.settings import clear_settings_cache


def _row(
    *,
    topic: str,
    title: str,
    summary: str,
    source_url: str,
) -> dict[str, object]:
    return {
        "topic": topic,
        "title": title,
        "summary": summary,
        "steps": [f"{title} 단계"],
        "links": [{"label": title, "url": source_url}],
        "source_url": source_url,
        "source_tag": "cuk_student_exchange_guides",
        "last_synced_at": "2026-03-20T00:00:00+09:00",
    }


def _tool_payloads(result) -> list[dict[str, object]]:
    return [json.loads(item.text) for item in result]


def test_student_exchange_guides_http_route_filters_and_rejects_invalid_topic(app_env):
    init_db()
    with connection() as conn:
        repo.replace_student_exchange_guides(
            conn,
            [
                _row(
                    topic="domestic_credit_exchange",
                    title="신청대상",
                    summary="국내 학점교류 신청대상",
                    source_url="https://www.catholic.ac.kr/ko/support/exchange_domestic1.do",
                ),
                _row(
                    topic="exchange_programs",
                    title="해외인턴십 프로그램",
                    summary="해외 교류프로그램",
                    source_url="https://www.catholic.ac.kr/ko/support/exchange_oversea3.do",
                ),
            ],
        )

    app = create_app()
    with TestClient(app) as client:
        response = client.get(
            "/student-exchange-guides",
            params={"topic": "exchange_programs", "limit": 5},
        )
        invalid = client.get("/student-exchange-guides", params={"topic": "unknown"})

    assert response.status_code == 200
    payload = response.json()
    assert [item["topic"] for item in payload] == ["exchange_programs"]
    assert payload[0]["title"] == "해외인턴십 프로그램"
    assert invalid.status_code == 400


def test_student_exchange_guides_public_mcp_resource_and_tool_share_service_data(
    app_env,
    monkeypatch: pytest.MonkeyPatch,
):
    pytest.importorskip("mcp.server.fastmcp")
    init_db()
    with connection() as conn:
        repo.replace_student_exchange_guides(
            conn,
            [
                _row(
                    topic="exchange_student",
                    title="상호교환 프로그램",
                    summary="해외 교환학생 프로그램",
                    source_url="https://www.catholic.ac.kr/ko/support/exchange_oversea2.do",
                )
            ],
        )

    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    clear_settings_cache()

    async def main():
        mcp = build_mcp()
        tool_result = await mcp.call_tool(
            "tool_list_student_exchange_guides",
            {"topic": "exchange_student", "limit": 5},
        )
        resource_result = await mcp.read_resource("songsim://student-exchange-guide")
        return tool_result, list(resource_result)

    tool_result, resource_result = asyncio.run(main())
    tool_payload = _tool_payloads(tool_result)[0]
    resource_payload = json.loads(resource_result[0].content)

    assert tool_payload["topic"] == "exchange_student"
    assert tool_payload["guide_summary"] == "해외 교환학생 프로그램"
    assert resource_payload[0]["topic"] == "exchange_student"
    assert resource_payload[0]["source_tag"] == "cuk_student_exchange_guides"

    clear_settings_cache()
