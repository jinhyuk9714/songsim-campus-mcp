from __future__ import annotations

from pathlib import Path

from songsim_campus.ingest.campus_life_support_guides import (
    HealthCenterGuideSource,
    LostFoundGuideSource,
    ParkingGuideSource,
)

FIXTURES_DIR = Path(__file__).with_name("fixtures")


def _fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def test_campus_life_support_source_defaults() -> None:
    health = HealthCenterGuideSource()
    lost_found = LostFoundGuideSource()
    parking = ParkingGuideSource()

    assert health.topic == "health_center"
    assert lost_found.topic == "lost_found"
    assert parking.topic == "parking"
    assert health.source_tag == "cuk_campus_life_support_guides"
    assert lost_found.source_tag == "cuk_campus_life_support_guides"
    assert parking.source_tag == "cuk_campus_life_support_guides"
    assert health.url.endswith("/campuslife/health.do")
    assert lost_found.url.endswith("/campuslife/find.do")
    assert parking.url.endswith("/about/location_songsim.do")


def test_health_center_guide_parser_extracts_expected_core_details() -> None:
    rows = HealthCenterGuideSource().parse(
        _fixture("health.do.html"),
        fetched_at="2026-03-20T00:00:00+09:00",
    )

    assert [row["title"] for row in rows] == ["보건실"]
    row = rows[0]
    assert row["topic"] == "health_center"
    assert row["source_tag"] == "cuk_campus_life_support_guides"
    assert row["summary"].startswith("보건실은 학생과 교직원의 건강을 유지ㆍ증진")
    assert any(step == "위치: 비르투스관 1층 104호" for step in row["steps"])
    assert any(
        step == "운영시간: 08:30 ~ 17:30 (점심시간 12시 ~ 13시)"
        for step in row["steps"]
    )
    assert any(
        "트리니티 → 보건실 → 방문시간, 방문목적 접수 후 방문" in step
        for step in row["steps"]
    )
    assert any(step == "응급처치" for step in row["steps"])
    assert any(step == "목발, 휠체어 의료보조기 대여" for step in row["steps"])
    assert row["links"]
    assert row["links"][0]["label"] == "보건실 방문접수 바로가기"


def test_lost_found_guide_parser_extracts_expected_core_details() -> None:
    rows = LostFoundGuideSource().parse(
        _fixture("find.do.html"),
        fetched_at="2026-03-20T00:00:00+09:00",
    )

    assert [row["title"] for row in rows] == ["유실물 찾기"]
    row = rows[0]
    assert row["topic"] == "lost_found"
    assert row["source_tag"] == "cuk_campus_life_support_guides"
    assert row["summary"] == (
        "유실물을 취득한 자는 관리부서인 학생지원팀(N109)에 유실물을 인계할 수 있습니다."
    )
    assert any("소유자 신분 확인" in step for step in row["steps"])
    assert any("유실물 정보를 게시하고 있습니다" in step for step in row["steps"])
    assert any("6개월 간 학생지원팀에 보관" in step for step in row["steps"])


def test_parking_guide_parser_extracts_expected_core_details() -> None:
    rows = ParkingGuideSource().parse(
        _fixture("location_songsim.do.html"),
        fetched_at="2026-03-20T00:00:00+09:00",
    )

    assert [row["title"] for row in rows] == ["주차요금안내"]
    row = rows[0]
    assert row["topic"] == "parking"
    assert row["source_tag"] == "cuk_campus_life_support_guides"
    assert row["summary"].startswith("교직원, 학생(학부, 대학원생)")
    assert any("정기권 발급 준비 서류" in step for step in row["steps"])
    assert any("할인권" in step for step in row["steps"])
    assert any("일반차량" in step for step in row["steps"])
    assert any("주차관리실(K102호 / K관 1층 안내데스크 옆)" in step for step in row["steps"])
