from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from songsim_campus import qa_eval, repo
from songsim_campus.db import connection, init_db
from songsim_campus.qa_eval import (
    DEFAULT_CORPUS_PATH,
    DEFAULT_WATCHLIST_PATH,
    EvalCorpusRow,
    EvalTruthRow,
    build_truth_rows,
    load_eval_rows,
    render_validation_report,
    run_evaluation,
    run_row_evaluation,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_load_eval_rows_rejects_duplicate_ids(tmp_path: Path) -> None:
    corpus_path = tmp_path / "duplicate.jsonl"
    _write_jsonl(
        corpus_path,
        [
            {
                "id": "QA001",
                "domain": "place",
                "style": "normal",
                "user_utterance": "중앙도서관 위치 알려줘",
                "api_request": {"path": "/places", "params": {"query": "중앙도서관"}},
                "expected_mcp_flow": "prompt_find_place -> tool_search_places -> tool_get_place",
                "truth_mode": "exact_value",
                "pass_rule": {"summary_kind": "places_top3"},
                "watch_policy": "none",
                "notes": "",
            },
            {
                "id": "QA001",
                "domain": "place",
                "style": "normal",
                "user_utterance": "정문 위치 알려줘",
                "api_request": {"path": "/places", "params": {"query": "정문"}},
                "expected_mcp_flow": "tool_search_places -> tool_get_place",
                "truth_mode": "exact_value",
                "pass_rule": {"summary_kind": "places_top3"},
                "watch_policy": "none",
                "notes": "",
            },
        ],
    )

    with pytest.raises(ValueError, match="Duplicate evaluation id"):
        load_eval_rows(corpus_path)


def test_load_eval_rows_rejects_invalid_truth_mode(tmp_path: Path) -> None:
    corpus_path = tmp_path / "invalid.jsonl"
    _write_jsonl(
        corpus_path,
        [
            {
                "id": "QA001",
                "domain": "place",
                "style": "normal",
                "user_utterance": "중앙도서관 위치 알려줘",
                "api_request": {"path": "/places", "params": {"query": "중앙도서관"}},
                "expected_mcp_flow": "prompt_find_place -> tool_search_places -> tool_get_place",
                "truth_mode": "made_up_mode",
                "pass_rule": {"summary_kind": "places_top3"},
                "watch_policy": "none",
                "notes": "",
            }
        ],
    )

    with pytest.raises(ValueError, match="truth_mode"):
        load_eval_rows(corpus_path)


def test_build_truth_rows_uses_database_snapshot_for_academic_support_guides(app_env: str) -> None:
    row = EvalCorpusRow.model_validate(
        {
            "id": "AG001",
            "domain": "academic_support_guides",
            "style": "normal",
            "user_utterance": "휴복학 문의 어디로 해야 해?",
            "api_request": {"path": "/academic-support-guides", "params": {"limit": 3}},
            "expected_mcp_flow": "tool_list_academic_support_guides",
            "truth_mode": "exact_value",
            "pass_rule": {"summary_kind": "academic_support_guides_top5"},
            "watch_policy": "none",
            "notes": "",
        }
    )
    init_db()
    with connection() as conn:
        repo.replace_academic_support_guides(
            conn,
            [
                {
                    "title": "휴·복학",
                    "summary": "휴·복학 관련 업무",
                    "steps": ["휴학 신청", "복학 신청"],
                    "contacts": ["02-2164-4288"],
                    "source_url": "https://www.catholic.ac.kr/ko/support/academic_contact_information.do",
                    "source_tag": "cuk_academic_support_guides",
                    "last_synced_at": "2026-03-18T10:00:00+09:00",
                }
            ],
        )

    truth_rows = build_truth_rows(
        [row],
        database_url=app_env,
        captured_at="2026-03-18T10:10:00+09:00",
    )

    assert truth_rows == [
        EvalTruthRow(
            id="AG001",
            normalized_expected=[
                {
                    "title": "휴·복학",
                    "summary": "휴·복학 관련 업무",
                    "contacts": ["02-2164-4288"],
                }
            ],
            truth_source="database_snapshot",
            captured_at="2026-03-18T10:10:00+09:00",
            stability="stable",
        )
    ]


def test_build_truth_rows_prefers_official_source_for_notices_even_with_database(
    app_env: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = EvalCorpusRow.model_validate(
        {
            "id": "NT001",
            "domain": "notices",
            "style": "normal",
            "user_utterance": "학사 공지 알려줘",
            "api_request": {
                "path": "/notices",
                "params": {"category": "academic", "limit": 3},
            },
            "expected_mcp_flow": "tool_list_latest_notices",
            "truth_mode": "set_contains",
            "pass_rule": {"summary_kind": "notices_top5"},
            "watch_policy": "none",
            "notes": "",
        }
    )

    monkeypatch.setattr(
        qa_eval,
        "_payload_from_db",
        lambda *_args, **_kwargs: pytest.fail("notices truth should not use database snapshot"),
    )
    monkeypatch.setattr(
        qa_eval,
        "_payload_from_sources",
        lambda *_args, **_kwargs: [
            {
                "title": "학사 공지 1",
                "category": "academic",
                "published_at": "2026-03-19",
            },
            {
                "title": "학사 공지 2",
                "category": "academic",
                "published_at": "2026-03-18",
            },
        ],
    )

    truth_rows = build_truth_rows(
        [row],
        database_url=app_env,
        captured_at="2026-03-19T10:10:00+09:00",
    )

    assert truth_rows == [
        EvalTruthRow(
            id="NT001",
            normalized_expected=[
                {"title": "학사 공지 1", "category": "academic", "published_at": "2026-03-19"},
                {"title": "학사 공지 2", "category": "academic", "published_at": "2026-03-18"},
            ],
            truth_source="official_source",
            captured_at="2026-03-19T10:10:00+09:00",
            stability="stable",
        )
    ]


def test_build_truth_rows_marks_watch_only_without_expected() -> None:
    row = EvalCorpusRow.model_validate(
        {
            "id": "CW001",
            "domain": "courses",
            "style": "normal",
            "user_utterance": "CSE301 과목 뭐야",
            "api_request": {
                "path": "/courses",
                "params": {"query": "CSE301", "year": 2026, "semester": 1},
            },
            "expected_mcp_flow": "tool_search_courses",
            "truth_mode": "watch_only",
            "pass_rule": {"summary_kind": "courses_top5"},
            "watch_policy": "course_source_gap",
            "notes": "",
        }
    )

    truth_rows = build_truth_rows([row], database_url=None, captured_at="2026-03-18T10:10:00+09:00")

    assert truth_rows[0].normalized_expected is None
    assert truth_rows[0].stability == "watch_only"
    assert truth_rows[0].truth_source == "watchlist"


def test_build_truth_rows_skips_facility_host_place_canary_without_database() -> None:
    row = EvalCorpusRow.model_validate(
        {
            "id": "PLF001",
            "domain": "place",
            "style": "normal",
            "user_utterance": "복사실이 어디야?",
            "api_request": {"path": "/places", "params": {"query": "복사실이 어디야?", "limit": 5}},
            "expected_mcp_flow": "tool_search_places -> tool_get_place",
            "truth_mode": "set_contains",
            "pass_rule": {"summary_kind": "places_top1_facility_host"},
            "watch_policy": "facility_search",
            "notes": "",
        }
    )

    truth_rows = build_truth_rows([row], database_url=None, captured_at="2026-03-18T10:10:00+09:00")

    assert truth_rows == [
        EvalTruthRow(
            id="PLF001",
            normalized_expected=None,
            truth_source="unavailable",
            captured_at="2026-03-18T10:10:00+09:00",
            stability="degraded_skip",
        )
    ]


def test_build_truth_rows_uses_database_snapshot_for_composite_facility_host_place(
    app_env: str,
) -> None:
    row = EvalCorpusRow.model_validate(
        {
            "id": "PLC0155",
            "domain": "place",
            "style": "composite",
            "user_utterance": "학생회관 1층 24시간 편의점 어디야?",
            "api_request": {
                "path": "/places",
                "params": {"query": "학생회관 1층 편의점", "limit": 5},
            },
            "expected_mcp_flow": "tool_search_places -> tool_get_place",
            "truth_mode": "set_contains",
            "pass_rule": {"summary_kind": "places_top1_facility_host"},
            "watch_policy": "none",
            "notes": "",
        }
    )

    init_db()
    with connection() as conn:
        repo.replace_places(
            conn,
            [
                {
                    "slug": "sophie-barat-hall",
                    "name": "학생미래인재관",
                    "category": "building",
                    "aliases": ["학생회관", "학생센터", "학생식당"],
                    "description": "",
                    "latitude": 37.486466,
                    "longitude": 126.801297,
                    "opening_hours": {},
                    "source_tag": "test",
                    "last_synced_at": "2026-03-19T12:00:00+09:00",
                }
            ],
        )
        repo.replace_campus_facilities(
            conn,
            [
                {
                    "facility_name": "CU",
                    "category": "편의점",
                    "phone": "032-343-3424",
                    "location_text": "학생회관 1층",
                    "hours_text": "평일 08:00~21:30 토,일 08:00~16:00 (야간 무인으로 24시간 운영)",
                    "place_slug": "sophie-barat-hall",
                    "source_url": "https://www.catholic.ac.kr/ko/campuslife/restaurant.do",
                    "source_tag": "cuk_facilities",
                    "last_synced_at": "2026-03-19T12:00:00+09:00",
                }
            ],
        )

    truth_rows = build_truth_rows(
        [row],
        database_url=app_env,
        captured_at="2026-03-19T12:10:00+09:00",
    )

    assert truth_rows == [
        EvalTruthRow(
            id="PLC0155",
            normalized_expected={
                "slug": "sophie-barat-hall",
                "name": "학생회관",
                "canonical_name": "학생미래인재관",
                "category": "building",
                "matched_facility": {
                    "name": "CU",
                    "location_hint": "학생회관 1층",
                },
            },
            truth_source="database_snapshot",
            captured_at="2026-03-19T12:10:00+09:00",
            stability="stable",
        )
    ]


def test_build_truth_rows_uses_official_source_for_place_query_without_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = EvalCorpusRow.model_validate(
        {
            "id": "PL001",
            "domain": "place",
            "style": "normal",
            "user_utterance": "중앙도서관 위치 알려줘",
            "api_request": {"path": "/places", "params": {"query": "중앙도서관", "limit": 3}},
            "expected_mcp_flow": "tool_search_places -> tool_get_place",
            "truth_mode": "exact_value",
            "pass_rule": {"summary_kind": "places_top3"},
            "watch_policy": "none",
            "notes": "",
        }
    )

    monkeypatch.setattr(
        qa_eval.CampusMapSource,
        "fetch_place_list",
        lambda self: "<places></places>",
    )
    monkeypatch.setattr(
        qa_eval.CampusMapSource,
        "parse_place_list",
        lambda self, _html, *, fetched_at: [
            {
                "slug": "central-library",
                "name": "베리타스관",
                "category": "library",
                "aliases": ["중앙도서관", "중도"],
                "opening_hours": {},
                "source_tag": "cuk_campus_map",
                "last_synced_at": fetched_at,
            }
        ],
    )

    truth_rows = build_truth_rows([row], database_url=None, captured_at="2026-03-19T10:00:00+09:00")

    assert truth_rows == [
        EvalTruthRow(
            id="PL001",
            normalized_expected=[
                {
                    "slug": "central-library",
                    "name": "중앙도서관",
                    "category": "library",
                }
            ],
            truth_source="official_source",
            captured_at="2026-03-19T10:00:00+09:00",
            stability="stable",
        )
    ]


def test_build_truth_rows_falls_back_to_official_source_for_unsupported_db_path(
    app_env: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = EvalCorpusRow.model_validate(
        {
            "id": "RST001",
            "domain": "restaurants",
            "style": "normal",
            "user_utterance": "중앙도서관 근처 한식집 찾아줘",
            "api_request": {
                "path": "/restaurants/nearby",
                "params": {"origin": "central-library", "limit": 3},
            },
            "expected_mcp_flow": "tool_find_nearby_restaurants",
            "truth_mode": "invariant_only",
            "pass_rule": {
                "summary_kind": "restaurants_nearby",
                "allow_empty": True,
                "required_fields": ["name", "origin"],
            },
            "watch_policy": "none",
            "notes": "",
        }
    )

    monkeypatch.setattr(
        qa_eval,
        "_payload_from_sources",
        lambda *_args, **_kwargs: [
            {
                "name": "학생식당 옆 한식집",
                "origin": "central-library",
                "category": "korean",
                "open_now": True,
            }
        ],
    )

    truth_rows = build_truth_rows(
        [row],
        database_url=app_env,
        captured_at="2026-03-19T10:30:00+09:00",
    )

    assert truth_rows == [
        EvalTruthRow(
            id="RST001",
            normalized_expected=[
                {
                    "name": "학생식당 옆 한식집",
                    "origin": "central-library",
                    "category": "korean",
                    "open_now": True,
                }
            ],
            truth_source="official_source",
            captured_at="2026-03-19T10:30:00+09:00",
            stability="stable",
        )
    ]


def test_payload_from_sources_prioritizes_songsim_academic_calendar_events() -> None:
    row = EvalCorpusRow.model_validate(
        {
            "id": "AC001",
            "domain": "academic_calendar",
            "style": "normal",
            "user_utterance": "4월 학사일정 보여줘",
            "api_request": {
                "path": "/academic-calendar",
                "params": {"academic_year": 2026, "month": 4, "limit": 5},
            },
            "expected_mcp_flow": "tool_list_academic_calendar",
            "truth_mode": "set_contains",
            "pass_rule": {"summary_kind": "academic_calendar_top5"},
            "watch_policy": "none",
            "notes": "",
        }
    )
    start_date, end_date = qa_eval._current_academic_year_bounds()
    source_cache = {
        f"academic_calendar:{start_date}:{end_date}": [
            {
                "academic_year": 2026,
                "title": "성신-only 일정",
                "start_date": "2026-04-02",
                "end_date": "2026-04-02",
                "campuses": ["성신"],
            },
            {
                "academic_year": 2026,
                "title": "성심 일정",
                "start_date": "2026-04-10",
                "end_date": "2026-04-10",
                "campuses": ["성심"],
            },
            {
                "academic_year": 2026,
                "title": "공통 일정",
                "start_date": "2026-04-05",
                "end_date": "2026-04-05",
                "campuses": ["성심", "성의", "성신"],
            },
        ]
    }

    payload = qa_eval._payload_from_sources(
        row,
        captured_at="2026-03-18T10:10:00+09:00",
        source_cache=source_cache,
    )
    summary = qa_eval._normalize_truth_payload(row, payload)

    assert summary == [
        {
            "title": "공통 일정",
            "start_date": "2026-04-05",
            "end_date": "2026-04-05",
            "campuses": ["성심", "성의", "성신"],
        },
        {
            "title": "성심 일정",
            "start_date": "2026-04-10",
            "end_date": "2026-04-10",
            "campuses": ["성심"],
        },
        {
            "title": "성신-only 일정",
            "start_date": "2026-04-02",
            "end_date": "2026-04-02",
            "campuses": ["성신"],
        },
    ]


def test_payload_from_sources_normalizes_notice_public_category_and_sorting() -> None:
    row = EvalCorpusRow.model_validate(
        {
            "id": "NT001",
            "domain": "notices",
            "style": "normal",
            "user_utterance": "장학 공지 알려줘",
            "api_request": {
                "path": "/notices",
                "params": {"category": "scholarship", "limit": 3},
            },
            "expected_mcp_flow": "tool_list_latest_notices",
            "truth_mode": "set_contains",
            "pass_rule": {"summary_kind": "notices_top5"},
            "watch_policy": "none",
            "notes": "",
        }
    )
    source_cache = {
        "notices_latest_30": [
            {
                "article_no": "101",
                "title": "older scholarship",
                "published_at": "2026-03-10",
                "summary": "",
                "labels": ["장학"],
                "raw_category": "scholarship",
                "category": "scholarship",
                "source_url": "https://example.com/101",
            },
            {
                "article_no": "103",
                "title": "newer scholarship",
                "published_at": "2026-03-17",
                "summary": "",
                "labels": ["장학"],
                "raw_category": "scholarship",
                "category": "scholarship",
                "source_url": "https://example.com/103",
            },
            {
                "article_no": "102",
                "title": "place-like notice",
                "published_at": "2026-03-16",
                "summary": "",
                "labels": ["일반"],
                "raw_category": "place",
                "category": "general",
                "source_url": "https://example.com/102",
            },
            {
                "article_no": "104",
                "title": "second scholarship",
                "published_at": "2026-03-17",
                "summary": "",
                "labels": ["장학"],
                "raw_category": "scholarship",
                "category": "scholarship",
                "source_url": "https://example.com/104",
            },
        ]
    }

    scholarship_payload = qa_eval._payload_from_sources(
        row,
        captured_at="2026-03-18T10:10:00+09:00",
        source_cache=source_cache,
    )
    scholarship_summary = qa_eval._normalize_truth_payload(row, scholarship_payload)

    assert scholarship_summary == [
        {"title": "second scholarship", "category": "scholarship", "published_at": "2026-03-17"},
        {"title": "newer scholarship", "category": "scholarship", "published_at": "2026-03-17"},
        {"title": "older scholarship", "category": "scholarship", "published_at": "2026-03-10"},
    ]

    place_row = EvalCorpusRow.model_validate(
        {
            "id": "NT002",
            "domain": "notices",
            "style": "normal",
            "user_utterance": "place 공지 알려줘",
            "api_request": {
                "path": "/notices",
                "params": {"category": "place", "limit": 1},
            },
            "expected_mcp_flow": "tool_list_latest_notices",
            "truth_mode": "set_contains",
            "pass_rule": {"summary_kind": "notices_top5"},
            "watch_policy": "none",
            "notes": "",
        }
    )

    place_payload = qa_eval._payload_from_sources(
        place_row,
        captured_at="2026-03-18T10:10:00+09:00",
        source_cache=source_cache,
    )
    place_summary = qa_eval._normalize_truth_payload(place_row, place_payload)

    assert place_summary == [
        {"title": "place-like notice", "category": "general", "published_at": "2026-03-16"}
    ]


def test_summarize_payload_places_alias_display_includes_aliases() -> None:
    payload = [
        {
            "slug": "student-center",
            "name": "학생회관",
            "canonical_name": "학생미래인재관",
            "category": "facility",
            "aliases": ["학생회관", "student center"],
            "matched_facility": None,
        }
    ]
    summary = qa_eval._summarize_payload(payload, summary_kind="places_top1_alias_display")

    assert summary == {
        "slug": "student-center",
        "name": "학생회관",
        "canonical_name": "학생미래인재관",
        "category": "facility",
        "aliases": ["학생회관", "student center"],
        "matched_facility": None,
    }


def test_run_row_evaluation_supports_exact_set_contains_invariant_and_watch() -> None:
    exact_row = EvalCorpusRow.model_validate(
        {
            "id": "PL001",
            "domain": "place",
            "style": "normal",
            "user_utterance": "중앙도서관 위치 알려줘",
            "api_request": {"path": "/places", "params": {"query": "중앙도서관"}},
            "expected_mcp_flow": "prompt_find_place -> tool_search_places -> tool_get_place",
            "truth_mode": "exact_value",
            "pass_rule": {"summary_kind": "places_top3"},
            "watch_policy": "none",
            "notes": "",
        }
    )
    contains_row = EvalCorpusRow.model_validate(
        {
            "id": "NT001",
            "domain": "notices",
            "style": "normal",
            "user_utterance": "최신 장학 공지 3개 보여줘",
            "api_request": {"path": "/notices", "params": {"category": "scholarship", "limit": 3}},
            "expected_mcp_flow": "prompt_latest_notices -> tool_list_latest_notices",
            "truth_mode": "set_contains",
            "pass_rule": {"summary_kind": "notices_top5"},
            "watch_policy": "none",
            "notes": "",
        }
    )
    invariant_row = EvalCorpusRow.model_validate(
        {
            "id": "RS001",
            "domain": "restaurants",
            "style": "composite",
            "user_utterance": "중앙도서관 근처 1만원 이하 밥집",
            "api_request": {
                "path": "/restaurants/nearby",
                "params": {"origin": "중앙도서관", "budget_max": 10000, "limit": 2},
            },
            "expected_mcp_flow": "prompt_find_nearby_restaurants -> tool_find_nearby_restaurants",
            "truth_mode": "invariant_only",
            "pass_rule": {
                "summary_kind": "restaurants_nearby",
                "allow_empty": True,
                "required_fields": ["name", "origin"],
            },
            "watch_policy": "none",
            "notes": "",
        }
    )
    watch_row = EvalCorpusRow.model_validate(
        {
            "id": "CW001",
            "domain": "courses",
            "style": "normal",
            "user_utterance": "CSE301 과목 뭐야",
            "api_request": {
                "path": "/courses",
                "params": {"query": "CSE301", "year": 2026, "semester": 1},
            },
            "expected_mcp_flow": "tool_search_courses",
            "truth_mode": "watch_only",
            "pass_rule": {"summary_kind": "courses_top5"},
            "watch_policy": "course_source_gap",
            "notes": "",
        }
    )

    exact_truth = EvalTruthRow(
        id="PL001",
        normalized_expected=[
            {"slug": "central-library", "name": "베리타스관", "category": "library"}
        ],
        truth_source="database_snapshot",
        captured_at="2026-03-18T10:10:00+09:00",
        stability="stable",
    )
    contains_truth = EvalTruthRow(
        id="NT001",
        normalized_expected=[{"title": "장학 공지", "category": "scholarship"}],
        truth_source="database_snapshot",
        captured_at="2026-03-18T10:10:00+09:00",
        stability="stable",
    )
    watch_truth = EvalTruthRow(
        id="CW001",
        normalized_expected=None,
        truth_source="watchlist",
        captured_at="2026-03-18T10:10:00+09:00",
        stability="watch_only",
    )

    exact_result = run_row_evaluation(
        exact_row,
        actual_payload=[{"slug": "central-library", "name": "베리타스관", "category": "library"}],
        truth=exact_truth,
        checked_at="2026-03-18T10:20:00+09:00",
    )
    contains_result = run_row_evaluation(
        contains_row,
        actual_payload=[
            {"title": "장학 공지", "category": "scholarship"},
            {"title": "장학 공지 2", "category": "scholarship"},
        ],
        truth=contains_truth,
        checked_at="2026-03-18T10:20:00+09:00",
    )
    invariant_result = run_row_evaluation(
        invariant_row,
        actual_payload=[{"name": "꼬밥", "origin": "central-library"}],
        truth=None,
        checked_at="2026-03-18T10:20:00+09:00",
    )
    watch_result = run_row_evaluation(
        watch_row,
        actual_payload=[],
        truth=watch_truth,
        checked_at="2026-03-18T10:20:00+09:00",
    )

    assert exact_result.verdict == "pass"
    assert contains_result.verdict == "pass"
    assert invariant_result.verdict == "pass"
    assert watch_result.verdict == "watch"


def test_run_row_evaluation_supports_place_top1_facility_host_summary() -> None:
    row = EvalCorpusRow.model_validate(
        {
            "id": "PLF001",
            "domain": "place",
            "style": "normal",
            "user_utterance": "트러스트짐 어디야?",
            "api_request": {
                "path": "/places",
                "params": {"query": "트러스트짐 어디야?", "limit": 5},
            },
            "expected_mcp_flow": "tool_search_places -> tool_get_place",
            "truth_mode": "set_contains",
            "pass_rule": {"summary_kind": "places_top1_facility_host"},
            "watch_policy": "facility_search",
            "notes": "",
        }
    )
    truth = EvalTruthRow(
        id="PLF001",
        normalized_expected={
            "slug": "kim-sou-hwan-hall",
            "name": "K관",
            "canonical_name": "김수환관",
            "matched_facility": {
                "name": "트러스트짐",
                "location_hint": "K관 1층",
            },
        },
        truth_source="database_snapshot",
        captured_at="2026-03-18T10:10:00+09:00",
        stability="stable",
    )

    result = run_row_evaluation(
        row,
        actual_payload=[
            {
                "slug": "kim-sou-hwan-hall",
                "name": "K관",
                "canonical_name": "김수환관",
                "category": "building",
                "matched_facility": {
                    "name": "트러스트짐",
                    "location_hint": "K관 1층",
                    "opening_hours": "평일 07:00~22:30",
                },
            }
        ],
        truth=truth,
        checked_at="2026-03-18T10:20:00+09:00",
    )

    assert result.verdict == "pass"
    assert result.actual_summary == {
        "slug": "kim-sou-hwan-hall",
        "name": "K관",
        "canonical_name": "김수환관",
        "category": "building",
        "matched_facility": {
            "name": "트러스트짐",
            "location_hint": "K관 1층",
        },
    }


def test_render_validation_report_separates_watchlist() -> None:
    rows = [
        EvalCorpusRow.model_validate(
            {
                "id": "PL001",
                "domain": "place",
                "style": "normal",
                "user_utterance": "중앙도서관 위치 알려줘",
                "api_request": {"path": "/places", "params": {"query": "중앙도서관"}},
                "expected_mcp_flow": "prompt_find_place -> tool_search_places -> tool_get_place",
                "truth_mode": "exact_value",
                "pass_rule": {"summary_kind": "places_top3"},
                "watch_policy": "none",
                "notes": "",
            }
        ),
        EvalCorpusRow.model_validate(
            {
                "id": "CW001",
                "domain": "courses",
                "style": "normal",
                "user_utterance": "CSE301 과목 뭐야",
                "api_request": {
                    "path": "/courses",
                    "params": {"query": "CSE301", "year": 2026, "semester": 1},
                },
                "expected_mcp_flow": "tool_search_courses",
                "truth_mode": "watch_only",
                "pass_rule": {"summary_kind": "courses_top5"},
                "watch_policy": "course_source_gap",
                "notes": "",
            }
        ),
    ]
    results = [
        {
            "id": "PL001",
            "status": "completed",
            "verdict": "pass",
            "actual_summary": [{"slug": "central-library"}],
            "comparison": "exact_match",
            "truth_source": "database_snapshot",
            "checked_at": "2026-03-18T10:20:00+09:00",
        },
        {
            "id": "CW001",
            "status": "completed",
            "verdict": "watch",
            "actual_summary": [],
            "comparison": "watch_only",
            "truth_source": "watchlist",
            "checked_at": "2026-03-18T10:20:00+09:00",
        },
    ]

    report = render_validation_report(
        rows=rows,
        results=results,
        checked_at="2026-03-18T10:20:00+09:00",
        base_url="https://songsim-public-api.onrender.com",
    )

    assert "hard fail 0" in report.lower()
    assert "Watchlist (hard fail 제외)" in report
    assert "CW001" in report


def test_render_validation_report_includes_registration_guides_coverage() -> None:
    rows = [
        EvalCorpusRow.model_validate(
            {
                "id": "RG001",
                "domain": "registration_guides",
                "style": "normal",
                "user_utterance": "등록금 반환기준 알려줘",
                "api_request": {
                    "path": "/registration-guides",
                    "params": {"topic": "payment_and_return", "limit": 5},
                },
                "expected_mcp_flow": "tool_list_registration_guides",
                "truth_mode": "set_contains",
                "pass_rule": {"summary_kind": "registration_guides_top5"},
                "watch_policy": "none",
                "notes": "",
            }
        )
    ]
    results = [
        {
            "id": "RG001",
            "status": "completed",
            "verdict": "pass",
            "actual_summary": [{"title": "등록금 반환기준"}],
            "comparison": "set_contains",
            "truth_source": "official_source",
            "checked_at": "2026-03-19T10:20:00+09:00",
        }
    ]

    report = render_validation_report(
        rows=rows,
        results=results,
        checked_at="2026-03-19T10:20:00+09:00",
        base_url="https://songsim-public-api.onrender.com",
    )

    assert "Guide-Domain Coverage" in report
    assert report.count("| registration_guides | 1 | 1 |") == 2


def test_run_evaluation_records_http_errors_without_crashing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = EvalCorpusRow.model_validate(
        {
            "id": "PL001",
            "domain": "place",
            "style": "normal",
            "user_utterance": "중앙도서관 위치 알려줘",
            "api_request": {"path": "/places", "params": {"query": "중앙도서관"}},
            "expected_mcp_flow": "tool_search_places -> tool_get_place",
            "truth_mode": "exact_value",
            "pass_rule": {"summary_kind": "places_top3"},
            "watch_policy": "none",
            "notes": "",
        }
    )

    def _raise_timeout(*args, **kwargs):
        raise httpx.ReadTimeout("boom")

    monkeypatch.setattr(qa_eval, "_load_actual_payload", _raise_timeout)

    results = run_evaluation(
        base_url="https://songsim-public-api.onrender.com",
        rows=[row],
        truth_rows=[],
        checked_at="2026-03-18T10:20:00+09:00",
    )

    assert len(results) == 1
    assert results[0].status == "error"
    assert results[0].verdict == "fail"
    assert results[0].comparison == "http_error:ReadTimeout"


def test_default_eval_assets_match_distribution_plan() -> None:
    rows = load_eval_rows(DEFAULT_CORPUS_PATH)
    watchlist_rows = load_eval_rows(DEFAULT_WATCHLIST_PATH)

    assert len(rows) == 1004
    assert len(watchlist_rows) == 5

    by_domain: dict[str, int] = {}
    for row in rows:
        by_domain[row.domain] = by_domain.get(row.domain, 0) + 1

    assert by_domain == {
        "place": 160,
        "courses": 160,
        "notices": 110,
        "restaurants": 160,
        "transport": 50,
        "classrooms": 60,
        "academic_calendar": 70,
        "certificate_guides": 40,
        "scholarship_guides": 40,
        "wifi_guides": 40,
        "leave_of_absence_guides": 40,
        "academic_support_guides": 40,
        "registration_guides": 4,
        "out_of_scope": 30,
    }

    registration_rows = [row for row in rows if row.domain == "registration_guides"]

    assert len(registration_rows) == 4
    assert {row.api_request.path for row in registration_rows} == {"/registration-guides"}
    assert {row.expected_mcp_flow for row in registration_rows} == {
        "tool_list_registration_guides"
    }
    assert {row.pass_rule["summary_kind"] for row in registration_rows} == {
        "registration_guides_top5"
    }
    assert {row.api_request.params["topic"] for row in registration_rows} == {
        "bill_lookup",
        "payment_and_return",
        "payment_by_student",
    }
