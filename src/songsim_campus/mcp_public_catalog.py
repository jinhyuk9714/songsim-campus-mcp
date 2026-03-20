from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field

from .services import (
    get_class_periods,
    get_notice_categories,
    list_academic_calendar,
    list_academic_milestone_guides,
    list_academic_status_guides,
    list_academic_support_guides,
    list_certificate_guides,
    list_class_guides,
    list_dormitory_guides,
    list_leave_of_absence_guides,
    list_registration_guides,
    list_scholarship_guides,
    list_seasonal_semester_guides,
    list_student_exchange_guides,
    list_transport_guides,
    list_wifi_guides,
    search_phone_book_entries,
    search_student_exchange_partners,
)

PLACE_CATEGORY_GUIDE = {
    "library": "도서관, 열람실, 자료 이용 중심 장소",
    "building": "강의동, 행정동 등 일반 건물",
    "facility": "학생식당, 편의점, 카페 같은 편의시설",
    "gate": "정문, 북문 같은 캠퍼스 출입구",
    "stop": "버스 정류장 같은 기준 위치",
}


def public_usage_guide_text() -> str:
    return "\n".join(
        [
            "Songsim public MCP usage guide",
            "",
            "This server is read-only.",
            (
                "Available: places, courses, academic calendar, academic support guides, "
                "academic status guides, registration guides, class guides, certificate guides, "
                "seasonal semester guides, academic milestone guides, phone book entries, "
                "leave-of-absence guides, scholarship guides, wifi guides, student exchange "
                "guides, student exchange partners, notices, dining menus, library seats, "
                "empty classrooms, nearby restaurants, restaurant search, affiliated notices, "
                "transport guides."
            ),
            "Use these public read-only tools for student information questions first.",
            "",
            "Recommended flow:",
            "1. Read songsim://usage-guide when you need the public MCP capability overview.",
            (
                "2. Use a prompt such as prompt_find_place or "
                "prompt_find_nearby_restaurants to choose the first tool."
            ),
            (
                "3. Use tool_search_places for fuzzy building/facility queries such as "
                "트러스트짐, 헬스장, 편의점, ATM, 복사실, K관, or 정문, then "
                "tool_get_place when you know the slug."
            ),
            (
                "4. Use tool_list_estimated_empty_classrooms for classroom availability "
                "in a lecture building like 니콜스관, N관, or 김수환관. 공식 실시간 "
                "데이터가 있으면 먼저 사용하고, 없으면 시간표 기반 예상 공실로 "
                "폴백합니다."
            ),
            (
                "5. Use tool_find_nearby_restaurants for walkable food "
                "recommendations from a campus origin. You can pass a slug, 대표 이름, "
                "or a clear alias like 중도 or 학생식당. If you set budget_max, only "
                "restaurants with explicit price evidence remain."
            ),
            (
                "6. Use tool_search_restaurants for direct brand-name searches such as "
                "매머드커피, 메가커피, 이디야, 스타벅스, 커피빈, 투썸, or 빽다방. "
                "origin이 없어도 캠퍼스 주변에서 브랜드를 직접 찾을 수 있고, "
                "캠퍼스에 가까운 후보를 먼저 찾은 뒤 필요하면 더 가까운 외부 "
                "지점까지 보여줄 수 있습니다."
            ),
            (
                "7. Use tool_search_dining_menus for official campus dining menus such as "
                "학생식당 메뉴, 카페 보나 메뉴, 카페 멘사 메뉴, or 부온 프란조 이번 주 메뉴. "
                "Returns extracted weekly menu text plus the original PDF link when available."
            ),
            (
                "8. Use tool_get_library_seat_status for 중앙도서관 열람실 남은 좌석, "
                "중앙도서관 좌석 현황, or 제1자유열람실 남은 좌석 questions. "
                "This is a best-effort live lookup with stale fallback."
            ),
            (
                "9. Use tool_list_academic_calendar for 학사일정 questions such as "
                "3월 학사일정, 1학기 개시일, 추가 등록기간, or 중간고사 일정."
            ),
            (
                "10. Use tool_list_academic_support_guides for 학사지원 업무안내 such as "
                "휴복학 문의처, 학점교류 담당 전화번호, 성적 담당처, or 교직 업무 문의 questions."
            ),
            (
                "11. Use tool_list_academic_status_guides for 학적변동 안내 such as "
                "복학 신청 방법, 자퇴 절차, or 재입학 지원자격 questions."
            ),
            (
                "12. Use tool_list_student_exchange_guides for 학생교류 안내 such as "
                "국내 학점교류 신청대상, 학점교류 신청시기, 교류대학 현황, 교환학생 프로그램, "
                "or 해외 교류프로그램 questions."
            ),
            (
                "13. Use tool_search_phone_book for 주요전화번호 / 부서 연락처 such as "
                "보건실 전화번호, 학사지원팀 전화번호, 트리니티 문의 전화번호, "
                "유실물 문의 전화번호, or 기숙사 운영팀 전화번호 questions."
            ),
            (
                "14. Use tool_search_student_exchange_partners for 해외협정대학 검색 such as "
                "해외협정대학 알려줘, 네덜란드 협정대학 알려줘, Utrecht University 있어?, "
                "유럽 교류대학 알려줘, or 대만 해외협정대학 홈페이지 알려줘 questions."
            ),
            (
                "15. Use tool_list_dormitory_guides for 기숙사 안내 such as "
                "성심교정 기숙사 안내해줘, 스테파노관 정보 알려줘, "
                "기숙사 입사안내 어디서 봐?, or 기숙사 최신 공지 알려줘 questions."
            ),
            (
                "16. Use tool_list_registration_guides for 등록 안내 such as "
                "등록금 고지서 조회 방법, "
                "등록금 납부 방법, 등록금 반환 기준, or 초과학기생 등록 questions."
            ),
            (
                "17. Use tool_list_certificate_guides for 증명서 발급 안내 such as "
                "재학증명서 발급 방법, 졸업증명서 발급 안내, or 인터넷 증명발급 questions."
            ),
            (
                "18. Use tool_list_class_guides for 수업 안내 such as "
                "수강신청 변경기간, 재수강 기준, 수업평가 기간, 공결 신청 방법, "
                "or 외국어강의 의무이수 요건 questions."
            ),
            (
                "19. Use tool_list_leave_of_absence_guides for 휴학 안내 such as 휴학 신청방법, "
                "군휴학, 질병휴학, 등록금 반환 기준, or 휴복학 FAQ questions."
            ),
            (
                "20. Use tool_list_seasonal_semester_guides for 계절학기 안내 such as "
                "계절학기 신청 시기, 신청대상, 학점 제한, or 신청절차 questions."
            ),
            (
                "21. Use tool_list_academic_milestone_guides for 성적·졸업 안내 such as "
                "성적평가 방법, 성적확인, 결석이 4분의 1 넘으면 어떻게 되는지, "
                "졸업요건, or 졸업논문 제출 절차 questions."
            ),
            (
                "22. Use tool_list_scholarship_guides for 장학제도 baseline guidance such as "
                "장학생 자격, 장학금 신청, 장학금 지급, or 장학제도 공식 문서 questions."
            ),
            (
                "23. Use tool_list_wifi_guides for campus wifi guidance such as 니콜스관 "
                "SSID, 중앙도서관 와이파이, or 무선랜 접속 방법 questions."
            ),
            (
                "24. Use tool_list_affiliated_notices for affiliated department and dormitory "
                "board notice bundles such as 국제학부 최신 공지 or 기숙사 일반공지."
            ),
            "25. Use tool_list_latest_notices for latest notices; category is optional.",
            (
                "26. Use tool_list_transport_guides for static subway or bus access "
                "guidance. You can pass query with natural-language cues like 지하철, "
                "1호선, 역곡역, or 버스. 셔틀은 현재 지원하지 않아 빈 결과가 정상입니다."
            ),
            (
                "27. Optional reference resources exist for notice categories and class periods "
                "when you need them."
            ),
            "",
            "Example questions:",
            "- 성심교정 중앙도서관 위치 알려줘",
            "- K관 어디야?",
            "- 정문 위치 알려줘",
            "- 트러스트짐 어디야?",
            "- 헬스장 어디야?",
            "- 편의점 어디 있어?",
            "- 최신 장학 공지 3개 보여줘",
            "- 장학제도 안내 알려줘",
            "- 등록금 고지서 조회 방법 알려줘",
            "- 등록금 납부 방법 알려줘",
            "- 등록금 반환 기준 알려줘",
            "- 초과학기생 등록은 어떻게 해?",
            "- 국제학부 최신 공지 알려줘",
            "- 국제학부 공결 신청 공지 있어?",
            "- 기숙사 일반공지 알려줘",
            "- 프란치스코관 입퇴사공지 알려줘",
            "- 기숙사 OT 공지 알려줘",
            "- 보건실 전화번호 알려줘",
            "- 학사지원팀 전화번호 알려줘",
            "- 트리니티 문의 전화번호 알려줘",
            "- 유실물 문의 전화번호 알려줘",
            "- 기숙사 운영팀 전화번호 알려줘",
            "- 해외협정대학 알려줘",
            "- 네덜란드 협정대학 알려줘",
            "- Utrecht University 있어?",
            "- 유럽 교류대학 알려줘",
            "- 대만 해외협정대학 홈페이지 알려줘",
            "- 성심교정 기숙사 안내해줘",
            "- 기숙사 최신 공지 알려줘",
            "- 수강신청 변경기간 알려줘",
            "- 재수강 기준 알려줘",
            "- 수업평가 기간 알려줘",
            "- 공결 신청 방법 알려줘",
            "- 외국어강의 의무이수 요건 알려줘",
            "- 계절학기 신청 시기 알려줘",
            "- 계절학기 신청대상 알려줘",
            "- 계절학기 학점 제한 알려줘",
            "- 계절학기 신청절차 알려줘",
            "- 성적평가 방법 알려줘",
            "- 성적확인 어떻게 해?",
            "- 결석이 4분의 1 넘으면 어떻게 돼?",
            "- 졸업요건 알려줘",
            "- 졸업논문 제출 절차 알려줘",
            "- 휴복학 문의 어디로 해야 해?",
            "- 학점교류 담당 전화번호 알려줘",
            "- 국내 학점교류 신청대상 알려줘",
            "- 학점교류 신청시기 알려줘",
            "- 교류대학 현황 알려줘",
            "- 교환학생 프로그램 알려줘",
            "- 해외 교류프로그램 알려줘",
            "- 복학 신청 방법 알려줘",
            "- 자퇴 절차 알려줘",
            "- 재입학 지원자격 알려줘",
            "- 휴학 신청방법 알려줘",
            "- 군휴학 제출 안내 알려줘",
            "- 니콜스관 WIFI 안내 알려줘",
            "- 재학증명서 발급 안내 알려줘",
            "- 니콜스관인데 지금 예상 빈 강의실 있어?",
            "- 매머드커피 어디 있어?",
            "- 스타벅스 있어?",
            "- 중앙도서관 근처 밥집 추천해줘",
            "- 중도 근처 밥집 추천해줘",
            "- 학생식당 메뉴 보여줘",
            "- 카페 보나 이번 주 메뉴 알려줘",
            "- 중앙도서관 열람실 남은 좌석 알려줘",
        ]
    )


