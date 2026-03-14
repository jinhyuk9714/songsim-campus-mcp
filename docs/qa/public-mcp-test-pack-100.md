# Public MCP Test Pack (100)

공개 `public_readonly` MCP를 실제 사용자 질문 기준으로 검증하기 위한 100문장 테스트팩입니다. 각 케이스는 `expected_first_step`, `expected_tool_chain`, `pass_criteria`, `common_failure_modes`를 함께 고정합니다.

## 기준

- 대상: public read-only MCP
- 표면: tool 7개, prompt 5개, resource 6개
- 언어: 한국어 중심, 일부 오타/영문 혼용 포함
- 판정 기준: MCP contract 기준
  - 자연어 최종 답변 품질이 아니라, 올바른 prompt/resource/tool flow로 도달하는지를 먼저 봅니다.

## 분포 요약

| Domain | Count |
| --- | ---: |
| 장소 | 25 |
| 과목 | 20 |
| 공지 | 20 |
| 주변 식당 | 20 |
| 교통 | 10 |
| 범위 밖/거절/애매한 요청 | 5 |

| Style | Count |
| --- | ---: |
| normal | 45 |
| ambiguous | 20 |
| composite | 20 |
| typo | 10 |
| out_of_scope | 5 |

## 표기 규칙

- `expected_first_step`
  - `resource:...`
  - `prompt:...`
  - `tool:...`
- `expected_tool_chain`
  - prompt/resource 이후에 따라야 하는 이상적인 흐름입니다.
- `pass_criteria`
  - 실제 답변 문장보다 MCP contract 충족 여부를 짧게 적습니다.

## 장소 25

