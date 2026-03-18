from __future__ import annotations

from songsim_campus.mcp_public_serializers import (
    format_opening_hours_preview,
    restaurant_price_hint,
    serialize_public_certificate_guide,
    serialize_public_course,
    serialize_public_error,
    truncate_preview,
)
from songsim_campus.schemas import CertificateGuide, Course
from songsim_campus.services import InvalidRequestError, NotFoundError


def test_truncate_preview_normalizes_whitespace_and_adds_ellipsis():
    text = "  학생   안내   문장입니다. \n 다음   줄도  포함됩니다.  "

    assert truncate_preview(text, limit=19) == "학생 안내 문장입니다. 다음..."


def test_format_opening_hours_preview_uses_first_two_items_in_order():
    opening_hours = {
        "mon-fri": "08:00-18:00",
        "sat": "09:00-13:00",
        "sun": "closed",
    }

    assert (
        format_opening_hours_preview(opening_hours)
        == "mon-fri: 08:00-18:00 / sat: 09:00-13:00"
    )


def test_restaurant_price_hint_formats_expected_ranges():
    assert restaurant_price_hint(6000, 6000) == "6,000원"
    assert restaurant_price_hint(6000, 9000) == "6,000~9,000원"
    assert restaurant_price_hint(6000, None) == "6,000원부터"
    assert restaurant_price_hint(None, 9000) == "9,000원 이하"
    assert restaurant_price_hint(None, None) is None


def test_serialize_public_course_prefers_raw_schedule_in_summary():
    course = Course(
        id=1,
        year=2026,
        semester=1,
        code="CSE332",
        title="데이터베이스",
        professor="김가톨",
        day_of_week="월",
        period_start=5,
        period_end=6,
        room="N201",
        raw_schedule="월5~6(N201)",
        source_tag="test",
        last_synced_at="2026-03-18T10:00:00+09:00",
    )

    payload = serialize_public_course(course)

    assert payload["course_summary"] == "데이터베이스 / 김가톨 / 월5~6(N201)"


def test_serialize_public_certificate_guide_falls_back_to_first_step_summary():
    guide = CertificateGuide(
        id=1,
        title="인터넷 증명발급",
        summary="",
        steps=["증명 발급 사이트에 로그인합니다.", "수수료를 결제합니다."],
        source_url="https://example.com/certificate",
        source_tag="test",
        last_synced_at="2026-03-18T10:00:00+09:00",
    )

    payload = serialize_public_certificate_guide(guide)

    assert payload["guide_summary"] == "증명 발급 사이트에 로그인합니다."


def test_serialize_public_error_distinguishes_not_found_and_invalid_request():
    missing = serialize_public_error(NotFoundError("missing"))
    invalid = serialize_public_error(InvalidRequestError("bad request"))

    assert missing == {
        "error": "missing",
        "type": "not_found",
        "message": "missing",
    }
    assert invalid == {
        "error": "bad request",
        "type": "invalid_request",
        "message": "bad request",
    }