def register_shared_resources(mcp: Any, connection_factory: Any, docs_dir: Path) -> None:
    @mcp.resource("songsim://source-registry")
    def source_registry() -> str:
        """Return the official source registry reference."""
        return (docs_dir / "source_registry.md").read_text(encoding="utf-8")

    @mcp.resource("songsim://transport-guide")
    def transport_guide_resource() -> str:
        """Return the latest static transport guides as JSON."""
        with connection_factory() as conn:
            return json.dumps(
                [item.model_dump() for item in list_transport_guides(conn, limit=50)],
                ensure_ascii=False,
                indent=2,
            )

    @mcp.resource("songsim://certificate-guide")
    def certificate_guide_resource() -> str:
        """Return the latest certificate guides as JSON."""
        with connection_factory() as conn:
            return json.dumps(
                [item.model_dump() for item in list_certificate_guides(conn, limit=50)],
                ensure_ascii=False,
                indent=2,
            )

    @mcp.resource("songsim://leave-of-absence-guide")
    def leave_of_absence_guide_resource() -> str:
        """Return the latest leave-of-absence guides as JSON."""
        with connection_factory() as conn:
            return json.dumps(
                [item.model_dump() for item in list_leave_of_absence_guides(conn, limit=50)],
                ensure_ascii=False,
                indent=2,
            )

    @mcp.resource("songsim://scholarship-guide")
    def scholarship_guide_resource() -> str:
        """Return the latest scholarship guides as JSON."""
        with connection_factory() as conn:
            return json.dumps(
                [item.model_dump() for item in list_scholarship_guides(conn, limit=50)],
                ensure_ascii=False,
                indent=2,
            )

    @mcp.resource("songsim://wifi-guide")
    def wifi_guide_resource() -> str:
        """Return the latest wifi guides as JSON."""
        with connection_factory() as conn:
            return json.dumps(
                [item.model_dump() for item in list_wifi_guides(conn, limit=50)],
                ensure_ascii=False,
                indent=2,
            )

    @mcp.resource("songsim://academic-support-guide")
    def academic_support_guide_resource() -> str:
        """Return the latest academic-support guides as JSON."""
        with connection_factory() as conn:
            return json.dumps(
                [item.model_dump() for item in list_academic_support_guides(conn, limit=50)],
                ensure_ascii=False,
                indent=2,
            )

    @mcp.resource("songsim://academic-status-guide")
    def academic_status_guide_resource() -> str:
        """Return the latest academic-status guides as JSON."""
        with connection_factory() as conn:
            return json.dumps(
                [item.model_dump() for item in list_academic_status_guides(conn, limit=50)],
                ensure_ascii=False,
                indent=2,
            )

    @mcp.resource("songsim://registration-guide")
    def registration_guide_resource() -> str:
        """Return the latest registration guides as JSON."""
        with connection_factory() as conn:
            return json.dumps(
                [item.model_dump() for item in list_registration_guides(conn, limit=50)],
                ensure_ascii=False,
                indent=2,
            )

    @mcp.resource("songsim://class-guide")
    def class_guide_resource() -> str:
        """Return the latest class guides as JSON."""
        with connection_factory() as conn:
            return json.dumps(
                [item.model_dump() for item in list_class_guides(conn, limit=50)],
                ensure_ascii=False,
                indent=2,
            )

    @mcp.resource("songsim://seasonal-semester-guide")
    def seasonal_semester_guide_resource() -> str:
        """Return the latest seasonal semester guides as JSON."""
        with connection_factory() as conn:
            return json.dumps(
                [item.model_dump() for item in list_seasonal_semester_guides(conn, limit=50)],
                ensure_ascii=False,
                indent=2,
            )

    @mcp.resource("songsim://academic-milestone-guide")
    def academic_milestone_guide_resource() -> str:
        """Return the latest academic milestone guides as JSON."""
        with connection_factory() as conn:
            return json.dumps(
                [item.model_dump() for item in list_academic_milestone_guides(conn, limit=50)],
                ensure_ascii=False,
                indent=2,
            )

    @mcp.resource("songsim://student-exchange-guide")
    def student_exchange_guide_resource() -> str:
        """Return the latest student exchange guides as JSON."""
        with connection_factory() as conn:
            return json.dumps(
                [item.model_dump() for item in list_student_exchange_guides(conn, limit=50)],
                ensure_ascii=False,
                indent=2,
            )

    @mcp.resource("songsim://student-exchange-partners")
    def student_exchange_partners_resource() -> str:
        """Return the latest student exchange partner universities as JSON."""
        with connection_factory() as conn:
            return json.dumps(
                [
                    item.model_dump()
                    for item in search_student_exchange_partners(conn, limit=50)
                ],
                ensure_ascii=False,
                indent=2,
            )

    @mcp.resource("songsim://phone-book")
    def phone_book_resource() -> str:
        """Return the latest phone-book entries as JSON."""
        with connection_factory() as conn:
            return json.dumps(
                [item.model_dump() for item in search_phone_book_entries(conn, limit=50)],
                ensure_ascii=False,
                indent=2,
            )

    @mcp.resource("songsim://affiliated-notices")
    def affiliated_notices_resource() -> str:
        """Return affiliated department and dormitory notices as JSON."""
        from . import services as _services

        with connection_factory() as conn:
            return json.dumps(
                [item.model_dump() for item in _services.list_affiliated_notices(conn, limit=50)],
                ensure_ascii=False,
                indent=2,
            )

    @mcp.resource("songsim://dormitory-guide")
    def dormitory_guide_resource() -> str:
        """Return the latest dormitory guides as JSON."""
        with connection_factory() as conn:
            return json.dumps(
                [item.model_dump() for item in list_dormitory_guides(conn, limit=50)],
                ensure_ascii=False,
                indent=2,
            )

    @mcp.resource("songsim://academic-calendar")
    def academic_calendar_resource() -> str:
        """Return the latest academic calendar events as JSON."""
        with connection_factory() as conn:
            return json.dumps(
                [item.model_dump() for item in list_academic_calendar(conn, limit=50)],
                ensure_ascii=False,
                indent=2,
            )