| ID | Style | User utterance | Intent | Expected first step | Expected tool chain | Pass criteria | Common failure modes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P01 | normal | 성심교정 중앙도서관 위치 알려줘 | 대표 도서관 찾기 | `prompt:prompt_find_place` | `prompt_find_place -> tool_search_places -> tool_get_place` | `central-library` 후보가 잡히고 slug까지 이어짐 | tool selection ambiguity, payload gap |
| P02 | normal | 중앙도서관 정보 찾아줘 | 대표 장소 요약 | `tool:tool_search_places` | `tool_search_places -> tool_get_place` | 중앙도서관 1건 이상, 상세 요약 가능 | empty result, wording issue |
| P03 | normal | 학생회관 어디야? | 학생회관 위치 | `prompt:prompt_find_place` | `prompt_find_place -> tool_search_places -> tool_get_place` | `student-center` 후보와 상세 조회 가능 | empty result |
| P04 | normal | 정문 위치 알려줘 | 정문 위치 확인 | `tool:tool_search_places` | `tool_search_places -> tool_get_place` | `main-gate` 또는 한국어 정문 후보가 나옴 | missing alias |
| P05 | normal | 니콜스관 설명해줘 | 니콜스관 상세 | `tool:tool_search_places` | `tool_search_places -> tool_get_place` | `nichols-hall` 후보와 상세 요약 가능 | empty result |
| P06 | ambiguous | 중도 어디야? | alias 기반 도서관 찾기 | `prompt:prompt_find_place` | `prompt_find_place -> tool_search_places -> tool_get_place` | alias `중도`로 중앙도서관 후보가 잡힘 | missing alias |
| P07 | ambiguous | 도서관 있잖아 그 건물 위치 | 직전 맥락 없는 도서관 지시 | `prompt:prompt_find_place` | `prompt_find_place -> tool_search_places` | 도서관 관련 후보 1개 이상 | tool selection ambiguity |
| P08 | ambiguous | 학생식당 있는 건물 뭐야? | 시설 별칭으로 건물 찾기 | `prompt:prompt_find_place` | `prompt_find_place -> tool_search_places` | 학생회관 후보가 포함됨 | missing alias |
| P09 | ambiguous | 입구 어디야 | 막연한 출입구 찾기 | `prompt:prompt_find_place` | `prompt_find_place -> tool_search_places` | gate 성격 후보 1개 이상 | tool selection ambiguity, empty result |
| P10 | ambiguous | N관이 뭐였지? | 약칭 alias 해석 | `prompt:prompt_find_place` | `prompt_find_place -> tool_search_places -> tool_get_place` | `nichols-hall` 후보가 alias로 잡힘 | missing alias |
| P11 | normal | 김수환관 위치 알려줘 | 다른 강의동 위치 | `tool:tool_search_places` | `tool_search_places -> tool_get_place` | `kim-soo-hwan-hall` 후보가 잡힘 | empty result |
| P12 | normal | 도서관 alias 뭐 있어? | 별칭 확인 | `tool:tool_search_places` | `tool_search_places -> tool_get_place` | aliases 필드에 별칭이 포함됨 | payload gap |
| P13 | composite | 도서관 말고 편의시설 위주로 찾아줘 | category 기반 시설 검색 | `prompt:prompt_find_place` | `prompt_find_place -> tool_search_places` | `category=facility` 성격 후보가 반환됨 | category mismatch |
| P14 | composite | gate 카테고리만 보여줘 | gate category 확인 | `resource:songsim://place-categories` | `songsim://place-categories -> tool_search_places` | gate 의미 설명 또는 gate 결과가 이어짐 | resource ignored |
| P15 | composite | library category로 2개만 보여줘 | category + limit 조합 | `resource:songsim://place-categories` | `songsim://place-categories -> tool_search_places` | library category 설명 후 결과 2개 이내 | category mismatch |
| P16 | composite | facility category로 학생회관 찾아줘 | category + exact target | `prompt:prompt_find_place` | `prompt_find_place -> tool_search_places -> tool_get_place` | facility 범주에서 학생회관 후보 확인 | tool selection ambiguity |
| P17 | composite | building 카테고리에서 김수환 들어가는 곳 찾아줘 | category + query 조합 | `prompt:prompt_find_place` | `prompt_find_place -> tool_search_places` | building 범주 후보 중 김수환관이 나옴 | category mismatch |
| P18 | normal | 학생식당 있는 곳 이름 알려줘 | 별칭으로 장소 이름만 찾기 | `tool:tool_search_places` | `tool_search_places` | 학생회관 또는 학생식당 alias 가진 후보가 나옴 | missing alias |
| P19 | typo | 중앙 도서 관 위치 | 띄어쓰기 오류 | `prompt:prompt_find_place` | `prompt_find_place -> tool_search_places` | ideally 중앙도서관 후보가 잡혀야 함 | missing alias, wording issue |
| P20 | typo | 니콜스 관 어디 | 띄어쓰기 오류 alias | `prompt:prompt_find_place` | `prompt_find_place -> tool_search_places` | ideally 니콜스관 후보가 나옴 | missing alias |
| P21 | normal | 학회관 정보 알려줘 | alias 기반 학생회관 | `tool:tool_search_places` | `tool_search_places -> tool_get_place` | `student-center` 후보가 alias로 잡힘 | missing alias |
| P22 | normal | 학교 정문 slug까지 알려줘 | 이름 + slug 요청 | `tool:tool_search_places` | `tool_search_places -> tool_get_place` | `main-gate` slug 확보 가능 | payload gap |
| P23 | normal | 중앙도서관 좌표 알려줘 | 좌표 확인 | `tool:tool_search_places` | `tool_search_places -> tool_get_place` | coordinates 필드가 채워짐 | payload gap |
| P24 | normal | K관 위치 알려줘 | 약칭 기반 건물 찾기 | `prompt:prompt_find_place` | `prompt_find_place -> tool_search_places -> tool_get_place` | K관 alias로 김수환관 후보가 잡힘 | missing alias |
| P25 | normal | place category에서 library가 무슨 뜻이야? | category 설명 | `resource:songsim://place-categories` | `songsim://place-categories` | `library` 의미 설명이 바로 가능 | resource ignored |

## 과목 20

