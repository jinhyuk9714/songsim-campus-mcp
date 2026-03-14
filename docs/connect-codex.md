# Connect From Codex

## 연결 정보

- 서버 이름 예시: `Songsim Campus MCP`
- Streamable HTTP URL: `https://your-public-mcp-url/mcp`
- 로그인: Auth0 + Google login

## 주 사용 시나리오

- 성심교정 장소와 건물 검색
- 개설과목 조회
- 최신 공지 조회
- 출발 장소 기준 주변 식당 조회
- 지하철/버스 교통 안내 조회

Codex에서는 이 MCP가 공개 제품의 기준 표면입니다. HTTP API나 Shared GPT보다 먼저 연결해 두면, 같은 검증 가능한 데이터 도구를 가장 직접적으로 쓸 수 있습니다.

## 추천 사용 흐름

1. `songsim://usage-guide` resource로 공개 범위를 확인
2. prompt_find_place / prompt_search_courses / prompt_latest_notices / prompt_find_nearby_restaurants / prompt_transport_guide 중 하나를 먼저 사용
3. prompt가 가리키는 tool로 실제 조회

## 예시 요청

- `성심교정 중앙도서관 정보 찾아줘`
- `2026년 1학기 컴퓨터정보공학부 과목 검색해줘`
- `최신 academic 공지 보여줘`
- `중앙도서관 근처 한식집 찾아줘`

## 대표 MCP 테스트 질문

- `성심교정 중앙도서관 위치 알려줘`
- `중도 어디야?`
- `학생식당 있는 건물 뭐야?`
- `2026년 1학기 객체지향 과목 찾아줘`
- `김가톨 교수 수업 알려줘`
- `최신 학사 공지 2개 보여줘`
- `장학 공지 최신순으로 3개 보여줘`
- `중앙도서관 근처 한식만 찾아줘`
- `중앙도서관에서 10분 안쪽에 1만원 이하 식당 보여줘`
- `성심교정 지하철 오는 길 알려줘`

## 공개 서버 제한

- 첫 연결 시 로그인 또는 `mcp login` 흐름이 필요할 수 있습니다.
- 이 공개 MCP는 read-only입니다.
- profile, timetable, notice preferences, meal personalization, admin 기능은 제외됩니다.

전체 100개 질문과 대표 리허설은 아래 문서를 보면 됩니다.

- [공개 MCP 100문장 테스트팩](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-test-pack-100.md)
- [공개 MCP 실행 리허설](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-rehearsal.md)
