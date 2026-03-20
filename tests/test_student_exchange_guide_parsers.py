from __future__ import annotations

from pathlib import Path

from songsim_campus.ingest.official_sources import (
    StudentExchangeDomesticCreditExchangeGuideSource,
    StudentExchangeDomesticPartnerUniversitiesGuideSource,
    StudentExchangeExchangeProgramsGuideSource,
    StudentExchangeExchangeStudentGuideSource,
)

FIXTURES_DIR = Path(__file__).with_name("fixtures")


def _fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def test_student_exchange_domestic_credit_exchange_parser_extracts_expected_sections():
    rows = StudentExchangeDomesticCreditExchangeGuideSource().parse(
        _fixture("exchange_domestic1.html"),
        fetched_at="2026-03-19T00:00:00+09:00",
    )

    assert [row["title"] for row in rows] == [
        "교류대학 현황",
        "신청대상",
        "신청시기",
        "신청방법",
        "유의사항",
    ]

    table_row = rows[0]
    assert table_row["topic"] == "domestic_credit_exchange"
    assert table_row["source_tag"] == "cuk_student_exchange_guides"
    assert table_row["source_url"] == "https://www.catholic.ac.kr/ko/support/exchange_domestic1.do"
    assert table_row["summary"] == table_row["steps"][0]
    assert "가천대학교" in table_row["steps"][0]
    assert "교류가능 학점 수: 6" in table_row["steps"][0]

    timing_row = next(row for row in rows if row["title"] == "신청시기")
    assert timing_row["summary"] == "매 학기 본교 홈페이지에 학점교류 일정 공고"
    assert any("반드시 공지사항" in step for step in timing_row["steps"])


def test_student_exchange_domestic_partner_universities_parser_preserves_intro_and_table():
    rows = StudentExchangeDomesticPartnerUniversitiesGuideSource().parse(
        _fixture("exchange_domestic2.html"),
        fetched_at="2026-03-19T00:00:00+09:00",
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["topic"] == "domestic_partner_universities"
    assert row["title"] == "교류대학 현황"
    assert row["source_tag"] == "cuk_student_exchange_guides"
    assert row["summary"] == (
        "가톨릭대학교는 타 대학들과 교육, 연구, 사회봉사 분야에서 "
        "상호교류·협력을 위하여 학생교류 및 학점교환 협정에 따라 "
        "학점교류제도를 운영하고 있습니다."
    )
    assert row["steps"][0] == row["summary"]
    assert any("가천대학교" in step for step in row["steps"])
    assert any("건국대학교" in step for step in row["steps"])
    assert row["links"] == []


def test_student_exchange_exchange_student_parser_extracts_program_rows():
    rows = StudentExchangeExchangeStudentGuideSource().parse(
        _fixture("exchange_oversea2.html"),
        fetched_at="2026-03-19T00:00:00+09:00",
    )

    assert [row["title"] for row in rows] == [
        "상호교환 프로그램",
        "방문학생(자비유학) 프로그램",
        "SAF 프로그램",
    ]

    assert all(row["topic"] == "exchange_student" for row in rows)
    assert all(row["source_tag"] == "cuk_student_exchange_guides" for row in rows)
    assert all(
        row["links"]
        == [
            {
                "label": "교환학생 프로그램 알아보기",
                "url": "https://oia.catholic.ac.kr/oia/admission/exchange-student.do",
            }
        ]
        for row in rows
    )

    first = rows[0]
    assert first["summary"].startswith(
        "본교와 학생 교환 협정을 맺은 해외 협정교에 1년 또는 1개 학기 동안"
    )
    assert any("학기당 최대 19학점" in step for step in first["steps"])


def test_student_exchange_exchange_programs_parser_extracts_thumb_box_rows():
    rows = StudentExchangeExchangeProgramsGuideSource().parse(
        _fixture("exchange_oversea3.html"),
        fetched_at="2026-03-19T00:00:00+09:00",
    )

    assert [row["title"] for row in rows] == [
        "해외인턴십 프로그램",
        "하 · 동계 단기 어학연수 프로그램",
        "EASCOM(East Asia Student Communication Program)",
    ]

    internship = rows[0]
    assert internship["topic"] == "exchange_programs"
    assert internship["source_tag"] == "cuk_student_exchange_guides"
    assert internship["summary"].startswith("국제 비즈니스 실무 경험")
    assert internship["links"] == [
        {
            "label": "해외인턴십 프로그램 알아보기",
            "url": "https://oia.catholic.ac.kr/oia/program/global_internship_tab1.do",
        }
    ]

    eascom = rows[2]
    assert any("Hokusei Gakuen University" in step for step in eascom["steps"])
    assert eascom["links"] == [
        {
            "label": "EASCOM 프로그램 알아보기",
            "url": "https://oia.catholic.ac.kr/oia/program/index.do",
        }
    ]