| ID | Style | User utterance | Intent | Expected first step | Expected tool chain | Pass criteria | Common failure modes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| C01 | normal | 2026년 1학기 객체지향 과목 찾아줘 | 학기 지정 과목 검색 | `prompt:prompt_search_courses` | `prompt_search_courses -> tool_search_courses` | year/semester가 반영된 객체지향 결과 1개 이상 | tool selection ambiguity |
| C02 | normal | 데이터베이스 수업 보여줘 | 과목명 검색 | `tool:tool_search_courses` | `tool_search_courses` | `데이터베이스` 결과 1개 이상 | empty result |
| C03 | normal | CSE420 과목 뭐야 | 과목코드 검색 | `tool:tool_search_courses` | `tool_search_courses` | code `CSE420` 결과 1개 이상 | empty result |
| C04 | normal | 홍길동 교수 수업 알려줘 | 교수명 검색 | `tool:tool_search_courses` | `tool_search_courses` | professor `홍길동` 결과 1개 이상 | wording issue |
| C05 | normal | 김가톨 교수 수업 알려줘 | 교수명 검색 | `tool:tool_search_courses` | `tool_search_courses` | professor `김가톨` 결과 1개 이상 | wording issue |
| C06 | normal | 박요셉 교수 과목 보여줘 | 교수명 검색 | `tool:tool_search_courses` | `tool_search_courses` | professor `박요셉` 결과 1개 이상 | wording issue |
| C07 | normal | 소프트웨어공학 2분반 있어? | title + section 확인 | `tool:tool_search_courses` | `tool_search_courses` | `소프트웨어공학` 결과와 section 확인 가능 | payload gap |
| C08 | normal | 2026년 1학기 과목 전체 보여줘 | 빈 query + 학기 필터 | `prompt:prompt_search_courses` | `prompt_search_courses -> tool_search_courses` | 2026-1 결과 목록이 반환됨 | tool selection ambiguity |
| C09 | normal | 객체지향 수업 시간표 알려줘 | 과목 검색 후 schedule 확인 | `tool:tool_search_courses` | `tool_search_courses` | raw_schedule 또는 course_summary로 시간 확인 가능 | payload gap |
| C10 | normal | 7교시는 몇 시야? | 교시표 조회 | `resource:songsim://class-periods` | `songsim://class-periods` | 7교시 start/end 확인 가능 | resource ignored |
| C11 | ambiguous | 김 교수님 데이터 쪽 수업 | 부분 교수명 + 주제 | `prompt:prompt_search_courses` | `prompt_search_courses -> tool_search_courses` | 관련 course 후보가 최소 1개 반환됨 | tool selection ambiguity, empty result |
| C12 | ambiguous | 객체지향 그거 이번 학기 열려? | 맥락 불완전 과목 확인 | `prompt:prompt_search_courses` | `prompt_search_courses -> tool_search_courses` | 현재 지정 학기면 해당 결과가 조회됨 | missing year/semester |
| C13 | ambiguous | 이 과목 몇 분반이야? 데이터베이스 | 분반 확인 | `prompt:prompt_search_courses` | `prompt_search_courses -> tool_search_courses` | 데이터베이스 결과에서 section 확인 가능 | payload gap |
| C14 | ambiguous | 과목코드로도 찾을 수 있어? CSE301 | code 검색 가능 여부 | `prompt:prompt_search_courses` | `prompt_search_courses -> tool_search_courses` | code 기반 검색 결과가 반환됨 | tool selection ambiguity |
| C15 | composite | 2026년 1학기 객체지향이면서 홍길동 교수인 거 찾아줘 | query + year + semester + professor | `prompt:prompt_search_courses` | `prompt_search_courses -> tool_search_courses` | 객체지향/홍길동/2026-1 결과가 맞아야 함 | filter mismatch |
| C16 | composite | CSE332면서 김가톨 교수인 과목 보여줘 | code + professor 조합 | `tool:tool_search_courses` | `tool_search_courses` | 동일 row가 조건을 함께 만족 | filter mismatch |
| C17 | composite | 2026년 1학기 박요셉 교수 수업 1개만 | year + semester + professor + limit | `prompt:prompt_search_courses` | `prompt_search_courses -> tool_search_courses` | limit 1, 박요셉 결과가 우선 반환 | limit ignored |
| C18 | composite | CSE401 화7~9 맞는지 확인해줘 | code 조회 후 schedule 검증 | `tool:tool_search_courses` | `tool_search_courses` | CSE401 결과와 `화7~9` schedule 확인 가능 | payload gap |
| C19 | typo | 데이타베이스 과목 있어? | 오타 title 검색 | `prompt:prompt_search_courses` | `prompt_search_courses -> tool_search_courses` | ideally 데이터베이스 후보가 잡힘 | wording issue, empty result |
| C20 | typo | 객채지향 설계 찾아줘 | 오타 title 검색 | `prompt:prompt_search_courses` | `prompt_search_courses -> tool_search_courses` | ideally 객체지향프로그래밍설계 후보가 잡힘 | wording issue, empty result |

