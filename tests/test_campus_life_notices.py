from __future__ import annotations

from pathlib import Path

from songsim_campus.ingest.official_sources import (
    CampusLifeEventsNoticeBoardSource,
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


def test_events_notice_board_list_parser_extracts_card_rows_and_metadata():
    source = CampusLifeEventsNoticeBoardSource()

    rows = source.parse_list(_fixture("notice_event_list.html"))

    assert rows == [
        {
            "topic": "events",
            "article_no": "266521",
            "title": "[음악과] 『개교 170주년 기념』성심 오케스트라 연주회",
            "published_at": "2025-11-28",
            "source_url": "https://www.catholic.ac.kr/ko/campuslife/notice_event.do?mode=view&articleNo=266521&article.offset=0&articleLimit=16",
            "source_tag": "cuk_campus_life_notices",
        },
        {
            "topic": "events",
            "article_no": "266278",
            "title": "[경영학과] Top Tier 커리어 마스터 클래스 특강",
            "published_at": "2025-11-20",
            "source_url": "https://www.catholic.ac.kr/ko/campuslife/notice_event.do?mode=view&articleNo=266278&article.offset=0&articleLimit=16",
            "source_tag": "cuk_campus_life_notices",
        },
    ]


def test_events_notice_board_detail_parser_extracts_summary_and_source_metadata():
    source = CampusLifeEventsNoticeBoardSource()

    parsed = source.parse_detail(
        _fixture("notice_event_detail.html"),
        default_title="[음악과] 『개교 170주년 기념』성심 오케스트라 연주회",
        default_category="행사안내",
        default_summary="",
        default_published_at="2025-11-28",
        default_source_url="https://www.catholic.ac.kr/ko/campuslife/notice_event.do?mode=view&articleNo=266521&article.offset=0&articleLimit=16",
    )

    assert parsed == {
        "topic": "events",
        "title": "[음악과] 『개교 170주년 기념』성심 오케스트라 연주회",
        "published_at": "2025-11-28",
        "summary": (
            "음악과에서 『개교 170주년 기념』성심 오케스트라 연주회를 개최하오니 많은 관심과 참여 "
            "부탁드립니다. "
            "□ 일정 - 2025년 11월 28일(금) 19시 □ 장소 - 콘서트홀 □ 참여 방법 - 전석 초대"
        ),
        "source_url": "https://www.catholic.ac.kr/ko/campuslife/notice_event.do?mode=view&articleNo=266521&article.offset=0&articleLimit=16",
        "source_tag": "cuk_campus_life_notices",
    }
