from __future__ import annotations

from pathlib import Path

from songsim_campus.ingest.official_sources import (
    GradeEvaluationGuideSource,
    GraduationRequirementGuideSource,
)

FIXTURES_DIR = Path(__file__).with_name("fixtures")


def _fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def test_academic_milestone_guide_sources_expose_expected_defaults() -> None:
    grade_source = GradeEvaluationGuideSource()
    graduation_source = GraduationRequirementGuideSource()

    assert grade_source.topic == "grade_evaluation"
    assert graduation_source.topic == "graduation_requirement"
    assert grade_source.source_tag == "cuk_academic_milestone_guides"
    assert graduation_source.source_tag == "cuk_academic_milestone_guides"
    assert grade_source.url.endswith("/grade_evaluation_system.do")
    assert graduation_source.url.endswith("/graduation_requirement.do")


def test_grade_evaluation_guide_parser_extracts_expected_sections() -> None:
    rows = GradeEvaluationGuideSource().parse(
        _fixture("grade_evaluation_system.html"),
        fetched_at="2026-03-20T00:00:00+09:00",
    )

    assert [row["title"] for row in rows] == [
        "성적평가 방법",
        "성적평가 등급",
        "성적확인",
        "수험자격",
        "학사경고",
    ]

    grade_method = next(row for row in rows if row["title"] == "성적평가 방법")
    assert grade_method["topic"] == "grade_evaluation"
    assert grade_method["source_tag"] == "cuk_academic_milestone_guides"
    assert grade_method["summary"] == "상대평가"
    assert grade_method["steps"] == ["상대평가"]

    grade_scale = next(row for row in rows if row["title"] == "성적평가 등급")
    assert any(
        "등급: A+ / 평점: 4.5 / 실점: 95 ~ 100" == step
        for step in grade_scale["steps"]
    )
    assert any("등급: A / 비율: 30% 이하" == step for step in grade_scale["steps"])
    assert any(
        "D, F 등급은 담당교수 재량으로 비율에 관계없이 줄 수 있음" == step
        for step in grade_scale["steps"]
    )
    assert any("자격증을 받기 위한 과목" in step for step in grade_scale["steps"])
    assert any("수강인원 10명 미만인 과목" == step for step in grade_scale["steps"])

    grade_check = next(row for row in rows if row["title"] == "성적확인")
    assert grade_check["summary"].startswith("성적 확인 및 이의신청 기간에 TRINITY 원스탑")
    assert any(
        "해당 학기 수강 교과목의 수업평가를 한 학생에 한해서 성적 조회 가능" in step
        for step in grade_check["steps"]
    )

    exam_eligibility = next(row for row in rows if row["title"] == "수험자격")
    assert exam_eligibility["steps"] == [
        (
            "각 교과목별로 결석일수가 수업시간의 4분의 1 이상인 학생은 "
            "수험자격 상실됨 (해당 과목은 F처리)"
        )
    ]

    probation = next(row for row in rows if row["title"] == "학사경고")
    assert probation["summary"].startswith("매학기 성적이 불량한 학생에 대하여 학사경고를 하고")
    assert any("연속 3회 또는 통산 4회" in step for step in probation["steps"])
    assert any("매학기 성적 평점평균 1.75 미만" in step for step in probation["steps"])


def test_graduation_requirement_guide_parser_extracts_expected_sections() -> None:
    rows = GraduationRequirementGuideSource().parse(
        _fixture("graduation_requirement.html"),
        fetched_at="2026-03-20T00:00:00+09:00",
    )

    assert [row["title"] for row in rows] == [
        "자격조건",
        "성적등급",
        "졸업논문 제목 신청서 제출 / 졸업논문 제목 변경 / 졸업논문 제출",
        "졸업종합시험 응시원 및 졸업종합시험 시행",
    ]

    eligibility = next(row for row in rows if row["title"] == "자격조건")
    assert eligibility["topic"] == "graduation_requirement"
    assert eligibility["source_tag"] == "cuk_academic_milestone_guides"
    assert eligibility["summary"] == "제8차 학기를 등록하고 재학 중인 학생"
    assert eligibility["steps"] == [
        "제8차 학기를 등록하고 재학 중인 학생",
        "제7차 학기까지 취득학점이 105학점 이상인 학생",
        "졸업논문 제목 신청서 및 졸업종합시험 응시원을 제출한 학생",
    ]

    grading = next(row for row in rows if row["title"] == "성적등급")
    assert any("통과(P) : A, B, C, D" == step for step in grading["steps"])
    assert any("부적격(F) : F" == step for step in grading["steps"])
    assert any(
        "졸업논문 성적이 'F'(부적격)인 학생은 졸업이 불가능함" == step
        for step in grading["steps"]
    )

    thesis = next(
        row
        for row in rows
        if row["title"] == "졸업논문 제목 신청서 제출 / 졸업논문 제목 변경 / 졸업논문 제출"
    )
    assert thesis["steps"] == [
        "지도교수 및 전공주임교수를 경유하여 소속 학부·과·전공에서 정한 기한까지 제출"
    ]

    comprehensive_exam = next(
        row for row in rows if row["title"] == "졸업종합시험 응시원 및 졸업종합시험 시행"
    )
    assert comprehensive_exam["summary"] == "각 학부·과·전공에서 정한 일정에 따라 시행"
    assert any(
        "복수전공 이수자는 각 전공별로 졸업논문 제목 신청서를 제출" in step
        for step in comprehensive_exam["steps"]
    )
    assert any(
        "졸업논문 작성 방법은 국문요람 '졸업논문 작성 요령' 참고" == step
        for step in comprehensive_exam["steps"]
    )