## 공지 20

| ID | Style | User utterance | Intent | Expected first step | Expected tool chain | Pass criteria | Common failure modes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| N01 | normal | 최신 학사 공지 2개 보여줘 | academic 공지 최신순 | `prompt:prompt_latest_notices` | `prompt_latest_notices -> tool_list_latest_notices` | academic filter + limit 2가 반영됨 | category mismatch |
| N02 | normal | 최신 장학 공지 3개 보여줘 | scholarship 공지 | `prompt:prompt_latest_notices` | `prompt_latest_notices -> tool_list_latest_notices` | scholarship filter + limit 3 | category mismatch |
| N03 | normal | 최신 취업 공지 3개 보여줘 | employment 공지 | `prompt:prompt_latest_notices` | `prompt_latest_notices -> tool_list_latest_notices` | employment filter + limit 3 | category mismatch |
| N04 | normal | 최신 도서관 공지 2개 보여줘 | library 공지 | `prompt:prompt_latest_notices` | `prompt_latest_notices -> tool_list_latest_notices` | library filter + limit 2 | category mismatch |
| N05 | normal | 최신 공지 5개 보여줘 | 전체 최신 공지 | `tool:tool_list_latest_notices` | `tool_list_latest_notices` | limit 5 이내 최신순 결과 | limit ignored |
| N06 | normal | academic 공지 최신순으로 보여줘 | 영문 category 사용 | `tool:tool_list_latest_notices` | `tool_list_latest_notices` | academic category 결과 | category mismatch |
| N07 | normal | scholarship 공지 보여줘 | 영문 장학 category | `tool:tool_list_latest_notices` | `tool_list_latest_notices` | scholarship 결과가 반환됨 | category mismatch |
| N08 | normal | employment 카테고리 공지 보여줘 | 영문 취업 category | `tool:tool_list_latest_notices` | `tool_list_latest_notices` | employment 결과가 반환됨 | category mismatch |
| N09 | normal | library 카테고리 공지 있어? | 영문 도서관 category | `tool:tool_list_latest_notices` | `tool_list_latest_notices` | library 결과가 반환됨 | category mismatch |
| N10 | normal | notice category label 뭐 있는지 보여줘 | category 설명 | `resource:songsim://notice-categories` | `songsim://notice-categories` | category label 매핑 설명 가능 | resource ignored |
| N11 | ambiguous | 장학 쪽 새 소식 있나 | 느슨한 장학 표현 | `prompt:prompt_latest_notices` | `prompt_latest_notices -> tool_list_latest_notices` | scholarship 흐름으로 좁혀짐 | tool selection ambiguity |
| N12 | ambiguous | 취업 관련 최신 글 있어? | 취업 표현 완화 | `prompt:prompt_latest_notices` | `prompt_latest_notices -> tool_list_latest_notices` | employment 흐름으로 연결됨 | tool selection ambiguity |
| N13 | ambiguous | 도서관 관련 공지 있나 | 도서관 관련 표현 | `prompt:prompt_latest_notices` | `prompt_latest_notices -> tool_list_latest_notices` | library 흐름으로 연결됨 | tool selection ambiguity |
| N14 | ambiguous | 최근 공지 중 중요한 거만 보여줘 | 중요도 기준 불명확 | `prompt:prompt_latest_notices` | `prompt_latest_notices -> tool_list_latest_notices` | 최소 최신 공지 조회 흐름으로 유도 | unsupported ranking |
| N15 | composite | 장학만 3개 최신순으로 보여줘 | category + limit + 정렬 | `prompt:prompt_latest_notices` | `prompt_latest_notices -> tool_list_latest_notices` | scholarship + limit 3 | limit ignored |
| N16 | composite | academic 말고 library 2개만 | category 전환 + limit | `resource:songsim://notice-categories` | `songsim://notice-categories -> tool_list_latest_notices` | library 2개 이내 결과 | category confusion |
| N17 | composite | 취업 공지 2개만 source_url 같이 보여줘 | category + limit + 링크 확인 | `tool:tool_list_latest_notices` | `tool_list_latest_notices` | source_url 포함한 employment 결과 | payload gap |
| N18 | composite | 최신 공지 3개 보여주고 category_display도 같이 써줘 | 전체 latest + display label | `tool:tool_list_latest_notices` | `tool_list_latest_notices` | category_display 필드 활용 가능 | payload gap |
| N19 | typo | 장확 공지 최신순 | 오타 category | `prompt:prompt_latest_notices` | `prompt_latest_notices -> tool_list_latest_notices` | ideally scholarship 흐름으로 연결 | wording issue |
| N20 | typo | 도서관 공지 잇나 | 오타 포함 도서관 질문 | `prompt:prompt_latest_notices` | `prompt_latest_notices -> tool_list_latest_notices` | ideally library 결과 조회 | wording issue |

