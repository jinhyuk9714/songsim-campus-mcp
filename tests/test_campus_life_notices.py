from __future__ import annotations

from pathlib import Path

from songsim_campus.ingest.official_sources import (
    CampusLifeOutsideAgenciesNoticeBoardSource,
)

FIXTURES_DIR = Path(__file__).with_name("fixtures")


def _fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def test_outside_agencies_notice_board_list_parser_extracts_rows_and_metadata():
    source = CampusLifeOutsideAgenciesNoticeBoardSource()

    rows = source.parse_list(_fixture("notice_outside_list.html"))

    assert rows == [
        {
            "topic": "outside_agencies",
            "article_no": "269665",
            "title": "[인천병무지청] 2026년 4월 각 군 모집일정 안내",
            "published_at": "2026-03-20",
            "source_url": "https://www.catholic.ac.kr/ko/campuslife/notice_outside.do?mode=view&articleNo=269665&article.offset=0&articleLimit=10",
            "source_tag": "cuk_campus_life_notices",
        },
        {
            "topic": "outside_agencies",
            "article_no": "269662",
            "title": "부천시일시청소년쉼터 거리상담 자원활동가 모집 안내",
            "published_at": "2026-03-20",
            "source_url": "https://www.catholic.ac.kr/ko/campuslife/notice_outside.do?mode=view&articleNo=269662&article.offset=0&articleLimit=10",
            "source_tag": "cuk_campus_life_notices",
        },
    ]


def test_outside_agencies_notice_board_detail_parser_extracts_summary_and_source_metadata():
    source = CampusLifeOutsideAgenciesNoticeBoardSource()

    parsed = source.parse_detail(
        _fixture("notice_outside_detail.html"),
        default_title="[인천병무지청] 2026년 4월 각 군 모집일정 안내",
        default_category="외부기관공지",
        default_summary="",
        default_published_at="2026-03-20",
        default_source_url="https://www.catholic.ac.kr/ko/campuslife/notice_outside.do?mode=view&articleNo=269665&article.offset=0&articleLimit=10",
    )

    assert parsed == {
        "topic": "outside_agencies",
        "title": "[인천병무지청] 2026년 4월 각 군 모집일정 안내",
        "published_at": "2026-03-20",
        "summary": "접수기간: 2026.3.27.(금) 14시 ~ 2026.4.2.(목) 14시 지원방법: 병무청 누리집",
        "source_url": "https://www.catholic.ac.kr/ko/campuslife/notice_outside.do?mode=view&articleNo=269665&article.offset=0&articleLimit=10",
        "source_tag": "cuk_campus_life_notices",
    }
