from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from songsim_campus import services
from songsim_campus.db import connection, init_db
from songsim_campus.ingest.pc_software import (
    OFFICIAL_PC_SOFTWARE_URL,
    PCSoftwareSource,
    search_pc_software_entries,
)
from songsim_campus.mcp_server import build_mcp
from songsim_campus.services import (
    refresh_pc_software_entries_from_source,
    run_admin_sync,
)
from songsim_campus.services import (
    search_pc_software_entries as search_pc_software_entries_service,
)
from songsim_campus.settings import clear_settings_cache

FIXTURES_DIR = Path(__file__).with_name("fixtures")


def _fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def _pc_row(
    *,
    room: str,
    pc_count: int | None,
    software_list: list[str],
) -> dict[str, object]:
    return {
        "room": room,
        "pc_count": pc_count,
        "software_list": software_list,
        "source_url": OFFICIAL_PC_SOFTWARE_URL,
        "source_tag": "cuk_pc_software",
        "last_synced_at": "2026-03-20T00:00:00+09:00",
    }


def test_pc_software_source_parses_maria_and_library_rows() -> None:
    rows = PCSoftwareSource().parse(
        _fixture("pc_software.html"),
        fetched_at="2026-03-20T00:00:00+09:00",
    )

    assert len(rows) == 4
    assert rows[0]["room"] == "마리아관 1실습실 (M307)"
    assert rows[0]["pc_count"] == 51
    assert rows[0]["software_list"] == [
        "한글 2014",
        "MS-Office 2013",
        "SPSS 25",
        "SAS 9.4",
        "Visual Studio 2015",
        "포토샵 CS6",
        "일러스트레이터 CS6",
        "Acrobat Reader DC",
    ]
    assert rows[0]["source_url"] == OFFICIAL_PC_SOFTWARE_URL
    assert rows[0]["source_tag"] == "cuk_pc_software"

    media_room = rows[-1]
    assert media_room["room"] == "중앙도서관 미디어룸 도서관 로비"
    assert media_room["pc_count"] == 49
    assert "포토샵 CS6" in media_room["software_list"][2]
    assert media_room["software_list"][-1] == "일러스트레이터 CS6 Chorme"


def test_pc_software_search_prefers_software_matches_over_room_matches() -> None:
    rows = PCSoftwareSource().parse(
        _fixture("pc_software.html"),
        fetched_at="2026-03-20T00:00:00+09:00",
    )

    spss = search_pc_software_entries(rows, query="SPSS", limit=20)
    photoshop = search_pc_software_entries(rows, query="Photoshop", limit=20)
    visual_studio = search_pc_software_entries(rows, query="Visual Studio", limit=20)
    maria = search_pc_software_entries(rows, query="마리아관", limit=20)
    default_rows = search_pc_software_entries(rows, query=None, limit=20)

    assert [row["room"] for row in spss] == [
        "마리아관 1실습실 (M307)",
        "마리아관 2실습실 (M306)",
        "마리아관 3실습실 (M304)",
    ]
    assert [row["room"] for row in photoshop][:3] == [
        "마리아관 1실습실 (M307)",
        "마리아관 2실습실 (M306)",
        "마리아관 3실습실 (M304)",
    ]
    assert [row["room"] for row in visual_studio] == [
        "마리아관 1실습실 (M307)",
        "마리아관 2실습실 (M306)",
        "마리아관 3실습실 (M304)",
    ]
    assert [row["room"] for row in maria] == [
        "마리아관 1실습실 (M307)",
        "마리아관 2실습실 (M306)",
        "마리아관 3실습실 (M304)",
    ]
    assert [row["room"] for row in default_rows] == [
        "마리아관 1실습실 (M307)",
        "마리아관 2실습실 (M306)",
        "마리아관 3실습실 (M304)",
        "중앙도서관 미디어룸 도서관 로비",
    ]


