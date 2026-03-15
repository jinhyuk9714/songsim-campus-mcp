# Connect From ChatGPT

## 연결 정보

- 이름 예시: `Songsim Campus MCP`
- URL: `https://your-public-mcp-url/mcp`
- 모드: read-only public server
- 로그인: Auth0 + Google login

## 먼저 무엇에 쓰나

- 건물명, 별칭, 시설명으로 장소 찾기
- 헬스장, 편의점, ATM, 복사실 같은 생활어로 관련 건물 찾기
- 강의동 기준 현재 공실 조회
- 학년도/학기 기준 개설과목 찾기
- 캠퍼스 출발지 기준 주변 식당 찾기
- 브랜드 상호로 카페/식당 직접 찾기
- 최신 공지와 교통 안내 조회
- 공개 서버는 read-only라서 profile, timetable, admin 기능은 제공하지 않음

## 추천 사용 흐름

1. `songsim://usage-guide` resource를 먼저 읽어 공개 MCP 범위를 확인
2. place / course / notice / restaurant / transport prompt 중 하나를 사용
3. prompt가 가리키는 tool을 호출해 실제 조회

강의실 공실은 공식 실시간 source가 있으면 그 결과를 우선 쓰고, 없으면 시간표 기준 예상 공실로 자동 폴백합니다.

## GPT 링크로 공개하고 싶을 때

ChatGPT의 `chatgpt.com/g/...` 링크를 만들고 싶다면 MCP connector 대신 GPT Builder의 `Actions`를 사용합니다. 다만 제품의 기본 표면은 MCP이고, GPT는 그 위에 얹는 공개 포장층으로 생각하면 됩니다.

- Actions schema URL: `https://your-public-api-url/gpt-actions-openapi-v2.json`
- Privacy Policy URL: `https://your-public-api-url/privacy`
- 인증: `None`
- 추천 endpoint 집합: GPT 전용 요약 endpoint 4개
- 추천 endpoint 집합: GPT 전용 요약 endpoint 5개
  - `/gpt/places`
  - `/gpt/classrooms/empty`
  - `/gpt/notices`
  - `/gpt/restaurants/search`
  - `/gpt/restaurants/nearby`
- 기존 `gpt-actions-openapi.json`은 회귀용으로 유지되지만, Shared GPT는 v2 schema를 기본으로 사용

## 연결 후 바로 해볼 질문

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
브랜드 direct search는 `origin`이 없어도 캠퍼스에 가까운 후보를 먼저 보여줍니다. `스타벅스`, `커피빈`, `투썸`, `빽다방` 같은 브랜드도 같은 흐름으로 검색할 수 있습니다.

## 기대 동작

- 최초 연결 시 OAuth 링크 화면이 뜨고 Google 로그인 후 사용합니다.
- 장소, 과목, 공지, 주변 식당, 교통 안내 조회
- 강의실 공실은 realtime 또는 estimated fallback 여부가 응답 note와 `availability_mode`에 함께 표시됩니다.
- 프로필 생성, 시간표 저장, admin 기능은 공개 서버에서 제공하지 않음

전체 검증 자산은 `docs/qa/` 아래에서 운영합니다. Shared GPT는 이 질문 전부를 게이트로 삼지 않고, 릴리즈팩 중 핵심 10~15문장만 샘플 확인합니다.

- [공개 MCP 500문장 코퍼스](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-corpus-500.md)
- [공개 MCP 릴리즈팩 50](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-release-pack-50.md)
- [공개 MCP 라이브 판정표 50](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-live-validation-50.md)
- [공개 MCP 라이브 판정 요약](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-live-validation-summary.md)
