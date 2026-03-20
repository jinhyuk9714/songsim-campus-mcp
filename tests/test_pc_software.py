from __future__ import annotations

from pathlib import Path

from songsim_campus.ingest.pc_software import (
    OFFICIAL_PC_SOFTWARE_URL,
    PCSoftwareSource,
    search_pc_software_entries,
)

FIXTURES_DIR = Path(__file__).with_name("fixtures")


def _fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


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