def test_pc_software_entries_refresh_replace_and_search(app_env) -> None:
    init_db()

    class DummySource:
        def fetch(self) -> str:
            return "<pc-software />"

        def parse(self, html: str, *, fetched_at: str):
            assert html == "<pc-software />"
            return [
                {
                    **_pc_row(
                        room="마리아관 1실습실 (M307)",
                        pc_count=51,
                        software_list=["SPSS 25", "포토샵 CS6"],
                    ),
                    "last_synced_at": fetched_at,
                },
                {
                    **_pc_row(
                        room="마리아관 2실습실 (M306)",
                        pc_count=51,
                        software_list=["Visual Studio 2015", "SAP"],
                    ),
                    "last_synced_at": fetched_at,
                },
                {
                    **_pc_row(
                        room="중앙도서관 미디어룸 도서관 로비",
                        pc_count=49,
                        software_list=["포토샵 CS6"],
                    ),
                    "last_synced_at": fetched_at,
                },
            ]

    with connection() as conn:
        refresh_pc_software_entries_from_source(conn, source=DummySource())
        spss = search_pc_software_entries_service(conn, query="SPSS", limit=20)
        photoshop = search_pc_software_entries_service(conn, query="Photoshop", limit=20)
        visual_studio = search_pc_software_entries_service(conn, query="Visual Studio", limit=20)
        maria = search_pc_software_entries_service(conn, query="마리아관", limit=20)

        refresh_pc_software_entries_from_source(
            conn,
            source=type(
                "SecondSource",
                (),
                {
                    "fetch": lambda self: "<pc-software />",
                    "parse": lambda self, html, *, fetched_at: [
                        {
                            **_pc_row(
                                room="중앙도서관 미디어룸 도서관 로비",
                                pc_count=49,
                                software_list=["포토샵 CS6"],
                            ),
                            "last_synced_at": fetched_at,
                        }
                    ],
                },
            )(),
        )
        replaced = search_pc_software_entries_service(conn, query=None, limit=20)

    assert [item.room for item in spss] == ["마리아관 1실습실 (M307)"]
    assert [item.room for item in photoshop] == [
        "마리아관 1실습실 (M307)",
        "중앙도서관 미디어룸 도서관 로비",
    ]
    assert [item.room for item in visual_studio] == ["마리아관 2실습실 (M306)"]
    assert [item.room for item in maria] == [
        "마리아관 1실습실 (M307)",
        "마리아관 2실습실 (M306)",
    ]
    assert [item.room for item in replaced] == ["중앙도서관 미디어룸 도서관 로비"]


def test_pc_software_dataset_is_wired_into_sync_and_readiness(app_env, monkeypatch):
    init_db()

    assert "pc_software_entries" in services.SYNC_DATASET_TABLES
    assert services.PUBLIC_READY_DATASET_POLICIES["pc_software_entries"] == "core"
    assert "pc_software_entries" in services.PUBLIC_READY_CORE_DATASETS
    assert "pc_software_entries" in services.ADMIN_SYNC_TARGETS

    monkeypatch.setattr(
        "songsim_campus.services.refresh_pc_software_entries_from_source",
        lambda conn, source=None, fetched_at=None: [],
    )

    with connection():
        run = run_admin_sync(target="pc_software_entries")

    assert run.status == "success"
    assert run.summary == {"pc_software_entries": 0}


def test_pc_software_http_and_mcp_surfaces(client, app_env, monkeypatch):
    pytest.importorskip("mcp.server.fastmcp")
    init_db()

    class DummySource:
        def fetch(self) -> str:
            return "<pc-software />"

        def parse(self, html: str, *, fetched_at: str):
            assert html == "<pc-software />"
            return [
                {
                    **_pc_row(
                        room="마리아관 1실습실 (M307)",
                        pc_count=51,
                        software_list=["SPSS 25", "포토샵 CS6"],
                    ),
                    "last_synced_at": fetched_at,
                },
                {
                    **_pc_row(
                        room="마리아관 2실습실 (M306)",
                        pc_count=51,
                        software_list=["Visual Studio 2015", "SAP"],
                    ),
                    "last_synced_at": fetched_at,
                },
            ]

    with connection() as conn:
        refresh_pc_software_entries_from_source(conn, source=DummySource())

    response = client.get("/pc-software", params={"query": "SPSS", "limit": 5})
    assert response.status_code == 200
    http_payload = response.json()
    assert http_payload[0]["room"] == "마리아관 1실습실 (M307)"
    assert http_payload[0]["source_tag"] == "cuk_pc_software"

    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    clear_settings_cache()

    async def main():
        mcp = build_mcp()
        tools = await mcp.list_tools()
        resources = await mcp.list_resources()
        tool_result = await mcp.call_tool(
            "tool_search_pc_software",
            {"query": "Visual Studio", "limit": 5},
        )
        resource_result = await mcp.read_resource("songsim://pc-software")
        return (
            {tool.name: tool.model_dump(by_alias=True) for tool in tools},
            {str(resource.uri) for resource in resources},
            json.loads(tool_result[0].text),
            json.loads(list(resource_result)[0].content),
        )

    tool_payloads, resource_uris, tool_payload, resource_payload = asyncio.run(main())
    clear_settings_cache()

    assert "tool_search_pc_software" in tool_payloads
    assert "songsim://pc-software" in resource_uris
    assert "SPSS" in tool_payloads["tool_search_pc_software"]["description"]
    assert "Visual Studio" in (
        tool_payloads["tool_search_pc_software"]["inputSchema"]["properties"]["query"]["description"]
    )
    assert tool_payload["room"] == "마리아관 2실습실 (M306)"
    assert tool_payload["software_summary"].startswith("Visual Studio")
    assert [item["room"] for item in resource_payload] == [
        "마리아관 1실습실 (M307)",
        "마리아관 2실습실 (M306)",
    ]
