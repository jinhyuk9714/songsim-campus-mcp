# Connect From Codex

## 연결 정보

- 서버 이름 예시: `Songsim Campus MCP`
- Streamable HTTP URL: `https://your-public-mcp-url/mcp`
- 기본 입구: Codex에서 학생용 기준 표면은 Remote MCP이고, HTTP는 검증 가능한 companion layer입니다.
- 로그인: 현재 공개 배포 기본값은 익명 read-only, 운영자가 OAuth 모드로 바꾸면 로그인 필요

## Codex에서 먼저 다루는 학생 여정

- 오늘 할 일: 최신 공지, 소속기관 공지, 행사/대외 프로그램, 학사일정
- 어디 / 연락처: 장소, 편의시설, 전화번호, 운영시간, 교통, Wi-Fi
- 절차 / 제도: 등록, 증명, 휴학, 수업, 계절학기, 성적·졸업, 학생교류, 장학
- 공부공간 / 자원: 과목, 교시, 도서관 좌석, 예상 빈 강의실, 학식, 주변 식당, PC 소프트웨어
- 특수 경로: 기숙사, 생활지원, 상담·예비군·병원, 소속기관 공지

## 추천 사용 흐름

1. `songsim://usage-guide`로 공개 범위를 먼저 확인
2. 질문에 맞는 prompt나 resource를 먼저 고름
3. prompt가 가리키는 tool을 호출
4. 필요하면 HTTP companion으로 같은 결과를 직접 검증

자주 쓰는 흐름:

- 장소 / 시설: `prompt_find_place` -> `tool_search_places` -> `tool_get_place`
- 과목 / 교시: `prompt_search_courses` -> `tool_search_courses` / `tool_get_class_periods`
- 오늘 할 일: `tool_list_latest_notices` / `tool_list_affiliated_notices` / `tool_list_campus_life_notices` / `tool_list_academic_calendar`
- 절차 / 제도: registration / certificate / leave / class / seasonal-semester / academic-milestone / student-exchange guide tools
- 공부공간 / 자원: `tool_get_library_seat_status`, `tool_list_estimated_empty_classrooms`, `tool_search_dining_menus`, `tool_find_nearby_restaurants`, `tool_search_pc_software`

## 예시 요청

### 오늘 할 일

- `최신 학사 공지 2개 보여줘`
- `국제학부 최신 공지 알려줘`
- `행사안내 보여줘`
- `3월 학사일정 보여줘`

### 어디 / 연락처

- `성심교정 중앙도서관 위치 알려줘`
- `ATM 어디 있어?`
- `보건실 전화번호 알려줘`
- `김수환관 WIFI 안내 알려줘`

### 절차 / 제도

- `등록금 고지서 조회 방법 알려줘`
- `공결 신청 방법 알려줘`
- `계절학기 신청 시기 알려줘`
- `졸업논문 제출 절차 알려줘`
- `유럽 교류대학 알려줘`

### 공부공간 / 자원

- `2026년 1학기 컴퓨터정보공학부 과목 검색해줘`
- `7교시가 몇 시야?`
- `중앙도서관 열람실 남은 좌석 알려줘`
- `니콜스관 지금 빈 강의실 있어?`
- `SPSS 설치된 컴퓨터실 어디야`
- `학생식당 메뉴 보여줘`

### 특수 경로

- `성심교정 기숙사 안내해줘`
- `학생상담 어디서 받아?`
- `예비군 신고 시기 알려줘`
- `부속병원 이용 안내해줘`
- `프란치스코관 입퇴사공지 알려줘`

## 공개 서버 제한

- 이 공개 MCP는 기본적으로 익명 read-only입니다.
- 운영자가 `SONGSIM_PUBLIC_MCP_AUTH_MODE=oauth`로 바꾸면 로그인 흐름이 다시 필요할 수 있습니다.
- 강의실 공실 응답에는 realtime/estimated fallback 여부가 함께 표시됩니다.
- profile, timetable, notice preferences, meal personalization, admin 기능은 제외됩니다.
- Local Full Mode는 운영과 개인화용 별도 모드입니다.

## 검증 자산

전체 검증 자산은 `docs/qa/` 아래에서 운영합니다. Codex 문서는 public MCP를 기준 표면으로 보고, HTTP와 GPT packaging은 보조 표면으로만 둡니다.

- [공개 MCP 500문장 코퍼스](qa/public-mcp-corpus-500.md)
- [공개 MCP 릴리즈팩 50](qa/public-mcp-release-pack-50.md)
- [공개 MCP 라이브 판정표 50](qa/public-mcp-live-validation-50.md)
- [공개 MCP 라이브 판정 요약](qa/public-mcp-live-validation-summary.md)
- [공개 API 1000문장 라이브 검증](qa/public-api-live-validation-1000.md)
