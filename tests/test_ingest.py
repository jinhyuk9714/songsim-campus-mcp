from __future__ import annotations

from pathlib import Path

from songsim_campus.ingest.official_sources import (
    CampusFacilitiesSource,
    CampusMapSource,
    CourseCatalogSource,
    LibraryHoursSource,
    NoticeSource,
    TransportGuideSource,
    classify_notice_category,
)

FIXTURES_DIR = Path(__file__).with_name("fixtures")


def _fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def test_campus_map_discovers_place_list_endpoint():
    source = CampusMapSource("https://www.catholic.ac.kr/ko/about/campus-map.do")

    url = source.discover_place_list_url(_fixture("campus_map_page.html"), campus="1")

    assert url == "https://www.catholic.ac.kr/ko/about/campus-map.do?mode=getPlaceListByCondition&campus=1"


def test_campus_map_parser_normalizes_aliases_and_missing_coordinates():
    source = CampusMapSource("https://www.catholic.ac.kr/ko/about/campus-map.do")

    rows = source.parse_place_list(
        _fixture("campus_map_places.json"),
        fetched_at="2026-03-13T09:00:00+09:00",
    )

    assert rows[0]["slug"] == "main-gate"
    assert rows[0]["category"] == "gate"

    library = next(item for item in rows if item["slug"] == "central-library")
    assert library["category"] == "library"
    assert "베리타스관" in library["aliases"]
    assert "중앙도서관" in library["aliases"]
    assert "L관" in library["aliases"]

    trail = next(item for item in rows if item["name"] == "산책로")
    assert trail["latitude"] is None
    assert trail["longitude"] is None


def test_course_parser_extracts_single_schedule_fields():
    source = CourseCatalogSource("https://www.catholic.ac.kr/ko/support/subject.do")

    rows = source.parse(
        _fixture("subject_results.html"),
        fetched_at="2026-03-13T09:00:00+09:00",
    )

    first = rows[0]
    assert first["year"] == 2026
    assert first["semester"] == 1
    assert first["code"] == "03149"
    assert first["title"] == "자료구조"
    assert first["professor"] == "박정흠"
    assert first["day_of_week"] == "화"
    assert first["period_start"] == 2
    assert first["period_end"] == 3
    assert first["room"] == "BA203"
    assert first["raw_schedule"] == "화2~3(BA203)"


def test_course_parser_preserves_raw_schedule_for_multi_slot_rows():
    source = CourseCatalogSource("https://www.catholic.ac.kr/ko/support/subject.do")

    rows = source.parse(
        _fixture("subject_results.html"),
        fetched_at="2026-03-13T09:00:00+09:00",
    )

    second = rows[1]
    assert second["raw_schedule"] == "화2~3(BA203), 목3(BA203)"
    assert second["day_of_week"] is None
    assert second["period_start"] is None
    assert second["period_end"] is None
    assert second["room"] is None


def test_course_parser_handles_schedule_without_room():
    source = CourseCatalogSource("https://www.catholic.ac.kr/ko/support/subject.do")

    rows = source.parse(
        _fixture("subject_results.html"),
        fetched_at="2026-03-13T09:00:00+09:00",
    )

    third = rows[2]
    assert third["day_of_week"] == "금"
    assert third["period_start"] == 5
    assert third["period_end"] == 6
    assert third["room"] is None


def test_notice_list_parser_extracts_dates_and_absolute_urls():
    source = NoticeSource("https://www.catholic.ac.kr/ko/campuslife/notice.do")

    rows = source.parse_list(_fixture("notice_list.html"))

    assert rows[0]["title"] == "2026학년도 1학기 가족장학금 신청 안내"
    assert rows[0]["published_at"] == "2026-03-12"
    assert rows[0]["source_url"] == "https://www.catholic.ac.kr/ko/campuslife/notice.do?mode=view&articleNo=1001&article.offset=0&articleLimit=10"


