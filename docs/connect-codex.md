# Connect From Codex

## 연결 정보

- 서버 이름 예시: `Songsim Campus MCP`
- Streamable HTTP URL: `https://your-public-mcp-url/mcp`
- 로그인: Auth0 + Google login

## 주 사용 시나리오

- 성심교정 장소와 건물 검색
- 교내 시설과 입점명 검색
- 헬스장, 편의점, ATM, 복사실 같은 생활어 검색
- 강의동 기준 현재 공실 조회
- 개설과목 조회
- 최신 공지 조회
- 출발 장소 기준 주변 식당 조회
- 브랜드 상호 직접 식당 검색
- 지하철/버스 교통 안내 조회

Codex에서는 이 MCP가 공개 제품의 기준 표면입니다. HTTP API나 Shared GPT보다 먼저 연결해 두면, 같은 검증 가능한 데이터 도구를 가장 직접적으로 쓸 수 있습니다.

## 추천 사용 흐름

1. `songsim://usage-guide` resource로 공개 범위를 확인
2. prompt_find_place / prompt_search_courses / prompt_class_periods / prompt_notice_categories / prompt_latest_notices / prompt_find_empty_classrooms / prompt_find_nearby_restaurants / prompt_search_restaurants / prompt_transport_guide 중 하나를 먼저 사용
3. prompt가 가리키는 tool로 실제 조회

강의실 공실은 공식 실시간 source가 있으면 그 결과를 우선 쓰고, 없으면 시간표 기준 예상 공실로 자동 폴백합니다.

## 예시 요청

- `성심교정 중앙도서관 정보 찾아줘`
- `2026년 1학기 컴퓨터정보공학부 과목 검색해줘`
- `최신 academic 공지 보여줘`
- `공지 카테고리 종류 알려줘`
- `employment랑 career 차이 설명해줘`
- `7교시가 몇 시야?`
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
- `매머드커피 어디 있어?`
- `이디야 있나?`
- `스타벅스 있어?`
- `커피빈 있어?`
- `중앙도서관 근처 한식집 찾아줘`
- `중앙도서관에서 10분 안쪽에 1만원 이하 식당 보여줘`
- `성심교정 지하철 오는 길 알려줘`

식당 조회에서 `budget_max`를 주면 가격 정보가 확인된 후보만 남고, 가격 정보가 없는 후보는 제외됩니다.
브랜드 direct search는 `origin`이 없어도 캠퍼스에 가까운 후보를 먼저 찾고, 근처에 없으면 더 가까운 외부 지점을 보여줄 수 있습니다. `스타벅스`, `커피빈`, `투썸`, `빽다방` 같은 브랜드도 같은 흐름으로 검색할 수 있습니다.
카테고리 설명은 `songsim://notice-categories` 또는 `/notice-categories`, 교시표는 `songsim://class-periods`, `/periods`, `/gpt/periods`로 바로 확인할 수 있습니다.

## 공개 서버 제한

- 첫 연결 시 로그인 또는 `mcp login` 흐름이 필요할 수 있습니다.
- 이 공개 MCP는 read-only입니다.
- 강의실 공실 응답에는 realtime/estimated fallback 여부가 함께 표시됩니다.
- profile, timetable, notice preferences, meal personalization, admin 기능은 제외됩니다.

전체 검증 자산은 `docs/qa/` 아래에서 운영합니다. Codex는 public MCP를 기준 표면으로 쓰고, Shared GPT는 릴리즈팩 중 핵심 10~15문장만 샘플 확인합니다.

- [공개 MCP 500문장 코퍼스](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-corpus-500.md)
- [공개 MCP 릴리즈팩 50](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-release-pack-50.md)
- [공개 MCP 라이브 판정표 50](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-live-validation-50.md)
- [공개 MCP 라이브 판정 요약](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-live-validation-summary.md)
