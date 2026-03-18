# Connect From ChatGPT

## 연결 정보

- 이름 예시: `Songsim Campus MCP`
- URL: `https://your-public-mcp-url/mcp`
- 모드: read-only public server
- 로그인: 현재 공개 배포 기본값은 익명 read-only, 운영자가 OAuth 모드로 바꾸면 로그인 필요

## 먼저 무엇에 쓰나

- 건물명, 별칭, 시설명으로 장소 찾기
- 헬스장, 편의점, ATM, 복사실 같은 생활어로 관련 건물 찾기
- 강의동 기준 현재 공실 조회
- 학년도/학기 기준 개설과목 찾기
- 학사일정 조회
- 증명발급 안내 조회
- 장학제도 안내 조회
- 캠퍼스 출발지 기준 주변 식당 찾기
- 브랜드 상호로 카페/식당 직접 찾기
- 공식 학식 3곳의 이번 주 메뉴 조회
- 중앙도서관 열람실 좌석 현황 조회
- 건물별 WIFI 안내 조회
- 최신 공지와 교통 안내 조회
- 공개 서버는 read-only라서 profile, timetable, admin 기능은 제공하지 않음

## 추천 사용 흐름

1. `songsim://usage-guide` resource를 먼저 읽어 공개 MCP 범위를 확인
2. place / course / academic calendar / notice / restaurant / transport prompt 중 하나를 사용
3. prompt가 가리키는 tool을 호출하거나, 장학·증명·WIFI guide는 resource 또는 direct tool을 바로 사용

강의실 공실은 공식 실시간 source가 있으면 그 결과를 우선 쓰고, 없으면 시간표 기준 예상 공실로 자동 폴백합니다.

## GPT 링크로 공개하고 싶을 때

ChatGPT의 `chatgpt.com/g/...` 링크를 만들고 싶다면 MCP connector 대신 GPT Builder의 `Actions`를 사용할 수 있습니다. 다만 학생-facing 기본 입구는 MCP connector이고, GPT Actions는 선택적 포장층입니다.

- Actions schema URL: `https://your-public-api-url/gpt-actions-openapi-v2.json`
- Privacy Policy URL: `https://your-public-api-url/privacy`
- 인증: `None`
- Shared GPT를 정말 공개할 때만 이 경로를 쓰고, 일반 학생 사용 기준으로는 MCP connector를 먼저 권장합니다.
- 기존 `gpt-actions-openapi.json`은 회귀용으로 남아 있지만, 학생-facing 기본 문서에서는 전면에 두지 않습니다.

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
- `공지 카테고리 종류 알려줘`
- `employment랑 career 차이 설명해줘`
- `7교시가 몇 시야?`
- `7교시에 시작하는 과목 찾고 싶어`
- `2026학년도 3월 학사일정 보여줘`
- `재학증명서 발급 안내 알려줘`
- `장학제도 안내 알려줘`
- `니콜스관 WIFI 안내 알려줘`
- `최신 취업 공지 3개 보여줘`
- `학생식당 메뉴 보여줘`
- `카페 보나 이번 주 메뉴 알려줘`
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
교내 공식 학식 메뉴는 MCP connector 기준으로 `tool_search_dining_menus` 흐름으로 읽을 수 있고, `학생식당 메뉴`, `카페 보나 메뉴`, `부온 프란조 이번 주 메뉴` 같은 질문을 current-week 기준으로 처리합니다. 현재는 주간 텍스트와 원본 PDF 링크를 함께 안내합니다.
중앙도서관 열람실 좌석은 MCP connector 기준으로 `tool_get_library_seat_status` 흐름으로 best-effort 실시간 조회할 수 있습니다. source가 불안정하면 stale cache 또는 unavailable note가 함께 내려올 수 있습니다.
학사일정, 증명발급 안내, 장학제도, WIFI 안내는 MCP connector에서 각각 academic calendar / guide tool과 resource로 바로 읽을 수 있고, HTTP companion에서는 `/academic-calendar`, `/certificate-guides`, `/scholarship-guides`, `/wifi-guides`를 씁니다.
교시 기반 과목 조회는 `/courses?year=2026&semester=1&period_start=7` 같은 direct filter를 함께 쓸 수 있습니다. 카테고리와 교시표 같은 메타데이터는 필요할 때만 확인하면 됩니다.

## 기대 동작

- 현재 공개 기본 배포는 익명 read-only라서 바로 연결되는 것이 정상입니다.
- 운영자가 OAuth 모드로 바꾸면 로그인 화면이 다시 나타날 수 있습니다.
- 장소, 과목, 학사일정, 증명발급, 장학제도, WIFI 안내, 공지, 주변 식당, 교통 안내 조회
- 강의실 공실은 realtime 또는 estimated fallback 여부가 응답 note와 `availability_mode`에 함께 표시됩니다.
- 프로필 생성, 시간표 저장, admin 기능은 공개 서버에서 제공하지 않음

전체 검증 자산은 `docs/qa/` 아래에서 운영합니다. Shared GPT는 이 질문 전부를 게이트로 삼지 않고, 릴리즈팩 중 핵심 10~15문장만 샘플 확인합니다.

- [공개 MCP 500문장 코퍼스](qa/public-mcp-corpus-500.md)
- [공개 MCP 릴리즈팩 50](qa/public-mcp-release-pack-50.md)
- [공개 MCP 라이브 판정표 50](qa/public-mcp-live-validation-50.md)
- [공개 MCP 라이브 판정 요약](qa/public-mcp-live-validation-summary.md)