def test_notice_detail_parser_builds_summary_and_classifies_rules():
    source = NoticeSource("https://www.catholic.ac.kr/ko/campuslife/notice.do")

    parsed = source.parse_detail(
        _fixture("notice_detail_scholarship.html"),
        default_title="2026학년도 1학기 가족장학금 신청 안내",
        default_category="학사",
    )

    assert parsed["published_at"] == "2026-03-12"
    assert parsed["summary"].startswith("2026학년도 1학기 가족장학금 신청을 원하는 학생은")
    assert parsed["category"] == "scholarship"


def test_notice_category_rules_cover_cafeteria_keywords():
    assert (
        classify_notice_category(
            title="천원의 아침밥 운영 일정 안내",
            body="학생식당 조식 이용 방법과 운영 시간을 안내합니다.",
            board_category="생활",
        )
        == "cafeteria"
    )


def test_library_hours_parser_extracts_room_labels_and_schedules():
    source = LibraryHoursSource("https://library.catholic.ac.kr/webcontent/info/45")
    shared_room_hours = (
        "학기중 평일 09:00-21:00 / 토요일 09:00-13:00 | "
        "방학중 평일 09:00-17:00 / 토요일 휴 실 | 공휴일 휴실"
    )

    rows = source.parse(
        _fixture("library_hours.html"),
        fetched_at="2026-03-13T09:00:00+09:00",
    )

    assert rows == [
        {
            "place_name": "중앙도서관",
            "opening_hours": {
                "대출반납실": shared_room_hours,
                "제1,2자료실": shared_room_hours,
                "리서치커먼스": shared_room_hours,
                "제1자유열람실": "24시간 개방 | 연중 무휴",
                "제2자유열람실": "08:00 ~ 23:00 | 연중 무휴",
            },
            "source_tag": "cuk_library_hours",
            "last_synced_at": "2026-03-13T09:00:00+09:00",
        }
    ]


def test_facility_hours_parser_extracts_cards_and_table_rows():
    source = CampusFacilitiesSource("https://www.catholic.ac.kr/ko/campuslife/restaurant.do")

    rows = source.parse(
        _fixture("facility_hours.html"),
        fetched_at="2026-03-13T09:00:00+09:00",
    )

    assert rows[0]["facility_name"] == "Buon Pranzo 부온 프란조"
    assert rows[0]["location"] == "학생미래인재관 2층"
    assert rows[0]["hours_text"] == "중식 11:30 ~ 14:00"
    assert rows[0]["category"] == "식당안내"

    cafe = next(item for item in rows if item["facility_name"] == "카페드림")
    assert cafe["location"] == "중앙도서관 2층"
    assert cafe["hours_text"] == "평일 08:00~19:00 토 10:00~16:00 (일/공휴일휴무)"

    market = next(item for item in rows if item["facility_name"] == "CU")
    assert market["category"] == "편의점"
    assert market["hours_text"].endswith("(야간 무인으로 24시간 운영)")


def test_transport_parser_extracts_modes_summaries_and_steps():
    source = TransportGuideSource("https://www.catholic.ac.kr/ko/about/location_songsim.do")

    rows = source.parse(
        _fixture("transport_page.html"),
        fetched_at="2026-03-13T09:00:00+09:00",
    )

    assert rows[0]["mode"] == "campus"
    assert rows[0]["title"] == "성심교정"
    assert rows[0]["summary"] == "14662 경기도 부천시 원미구 지봉로 43 / 02-2164-4114"

    subway = next(item for item in rows if item["title"] == "1호선")
    assert subway["mode"] == "subway"
    assert "역곡역 2번 출구" in subway["summary"]
    assert subway["steps"] == ["인천역 ↔ 역곡역 : 35분 소요", "서울역 ↔ 역곡역 : 30분 소요"]

    bus = next(item for item in rows if item["title"] == "시내버스")
    assert bus["mode"] == "bus"
    assert bus["steps"][-1] == "후문 기준 : [금강맨션] 정류장 하차"