## 주변 식당 20

| ID | Style | User utterance | Intent | Expected first step | Expected tool chain | Pass criteria | Common failure modes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R01 | normal | 중앙도서관 근처 밥집 추천해줘 | 기본 nearby 추천 | `prompt:prompt_find_nearby_restaurants` | `prompt_find_nearby_restaurants -> tool_find_nearby_restaurants` | origin 해석 후 식당 후보 1개 이상 | tool selection ambiguity |
| R02 | normal | 중앙도서관 근처 한식 보여줘 | category 필터 | `prompt:prompt_find_nearby_restaurants` | `prompt_find_nearby_restaurants -> tool_find_nearby_restaurants` | `category=korean` 결과 반환 | category mismatch |
| R03 | normal | 중앙도서관 근처 카페 보여줘 | 카페 검색 | `prompt:prompt_find_nearby_restaurants` | `prompt_find_nearby_restaurants -> tool_find_nearby_restaurants` | `category=cafe` 결과 반환 | category mismatch |
| R04 | normal | 학생회관 근처 식당 추천해줘 | 다른 origin nearby | `prompt:prompt_find_nearby_restaurants` | `prompt_find_nearby_restaurants -> tool_find_nearby_restaurants` | `origin=student-center` 해석 가능 | missing origin |
| R05 | normal | 정문 근처 1만원 이하 밥집 | origin + budget | `prompt:prompt_find_nearby_restaurants` | `prompt_find_nearby_restaurants -> tool_find_nearby_restaurants` | `budget_max=10000` 조건 유지 | budget ignored |
| R06 | normal | 니콜스관 근처 라멘집 찾아줘 | origin + category 해석 | `prompt:prompt_find_nearby_restaurants` | `prompt_find_nearby_restaurants -> tool_find_nearby_restaurants` | japanese 성격 결과 또는 0건 명확화 | category mismatch |
| R07 | normal | 중앙도서관에서 걸어서 가까운 곳만 | 짧은 도보 중심 | `prompt:prompt_find_nearby_restaurants` | `prompt_find_nearby_restaurants -> tool_find_nearby_restaurants` | walk_minutes를 보수적으로 적용 가능 | walk filter ignored |
| R08 | normal | 중앙도서관 근처 오픈한 곳 말고 전체 보여줘 | open_now false 기본 | `tool:tool_find_nearby_restaurants` | `tool_find_nearby_restaurants` | open_now 미적용 전체 결과 | filter confusion |
| R09 | ambiguous | 중도 근처 밥집 | alias origin nearby | `prompt:prompt_find_nearby_restaurants` | `prompt_find_nearby_restaurants -> tool_search_places -> tool_find_nearby_restaurants` | ideally `중도 -> 중앙도서관` 후 nearby | missing alias, unsupported origin |
| R10 | ambiguous | 학교 입구 근처 먹을 데 | 입구 표현 해석 | `prompt:prompt_find_nearby_restaurants` | `prompt_find_nearby_restaurants -> tool_search_places -> tool_find_nearby_restaurants` | `입구 -> 정문` 또는 gate 후보로 이어짐 | missing alias |
| R11 | ambiguous | 아침에 간단히 먹을 데 있어? | origin 빠진 추천 요청 | `resource:songsim://usage-guide` | `songsim://usage-guide -> prompt_find_nearby_restaurants` | origin 필요성을 설명하고 flow 제시 | unsupported scope |
| R12 | ambiguous | 가성비 좋은 데 추천해줘 | origin/제약 빠진 추상 요청 | `resource:songsim://usage-guide` | `songsim://usage-guide -> prompt_find_nearby_restaurants` | origin, budget_max를 물을 수 있어야 함 | unsupported scope |
| R13 | composite | 중앙도서관에서 10분 안쪽 한식 | origin + walk + category | `prompt:prompt_find_nearby_restaurants` | `prompt_find_nearby_restaurants -> tool_find_nearby_restaurants` | `walk_minutes=10`, `category=korean` 유지 | filter mismatch |
| R14 | composite | 중앙도서관에서 10분 안쪽 1만원 이하 한식 | origin + walk + budget + category | `prompt:prompt_find_nearby_restaurants` | `prompt_find_nearby_restaurants -> tool_find_nearby_restaurants` | 세 조건이 동시에 유지됨 | budget ignored, filter mismatch |
| R15 | composite | 중앙도서관 기준 지금 열어있는 카페 | origin + category + open_now + at | `prompt:prompt_find_nearby_restaurants` | `prompt_find_nearby_restaurants -> tool_find_nearby_restaurants` | open_now true 필터와 at 처리 | timestamp parse error, hours gap |
| R16 | composite | 정문 말고 중앙도서관 기준으로 15분 안 양식 | 기준점 수정 + walk + category | `prompt:prompt_find_nearby_restaurants` | `prompt_find_nearby_restaurants -> tool_find_nearby_restaurants` | origin `central-library`, walk 15, western | tool selection ambiguity |
| R17 | composite | 학생회관 기준 budget_max 8000 open_now true | 영문 파라미터 감각 포함 | `prompt:prompt_find_nearby_restaurants` | `prompt_find_nearby_restaurants -> tool_find_nearby_restaurants` | budget/open_now 조합이 유지됨 | wording issue, hours gap |
| R18 | typo | 중앵도서관 근처 밥집 | 오타 origin | `prompt:prompt_find_nearby_restaurants` | `prompt_find_nearby_restaurants -> tool_search_places -> tool_find_nearby_restaurants` | ideally 중앙도서관으로 복구 | missing alias |
| R19 | typo | 니콜스 근처 라면집 | 오타/구어체 category | `prompt:prompt_find_nearby_restaurants` | `prompt_find_nearby_restaurants -> tool_find_nearby_restaurants` | japanese 성격 결과 또는 명확한 0건 | wording issue |
| R20 | typo | 중도 근처 라멘집 | alias origin + category | `prompt:prompt_find_nearby_restaurants` | `prompt_find_nearby_restaurants -> tool_search_places -> tool_find_nearby_restaurants` | ideally alias 해석 후 nearby | missing alias, unsupported origin |