def register_public_resources(mcp: Any, connection_factory: Any) -> None:
    @mcp.resource("songsim://usage-guide")
    def usage_guide_resource() -> str:
        """Return the public MCP usage guide."""
        return public_usage_guide_text()

    @mcp.resource("songsim://place-categories")
    def place_categories_resource() -> str:
        """Return public place category descriptions as JSON."""
        return json.dumps(PLACE_CATEGORY_GUIDE, ensure_ascii=False, indent=2)

    @mcp.resource("songsim://notice-categories")
    def notice_categories_resource() -> str:
        """Return public notice category labels as JSON."""
        return json.dumps(
            [item.model_dump() for item in get_notice_categories()],
            ensure_ascii=False,
            indent=2,
        )

    @mcp.resource("songsim://class-periods")
    def class_periods_resource() -> str:
        """Return the static class period table as JSON."""
        return json.dumps(
            [item.model_dump() for item in get_class_periods()],
            ensure_ascii=False,
            indent=2,
        )


def register_public_prompts(mcp: Any) -> None:
    @mcp.prompt(
        name="prompt_find_place",
        description="Explain how to search for a place, building, alias, or facility.",
    )
    def prompt_find_place(
        query: Annotated[
            str,
            Field(
                description=(
                    "건물명, 별칭, 시설명, 교내 입점명. "
                    "예: 중앙도서관, 중도, K관, 정문, 학생회관, 트러스트짐, 헬스장, 편의점"
                )
            ),
        ]
    ):
        return (
            "Use songsim://usage-guide first if you need the public MCP rules.\n"
            f"Then call tool_search_places with query={query}.\n"
            "Short campus queries like K관 or 정문 are okay; exact short queries "
            "should resolve to the canonical campus place directly.\n"
            "If the result narrows to one clear candidate, call tool_get_place with the "
            "slug from tool_search_places.\n"
            "Use songsim://place-categories if you need to explain category labels."
        )

    @mcp.prompt(
        name="prompt_search_courses",
        description=(
            "Explain how to search Songsim courses by title, code, professor, "
            "year, or semester."
        ),
    )
    def prompt_search_courses(
        query: Annotated[str, Field(description="과목명, 코드, 교수명 등 검색어")] = "",
        year: Annotated[int | None, Field(description="학년도 필터")] = None,
        semester: Annotated[int | None, Field(description="학기 필터")] = None,
        period_start: Annotated[int | None, Field(description="교시 시작 번호 필터")] = None,
    ):
        return (
            "Use tool_search_courses for public course lookup.\n"
            f"query={query or '<empty>'}, year={year}, semester={semester}, "
            f"period_start={period_start}.\n"
            "If a user asks about period numbers, use prompt_class_periods first.\n"
            "For questions like 7교시에 시작하는 과목, call tool_search_courses with "
            "period_start=7 plus year/semester when available.\n"
            "The direct metadata paths are songsim://class-periods, "
            "tool_get_class_periods, and /periods."
        )

    @mcp.prompt(
        name="prompt_academic_calendar",
        description="Explain how to fetch academic calendar events by academic year or month.",
    )
    def prompt_academic_calendar(
        academic_year: Annotated[
            int | None,
            Field(description="optional academic year"),
        ] = None,
        month: Annotated[
            int | None,
            Field(description="optional month filter as an integer from 1 to 12"),
        ] = None,
        query: Annotated[
            str | None,
            Field(description="optional title substring like 등록, 개시일, 중간고사"),
        ] = None,
        limit: Annotated[int, Field(description="최대 결과 수")] = 20,
    ):
        return (
            "Use tool_list_academic_calendar for public academic calendar lookup.\n"
            f"academic_year={academic_year}, month={month}, query={query or '<optional>'}, "
            f"limit={limit}.\n"
            "month is optional and should be an integer from 1 to 12. "
            "It keeps events that overlap that month within the academic year.\n"
            "Use this for questions like 3월 학사일정, 1학기 개시일, "
            "추가 등록기간, or 중간고사 일정."
        )

    @mcp.prompt(
        name="prompt_search_dining_menus",
        description="Explain how to fetch official campus dining menus for the current week.",
    )
    def prompt_search_dining_menus(
        query: Annotated[
            str | None,
            Field(
                description=(
                    "교내 식당 메뉴 질의. 예: 학생식당 메뉴, 카페 보나 메뉴, "
                    "카페 멘사 메뉴, 부온 프란조 이번 주 메뉴"
                )
            ),
        ] = None,
        limit: Annotated[int, Field(description="최대 결과 수")] = 10,
    ):
        return (
            "Use tool_search_dining_menus for official campus dining menus.\n"
            f"query={query or '<optional>'}, limit={limit}.\n"
            "Generic queries like 학생식당 메뉴, 교내 식당 메뉴, or 학식 메뉴 "
            "should return all current official dining venues.\n"
            "Venue-specific queries like 카페 보나 메뉴 or 부온 프란조 이번 주 메뉴 "
            "should narrow to that venue.\n"
            "This tool returns weekly menu text plus the original PDF link."
        )

    @mcp.prompt(
        name="prompt_class_periods",
        description="Explain how to read the static class period table directly.",
    )
    def prompt_class_periods():
        return (
            "Use songsim://class-periods or call tool_get_class_periods for the public "
            "class period table.\n"
            "The HTTP metadata path is /periods.\n"
            "Use this first for questions like 7교시가 몇 시야 or 3교시가 몇 시야."
        )

    @mcp.prompt(
        name="prompt_library_seat_status",
        description="Explain how to check central-library reading-room seat status.",
    )
    def prompt_library_seat_status(
        query: Annotated[
            str | None,
            Field(
                description=(
                    "optional room query like 열람실 남은 좌석, 중앙도서관 좌석 현황, "
                    "or 제1자유열람실 남은 좌석"
                )
            ),
        ] = None,
    ):
        return (
            "Use tool_get_library_seat_status for 중앙도서관 열람실 좌석 현황.\n"
            f"query={query or '<optional>'}.\n"
            "The HTTP path is /library-seats.\n"
            "This is a best-effort live lookup with fresh cache and stale fallback, "
            "so availability_mode may be live, stale_cache, or unavailable."
        )

    @mcp.prompt(
        name="prompt_notice_categories",
        description="Explain how to read the public notice category list directly.",
    )
    def prompt_notice_categories():
        return (
            "Use songsim://notice-categories for the canonical public notice categories.\n"
            "The HTTP metadata path is /notice-categories.\n"
            "Use this first for questions like 공지 카테고리 종류, academic이 뭐야, "
            "or employment랑 career 차이."
        )

    @mcp.prompt(
        name="prompt_latest_notices",
        description=(
            "Explain how to fetch latest public notices, optionally filtered "
            "by category."
        ),
    )
    def prompt_latest_notices(
        category: Annotated[
            str | None,
            Field(description="optional notice category like scholarship or academic"),
        ] = None,
        limit: Annotated[int, Field(description="가져올 공지 수")] = 10,
    ):
        return (
            "Use tool_list_latest_notices for latest public notices.\n"
            f"category={category or '<optional>'}, limit={limit}.\n"
            "Category is optional. For category-explanation questions, use "
            "prompt_notice_categories first.\n"
            "The direct metadata paths are songsim://notice-categories and "
            "/notice-categories."
        )

    @mcp.prompt(
        name="prompt_find_nearby_restaurants",
        description="Explain how to find walkable nearby restaurants from a campus origin.",
    )
    def prompt_find_nearby_restaurants(
        origin: Annotated[
            str,
            Field(
                description=(
                    "출발 장소 대표 이름 또는 alias. "
                    "예: 중앙도서관, 중도, 학생식당, K관, 정문"
                )
            ),
        ],
        category: Annotated[
            str | None,
            Field(description="optional category like korean or cafe"),
        ] = None,
        budget_max: Annotated[int | None, Field(description="optional maximum budget")] = None,
        open_now: Annotated[bool, Field(description="영업 중 후보만 원하면 true")] = False,
        walk_minutes: Annotated[int, Field(description="도보 허용 시간(분)")] = 15,
    ):
        return (
            "Use songsim://usage-guide first if you need the public MCP rules.\n"
            f"Then call tool_find_nearby_restaurants with origin={origin}, "
            f"category={category or '<optional>'}, budget_max={budget_max}, "
            f"open_now={open_now}, walk_minutes={walk_minutes}.\n"
            "A clear alias such as 중도, 학생식당, or K관 can be used directly.\n"
            "If cached nearby results exist, the API may return them immediately for a "
            "faster response.\n"
            "Use tool_search_places first only if the origin is ambiguous."
        )

    @mcp.prompt(
        name="prompt_search_restaurants",
        description="Explain how to search restaurant or cafe brands directly by name.",
    )
    def prompt_search_restaurants(
        query: Annotated[
            str,
            Field(
                description=(
                    "브랜드 또는 상호 직접 검색어. "
                    "예: 매머드커피, 메가커피, 이디야, 스타벅스, 커피빈"
                )
            ),
        ],
        origin: Annotated[
            str | None,
            Field(description="optional campus origin for distance sorting"),
        ] = None,
        category: Annotated[
            str | None,
            Field(description="optional category like cafe or korean"),
        ] = None,
        limit: Annotated[int, Field(description="최대 결과 수")] = 10,
    ):
        return (
            "Use songsim://usage-guide first if you need the public MCP rules.\n"
            f"Then call tool_search_restaurants with query={query}, "
            f"origin={origin or '<optional>'}, category={category or '<optional>'}, "
            f"limit={limit}.\n"
            "Use this for direct brand searches like 매머드커피, 메가커피, "
            "이디야, 스타벅스, or 커피빈.\n"
            "If origin is omitted, search around the campus center first and show "
            "campus-nearest matches first. If nothing is nearby, return the nearest "
            "outside branch that still matches.\n"
            "For recommendation-style questions from a campus origin, use the nearby "
            "restaurant flow instead."
        )

    @mcp.prompt(
        name="prompt_find_empty_classrooms",
        description=(
            "Explain how to find current empty classrooms in a building "
            "with realtime-first fallback."
        ),
    )
    def prompt_find_empty_classrooms(
        building: Annotated[
            str,
            Field(
                description=(
                    "강의실을 확인할 건물 대표 이름 또는 alias. "
                    "예: 니콜스관, 니콜스, N관, 김수환관"
                )
            ),
        ],
        at: Annotated[
            str | None,
            Field(description="optional ISO 8601 timestamp for the evaluation time"),
        ] = None,
        year: Annotated[int | None, Field(description="optional academic year")] = None,
        semester: Annotated[int | None, Field(description="optional semester")] = None,
        limit: Annotated[int, Field(description="최대 결과 수")] = 10,
    ):
        return (
            "Use songsim://usage-guide first if you need the public MCP rules.\n"
            f"Then call tool_list_estimated_empty_classrooms with building={building}, "
            f"at={at or '<optional>'}, year={year}, semester={semester}, limit={limit}.\n"
            "This flow prefers 공식 실시간 classroom availability when available, "
            "and otherwise falls back to timetable-based 예상 공실.\n"
            "If the building name is unclear, use tool_search_places first."
        )

    @mcp.prompt(
        name="prompt_transport_guide",
        description="Explain how to fetch subway or bus transport guidance for Songsim campus.",
    )
    def prompt_transport_guide(
        mode: Annotated[
            str | None,
            Field(description="optional transport mode like subway or bus"),
        ] = None,
        query: Annotated[
            str | None,
            Field(
                description=(
                    "optional natural-language transport cue like 지하철, "
                    "1호선, 역곡역, bus"
                )
            ),
        ] = None,
        limit: Annotated[int, Field(description="가져올 가이드 수")] = 20,
    ):
        return (
            "Use tool_list_transport_guides for static transit guidance.\n"
            f"mode={mode or '<optional>'}, query={query or '<optional>'}, limit={limit}.\n"
            "If mode is explicit, it wins over query. query can be natural-language cues "
            "like 지하철, 1호선, 역곡역, bus, or 버스.\n"
            "This tool is for subway and bus access guidance, not live routing. "
            "셔틀 is not currently supported, so an empty result (빈 결과) is normal."
        )
