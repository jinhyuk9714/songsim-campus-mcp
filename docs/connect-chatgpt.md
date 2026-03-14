# Connect From ChatGPT

## 연결 정보

- 이름 예시: `Songsim Campus MCP`
- URL: `https://your-public-mcp-url/mcp`
- 모드: read-only public server
- 로그인: Auth0 + Google login

## 먼저 무엇에 쓰나

- 건물명, 별칭, 시설명으로 장소 찾기
- 강의동 기준 예상 빈 강의실 조회
- 학년도/학기 기준 개설과목 찾기
- 캠퍼스 출발지 기준 주변 식당 찾기
- 최신 공지와 교통 안내 조회
- 공개 서버는 read-only라서 profile, timetable, admin 기능은 제공하지 않음

## 추천 사용 흐름

1. `songsim://usage-guide` resource를 먼저 읽어 공개 MCP 범위를 확인
2. place / course / notice / restaurant / transport prompt 중 하나를 사용
3. prompt가 가리키는 tool을 호출해 실제 조회

## GPT 링크로 공개하고 싶을 때

ChatGPT의 `chatgpt.com/g/...` 링크를 만들고 싶다면 MCP connector 대신 GPT Builder의 `Actions`를 사용합니다. 다만 제품의 기본 표면은 MCP이고, GPT는 그 위에 얹는 공개 포장층으로 생각하면 됩니다.

- Actions schema URL: `https://your-public-api-url/gpt-actions-openapi-v2.json`
- Privacy Policy URL: `https://your-public-api-url/privacy`
- 인증: `None`
- 추천 endpoint 집합: GPT 전용 요약 endpoint 3개
- 추천 endpoint 집합: GPT 전용 요약 endpoint 4개
  - `/gpt/places`
  - `/gpt/classrooms/empty`
  - `/gpt/notices`
  - `/gpt/restaurants/nearby`
- 기존 `gpt-actions-openapi.json`은 회귀용으로 유지되지만, Shared GPT는 v2 schema를 기본으로 사용

## 연결 후 바로 해볼 질문

- `성심교정 중앙도서관 위치 알려줘`
- `중도 어디야?`
- `학생식당 있는 건물 뭐야?`
- `니콜스관인데 지금 예상 빈 강의실 있어?`
- `2026년 1학기 객체지향 과목 찾아줘`
- `김가톨 교수 수업 알려줘`
- `최신 학사 공지 2개 보여줘`
- `장학 공지 최신순으로 3개 보여줘`
- `중앙도서관 근처 한식만 찾아줘`
- `중앙도서관에서 10분 안쪽에 1만원 이하 식당 보여줘`
- `성심교정 지하철 오는 길 알려줘`

## 기대 동작

- 최초 연결 시 OAuth 링크 화면이 뜨고 Google 로그인 후 사용합니다.
- 장소, 과목, 공지, 주변 식당, 교통 안내 조회
- 프로필 생성, 시간표 저장, admin 기능은 공개 서버에서 제공하지 않음

전체 100개 질문과 대표 리허설은 아래 문서를 보면 됩니다.

- [공개 MCP 100문장 테스트팩](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-test-pack-100.md)
- [공개 MCP 실행 리허설](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-rehearsal.md)