## 교통 10

| ID | Style | User utterance | Intent | Expected first step | Expected tool chain | Pass criteria | Common failure modes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T01 | normal | 성심교정 지하철 오는 길 알려줘 | subway guide | `prompt:prompt_transport_guide` | `prompt_transport_guide -> tool_list_transport_guides` | `mode=subway` guide 1개 이상 | tool selection ambiguity |
| T02 | normal | 성심교정 버스 오는 길 알려줘 | bus guide | `prompt:prompt_transport_guide` | `prompt_transport_guide -> tool_list_transport_guides` | `mode=bus` guide 1개 이상 | tool selection ambiguity |
| T03 | normal | 지하철 안내 보여줘 | subway guide 조회 | `tool:tool_list_transport_guides` | `tool_list_transport_guides` | subway 결과 반환 | mode mismatch |
| T04 | normal | 버스 안내 보여줘 | bus guide 조회 | `tool:tool_list_transport_guides` | `tool_list_transport_guides` | bus 결과 반환 | mode mismatch |
| T05 | ambiguous | 역곡역에서 오는 법? | subway/bus 중 하나 유도 | `prompt:prompt_transport_guide` | `prompt_transport_guide -> tool_list_transport_guides` | 정적 transit guide surface로 연결 | tool selection ambiguity |
| T06 | ambiguous | 대중교통으로 어떻게 와? | transit 범위 확인 | `prompt:prompt_transport_guide` | `prompt_transport_guide -> tool_list_transport_guides` | bus/subway 안내로 연결 | unsupported live routing |
| T07 | ambiguous | 1호선으로 오면 돼? | subway guide 탐색 | `prompt:prompt_transport_guide` | `prompt_transport_guide -> tool_list_transport_guides` | subway guide로 연결 | tool selection ambiguity |
| T08 | composite | 버스 말고 지하철만 보여줘 | mode exclusion | `prompt:prompt_transport_guide` | `prompt_transport_guide -> tool_list_transport_guides` | `mode=subway`만 조회 | mode mismatch |
| T09 | composite | subway 1개만 보여줘 | 영문 mode + limit | `prompt:prompt_transport_guide` | `prompt_transport_guide -> tool_list_transport_guides` | `mode=subway`, `limit=1` 유지 | wording issue |
| T10 | typo | 지하철 오느 ㄴ길 | 오타 포함 교통 요청 | `prompt:prompt_transport_guide` | `prompt_transport_guide -> tool_list_transport_guides` | subway guide로 연결 가능 | wording issue |

