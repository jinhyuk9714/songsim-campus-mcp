# Connect From Codex

## 연결 정보

- 서버 이름 예시: `Songsim Campus MCP`
- Streamable HTTP URL: `https://your-public-mcp-url/mcp`
- 로그인: 현재 공개 배포 기본값은 익명 read-only, 운영자가 OAuth 모드로 바꾸면 로그인 필요

## 주 사용 시나리오

- 성심교정 장소와 건물 검색
- 교내 시설과 입점명 검색
- 헬스장, 편의점, ATM, 복사실 같은 생활어 검색
- 강의동 기준 현재 공실 조회
- 개설과목 조회
- 학사일정 조회
- 증명서 발급 안내 조회
- 장학제도 안내 조회
- 최신 공지 조회
- 출발 장소 기준 주변 식당 조회
- 브랜드 상호 직접 식당 검색
- 공식 학식 3곳의 이번 주 메뉴 조회
- 중앙도서관 열람실 좌석 현황 조회
- 건물별 WIFI 안내 조회
- 지하철/버스 교통 안내 조회

Codex에서는 이 MCP가 공개 제품의 기준 표면입니다. 학생-facing 기본 입구는 Remote MCP이고, HTTP는 검증 가능한 companion layer입니다.

## 추천 사용 흐름

1. `songsim://usage-guide` resource로 공개 범위를 확인
2. prompt_find_place / prompt_search_courses / prompt_academic_calendar / prompt_class_periods / prompt_library_seat_status / prompt_notice_categories / prompt_latest_notices / prompt_find_empty_classrooms / prompt_find_nearby_restaurants / prompt_search_restaurants / prompt_search_dining_menus / prompt_transport_guide 중 하나를 먼저 사용
3. prompt가 가리키는 tool을 호출하고, 장학제도·증명발급·WIFI 같은 guide는 resource 또는 direct tool로 바로 조회

강의실 공실은 공식 실시간 source가 있으면 그 결과를 우선 쓰고, 없으면 시간표 기준 예상 공실로 자동 폴백합니다.

## 예시 요청

- `성심교정 중앙도서관 정보 찾아줘`
- `2026년 1학기 컴퓨터정보공학부 과목 검색해줘`
- `2026학년도 3월 학사일정 보여줘`
- `재학증명서 발급 안내 알려줘`
- `장학제도 안내 알려줘`
- `김수환관 WIFI 안내 알려줘`
- `최신 academic 공지 보여줘`
- `학생식당 메뉴 보여줘`
- `카페 보나 이번 주 메뉴 알려줘`
- `공지 카테고리 종류 알려줘`
- `employment랑 career 차이 설명해줘`
- `7교시가 몇 시야?`
- `7교시에 시작하는 과목 찾고 싶어`
- `중앙도서관 근처 한식집 찾아줘`

## 대표 MCP 테스트 질문

- `성심교정 중앙도서관 위치 알려줘`
- `중도 어디야`
- `트러스트짐 어디야?`
- `헬스장 어디야?`
- `편의점 어디 있어?`
- `ATM 어디 있어?`
- `학생회관 어디야?`
- `K관 어디야?`
- `니콜스인데 2026-03-16 오전 10시 15분 기준 비어 있는 강의실 있어?`
- `K관 지금 빈 강의실 있어?`
- `김수환관 지금 비어 있는 강의실 있어?`
- `정문 기준 빈 강의실 보여줘`
- `장학 공지 최신순으로 3개 보여줘`
- `최신 취업 공지 3개 보여줘`
- `3월 학사일정 보여줘`
- `추가 등록기간 일정 알려줘`
- `재학증명서 발급 방법 알려줘`
- `장학금 신청 안내 알려줘`
- `니콜스관 WIFI 안내 알려줘`
- `학생식당 메뉴 보여줘`
- `카페 멘사 메뉴 있어?`
- `중앙도서관 열람실 남은 좌석 알려줘`
- `제1자유열람실 남은 좌석 알려줘`
- `매머드커피 어디 있어?`
- `이디야 있나?`
- `스타벅스 있어?`
- `커피빈 있어?`
- `중앙도서관 근처 한식집 찾아줘`
- `중앙도서관에서 10분 안쪽에 1만원 이하 식당 보여줘`
- `성심교정 지하철 오는 길 알려줘`

식당 조회에서 `budget_max`를 주면 가격 정보가 확인된 후보만 남고, 가격 정보가 없는 후보는 제외됩니다.
브랜드 direct search는 `origin`이 없어도 캠퍼스에 가까운 후보를 먼저 찾고, 근처에 없으면 더 가까운 외부 지점을 보여줄 수 있습니다. `스타벅스`, `커피빈`, `투썸`, `빽다방` 같은 브랜드도 같은 흐름으로 검색할 수 있습니다.
학사일정은 `prompt_academic_calendar`와 `tool_list_academic_calendar`로 조회하고, HTTP에서는 `/academic-calendar`를 씁니다. `academic_year`, `month`, `query`를 함께 주면 특정 월이나 제목 기준으로 좁힐 수 있습니다.
증명서 발급 안내는 `tool_list_certificate_guides`로 조회하고, HTTP에서는 `/certificate-guides`를 씁니다.
장학제도 안내는 `songsim://scholarship-guide`, `tool_list_scholarship_guides`, `/scholarship-guides`로 조회합니다.
건물별 WIFI 안내는 `songsim://wifi-guide`, `tool_list_wifi_guides`, `/wifi-guides`로 조회합니다.
교내 공식 학식 메뉴는 `prompt_search_dining_menus`와 `tool_search_dining_menus`로 조회하고, HTTP에서는 `/dining-menus`를 씁니다. 현재는 current-week 메뉴 텍스트와 원본 PDF 링크를 함께 반환합니다.
중앙도서관 열람실 좌석은 `prompt_library_seat_status`와 `tool_get_library_seat_status`로 조회하고, HTTP에서는 `/library-seats`를 씁니다. 이 기능은 best-effort live fetch이며 stale cache 또는 unavailable note로 폴백할 수 있습니다.
카테고리 설명은 `songsim://notice-categories` 또는 `/notice-categories`, 교시표는 `songsim://class-periods` 또는 `/periods`로 확인할 수 있습니다. 교시 기반 과목 조회는 `tool_search_courses(period_start=7, year=2026, semester=1)` 또는 `/courses?year=2026&semester=1&period_start=7`처럼 direct filter를 쓰면 됩니다.

## 공개 서버 제한

- 이 공개 MCP는 기본적으로 익명 read-only입니다.
- 운영자가 `SONGSIM_PUBLIC_MCP_AUTH_MODE=oauth`로 바꾸면 로그인 흐름이 다시 필요할 수 있습니다.
- 이 공개 MCP는 read-only입니다.
- 강의실 공실 응답에는 realtime/estimated fallback 여부가 함께 표시됩니다.
- profile, timetable, notice preferences, meal personalization, admin 기능은 제외됩니다.

전체 검증 자산은 `docs/qa/` 아래에서 운영합니다. Codex는 public MCP를 기준 표면으로 쓰고, GPT 표면은 선택적 포장층으로만 다룹니다.

- [공개 MCP 500문장 코퍼스](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-corpus-500.md)
- [공개 MCP 릴리즈팩 50](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-release-pack-50.md)
- [공개 MCP 라이브 판정표 50](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-live-validation-50.md)
- [공개 MCP 라이브 판정 요약](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-live-validation-summary.md)