## 범위 밖/거절/애매한 요청 5

| ID | Style | User utterance | Intent | Expected first step | Expected tool chain | Pass criteria | Common failure modes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| X01 | out_of_scope | 내 프로필 만들고 시간표 저장해줘 | profile/timetable mutation | `resource:songsim://usage-guide` | `songsim://usage-guide` | read-only public MCP라 불가 범위를 설명 가능 | unsupported scope not explained |
| X02 | out_of_scope | 관리자 sync 돌려줘 | admin action 요청 | `resource:songsim://usage-guide` | `songsim://usage-guide` | admin 제외를 분명히 설명 | unsupported scope not explained |
| X03 | out_of_scope | 개인화 공지 추천해줘 | local_full personalization 요청 | `resource:songsim://usage-guide` | `songsim://usage-guide` | personalization 제외 범위를 설명 | unsupported scope not explained |
| X04 | out_of_scope | meal recommendation 개인화로 해줘 | meal personalization 요청 | `resource:songsim://usage-guide` | `songsim://usage-guide` | read-only public surface 한계를 설명 | unsupported scope not explained |
| X05 | out_of_scope | 수강신청 정정 공지를 제목으로 정확히 찾아줘 | title/keyword notice search gap | `resource:songsim://usage-guide` | `songsim://usage-guide -> prompt_latest_notices` | 최신/category surface만 가능하다고 제한 설명 | unsupported scope, tool overreach |

## 활용 팁

- 100개를 한 번에 돌리기보다, 각 도메인에서 `normal -> ambiguous -> composite -> typo` 순서로 돌리면 흐름을 빨리 파악할 수 있습니다.
- `resource`와 `prompt`를 먼저 읽는 패턴이 정착되어야 `tool` 선택 안정성이 올라갑니다.
- `out_of_scope` 케이스는 “거절”이 아니라 `public read-only MCP 범위 설명`까지 포함되어야 통과로 봅니다.
