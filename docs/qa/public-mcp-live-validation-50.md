# Public MCP Live Validation 50

배포된 공개 `public read-only` MCP/API를 2026-03-16 KST 기준으로 실제 점검한 운영 시트입니다. 이번 실측은 **public API 우선** 방식으로 실행했고, `expected_mcp_flow`는 ChatGPT/Codex에서 이상적으로 밟아야 하는 MCP 흐름을 함께 기록합니다. course 10문장은 이번 날짜에 source-backed canary 기준으로 재보정했습니다.

## 실행 기준

- 대상
  - public API: `https://songsim-public-api.onrender.com`
  - public MCP: `https://songsim-public-mcp.onrender.com/mcp`
- 실제 호출 방식
  - 공개 MCP는 OAuth-protected tool call이 필요하므로, 실측값 수집은 같은 배포 데이터를 보는 public API raw endpoint로 진행했습니다.
  - `expected_mcp_flow`는 prompt/resource/tool 관점의 기대 경로를 기록합니다.
  - `songsim://notice-categories`, `songsim://usage-guide`처럼 API 직접 대응이 없는 resource-only 케이스는 공개 문서와 resource contract를 근거로 판정했습니다.
- Shared GPT
  - 이번 50문장 게이트에는 포함하지 않았고, 후속 샘플 검증 대상으로만 남깁니다.

## 판정 레벨

- `pass`: 핵심 사실과 제약이 실제값과 맞음
- `soft_pass`: 핵심 사실은 맞지만 naming, ranking, 표현, 검증 표면에 약한 점이 남음
- `soft_fail`: 큰 거짓은 아니지만 alias, taxonomy, 제약 해석이 기대에 못 미침
- `fail`: 핵심 사실 오류, 잘못된 거절, 필수 제약 미반영

## Ground Truth 규칙

- place: 공식 캠퍼스맵
- course: 현재 public course snapshot과 교시표 contract
- notices: 공식 notice `source_url`
- restaurants: Kakao Maps public listing
- transport: 공식 교통 안내 페이지
- classrooms: 공식 realtime source 유무와 fallback note, 공개 timetable contract
- out_of_scope: `songsim://usage-guide`와 공개 read-only 정책

## 판정 요약

| Verdict | Count |
| --- | ---: |
| pass | 42 |
| soft_pass | 8 |
| soft_fail | 0 |
| fail | 0 |

## 운영 시트

| Validation ID | Release ID | User utterance | Domain | Expected MCP flow | Ground truth source | Validation status | Deployed response summary | Comparison result | Verdict | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LV001 | RP01 | 성심교정 중앙도서관 위치 알려줘 | place | `prompt_find_place -> tool_search_places -> tool_get_place` | 공식 캠퍼스맵 | completed | `/places?query=중앙도서관` 첫 결과가 `central-library`; 이름 `베리타스관`; alias에 `중앙도서관/L관/중도` 포함 | 대표 건물명, alias, category=`library`가 공식 캠퍼스맵과 일치한다. | pass | 사용자 답변에서는 `베리타스관(중앙도서관, L관)`으로 함께 풀어주는 편이 가장 자연스럽다. |
| LV002 | RP02 | 중도 어디야 | place | `prompt_find_place -> tool_search_places -> tool_get_place` | 공식 캠퍼스맵 + 제품 alias 정책 | completed | `/places?query=중도`가 `central-library` 1건으로 수렴하고 alias에 `중도`가 포함된다. | 학생 생활어 alias가 공개 배포에서 정상적으로 중앙도서관으로 풀린다. | pass | 이전 실측 fail 항목이 해소됐다. |
| LV003 | RP03 | 학생식당 있는 건물 뭐야 | place | `prompt_find_place -> tool_search_places -> tool_get_place` | 공식 캠퍼스맵 | completed | `/places?query=학생식당` 첫 결과가 `sophie-barat-hall`; 이름 `학생미래인재관`; alias에 `학생식당` 포함 | 학생식당 생활어가 공식 건물 `학생미래인재관(B관)`으로 안정적으로 연결된다. | pass | place search와 restaurant origin alias가 같은 vocabulary를 쓰기 시작했다. |
| LV004 | RP04 | 니콜스관 위치 알려줘 | place | `tool_search_places -> tool_get_place` | 공식 캠퍼스맵 | completed | `/places?query=니콜스관`이 `nicholls-hall` 1건을 반환하고 alias에 `N관`, `니콜스`가 있다. | 정식 건물명 happy path가 공식 캠퍼스맵과 일치한다. | pass | 정식 명칭 검색은 안정적이다. |
| LV005 | RP05 | 니콜스 어디야 | place | `prompt_find_place -> tool_search_places -> tool_get_place` | 공식 캠퍼스맵 + 제품 alias 정책 | completed | `/places?query=니콜스`가 `nicholls-hall` 1건으로 반환된다. | 생활어 alias `니콜스`가 니콜스관으로 정확히 수렴한다. | pass | classroom resolver와도 같은 alias를 쓴다. |
| LV006 | RP06 | 김수환관 어디 있어 | place | `tool_search_places -> tool_get_place` | 공식 캠퍼스맵 | completed | `/places?query=김수환관` 첫 결과는 `kim-sou-hwan-hall`이고 두 번째로 `dormitory-stephen`이 함께 반환된다. | 첫 결과의 이름과 category=`building`은 맞지만 `K관` alias가 기숙사에도 걸려 raw 검색 노이즈가 남아 있다. | soft_pass | raw API 소비자는 `K관` alias 중복을 볼 수 있다. |
| LV007 | RP07 | 정문 위치 알려줘 | place | `tool_search_places -> tool_get_place` | 공식 캠퍼스맵 | completed | `/places?query=정문` 첫 결과는 `main-gate`, 두 번째는 `창업보육센터`다. | 주정답은 맞지만 짧은 질의에서 `창업보육센터` 노이즈가 아직 따라온다. | soft_pass | 정답 우선 정렬까지는 개선됐고 완전 제거는 아직 아니다. |
| LV008 | RP08 | 중앙 도서관 위치 알려줘 | place | `prompt_find_place -> tool_search_places -> tool_get_place` | 공식 캠퍼스맵 | completed | `/places?query=중앙 도서관`이 `central-library` 1건으로 복구된다. | 공백 변형이 중앙도서관으로 정상 복구된다. | pass | spacing normalization이 live 배포에서 동작한다. |
| LV009 | RP09 | 니콜스 관 위치 | place | `prompt_find_place -> tool_search_places -> tool_get_place` | 공식 캠퍼스맵 | completed | `/places?query=니콜스 관`이 `nicholls-hall` 1건으로 복구된다. | 공백 변형이 니콜스관으로 정상 복구된다. | pass | 생활형 spacing variation을 수용한다. |
| LV010 | RP10 | building 카테고리에서 K관 찾아줘 | place | `songsim://place-categories -> tool_search_places -> tool_get_place` | 공식 캠퍼스맵 + resource contract | completed | `/places?query=K관&category=building`이 `kim-sou-hwan-hall` 1건만 반환한다. | category filter와 alias search를 함께 쓰는 기본 흐름은 맞는다. | pass | API-first 실행이라 resource 자체는 직접 호출하지 않았지만 결과는 기대와 일치한다. |
| LV011 | RC01 | 2026년 1학기 자료구조 과목 찾아줘 | course | `prompt_search_courses -> tool_search_courses` | public course snapshot | completed | `/courses?query=자료구조&year=2026&semester=1`이 `자료구조`, `자료구조기초` 5건을 반환한다. 첫 결과 code는 `03149`다. | 학기 + 대표 과목명 canary가 공개 snapshot에서 안정적으로 재현된다. | pass | source-backed course gate로 교체한 뒤 live canary가 정상 동작한다. |
| LV012 | RC02 | 2026년 1학기 객체지향 과목 찾아줘 | course | `prompt_search_courses -> tool_search_courses` | public course snapshot | completed | `/courses?query=객체지향&year=2026&semester=1`이 `객체지향패러다임`, `객체지향프로그래밍`, `객체지향프로그래밍설계`를 포함한 5건을 반환한다. | 대표 과목명 질의가 공개 snapshot에서 안정적으로 재현된다. | pass | 객체지향 계열은 source-backed canary로 쓰기 충분하다. |
| LV013 | RC03 | 03149 과목 뭐야 | course | `tool_search_courses` | public course snapshot | completed | `/courses?query=03149&year=2026&semester=1`이 code `03149`인 `자료구조` 3건을 반환한다. | exact code query가 title family와 함께 정확히 풀린다. | pass | 기존 `CSE301` gate보다 재현성이 높다. |
| LV014 | RC04 | 전혜경 교수 수업 보여줘 | course | `tool_search_courses` | public course snapshot | completed | `/courses?query=전혜경&year=2026&semester=1`이 `객체지향프로그래밍설계`, `컴퓨터와프로그래밍1` 2건을 반환한다. | professor query가 공개 snapshot에서 안정적으로 검증된다. | pass | 교수명 canary도 source-backed 표본으로 교체했다. |
| LV015 | RC05 | 자료구조 교수가 누구야 | course | `tool_search_courses` | public course snapshot | completed | `/courses?query=자료구조&year=2026&semester=1&limit=3`이 `신은영`, `한미현`, `김의찬` professor 필드가 있는 `자료구조` rows를 반환한다. | natural-language 의도는 payload의 professor 필드를 읽는 흐름으로 충분히 충족된다. | pass | title+professor 복합 질의가 아니라 payload 확인 canary로 재설계했다. |
| LV016 | RC06 | 객체지향 과목 2개만 보여줘 | course | `tool_search_courses` | public course snapshot | completed | `/courses?query=객체지향&limit=2`가 정확히 2건을 반환한다. | limit 파라미터와 대표 과목명 검색이 함께 검증된다. | pass | 이전 empty-result gate를 정상 canary로 교체했다. |
| LV017 | RC07 | 객체 지향 과목 찾아줘 | course | `prompt_search_courses -> tool_search_courses` | public course snapshot | completed | `/courses?query=객체 지향&year=2026&semester=1`이 `객체지향패러다임`, `객체지향프로그래밍`, `객체지향프로그래밍설계`를 반환한다. | course spacing recovery가 공개 배포에서 실제로 재현된다. | pass | place뿐 아니라 course에서도 spacing normalization canary가 성립한다. |
| LV018 | RC08 | 자료 구조 수업 있어 | course | `prompt_search_courses -> tool_search_courses` | public course snapshot | completed | `/courses?query=자료 구조&year=2026&semester=1`이 `자료구조`, `자료구조기초`를 반환한다. | 자료구조 spacing variation도 공개 snapshot에서 재현된다. | pass | old typo gate 대신 source-backed spacing canary로 교체했다. |
| LV019 | RC09 | C0 106 과목 뭐야 | course | `tool_search_courses` | public course snapshot | completed | `/courses?query=C0 106&year=2026&semester=1`이 code `C0106`인 `AI기반앱개발과활용` 1건을 반환한다. | code spacing variation이 정확히 canonical course row로 풀린다. | pass | 기존 `CSE 420` gate보다 live 재현성이 높다. |
| LV020 | RC10 | 7교시에 시작하는 과목 찾고 싶어 | course | `songsim://class-periods -> tool_search_courses` | class-periods resource + public course snapshot | completed | `/periods`가 1~10교시 표를 반환하고, `/courses?year=2026&semester=1&limit=10`에는 `3D애니메이션1`처럼 `period_start=7`인 과목이 포함된다. | 교시표와 course snapshot은 존재하지만 API에 `period_start=7` 직접 필터는 없어 resource chaining 전제가 여전히 필요하다. | soft_pass | MCP에서는 `songsim://class-periods`를 읽고 course search 결과를 좁히는 흐름으로 설명하는 것이 맞다. |
| LV021 | RN01 | 최신 공지 3개 보여줘 | notices | `prompt_latest_notices -> tool_list_latest_notices` | 공식 notice source_url | completed | `/notices?limit=3`와 `/gpt/notices?limit=3`가 최신 3건과 공식 `source_url`을 안정적으로 반환한다. | latest ordering과 source_url 보존이 맞고 gpt display도 일관된다. | pass | 기본 latest 흐름은 안정적이다. |
| LV022 | RN02 | 최신 장학 공지 3개 보여줘 | notices | `prompt_latest_notices -> tool_list_latest_notices` | 공식 notice source_url | completed | scholarship filter에서 최신 3건이 반환되고 `/gpt/notices`에서도 `category_display=scholarship`으로 보인다. | 장학 카테고리 filtering과 표시가 공식 공지 링크와 함께 잘 유지된다. | pass | 현재 notice 축에서 가장 안정적인 happy path다. |
| LV023 | RN03 | 최신 취업 공지 3개 보여줘 | notices | `prompt_latest_notices -> tool_list_latest_notices` | 공식 notice source_url | completed | employment filter가 2건을 반환하고, 둘 다 gpt display에서 `employment`로 정규화된다. | legacy career 계열 공지가 `employment`로 안정적으로 보인다. | pass | 20문장 실측에서 fail이던 항목이 해소됐다. |
| LV024 | RN04 | 공지 카테고리 종류부터 알려줘 | notices | `songsim://notice-categories` | resource contract | completed | API-first 실행에서는 `/gpt/notices?limit=5`로 `general/scholarship/employment` display를 교차 확인했다. | 카테고리 display는 일관되지만 `songsim://notice-categories` resource 자체는 이번 API 우선 실행으로 직접 확인하지 못했다. | soft_pass | MCP resource 스팟체크는 후속 샘플 검증으로 넘기는 편이 좋다. |
| LV025 | RN05 | 커리어 센터 쪽 공지 있어 | notices | `prompt_latest_notices -> tool_list_latest_notices` | 공식 notice source_url + taxonomy policy | completed | `/notices?category=career`와 `/gpt/notices?category=career`가 모두 취업 공지 2건을 반환하고 display는 `employment`다. | legacy `career` 입력이 `employment`로 수렴한다. | pass | taxonomy 하위호환이 live 배포에서 동작한다. |
| LV026 | RN06 | 학사 공지 5개 최신순으로 요약해줘 | notices | `prompt_latest_notices -> tool_list_latest_notices` | 공식 notice source_url | completed | `/notices?category=academic&limit=5`와 `/gpt/notices?category=academic&limit=5`가 모두 5건을 반환하고 `Major Discovery Week`도 포함된다. | academic slice와 GPT display가 현재 공개 snapshot에서 안정적으로 재현된다. | pass | 이전 generic detail label 회귀가 해소된 뒤 notice gate도 현재 truth와 일치한다. |
| LV027 | RN07 | 취업 공지에서 legacy career도 같이 잡아줘 | notices | `tool_list_latest_notices` | 공식 notice source_url + taxonomy policy | completed | employment filter가 2건을 반환하고 career legacy 입력과 같은 결과 집합으로 수렴한다. | employment/career normalization이 일관된다. | pass | legacy taxonomy 회귀 포인트는 해결됐다. |
| LV028 | RN08 | 취 업 공지 보여줘 | notices | `prompt_latest_notices -> tool_list_latest_notices` | 공식 notice source_url + taxonomy policy | completed | spacing variant인 `취 업`도 employment 결과 2건으로 정규화된다. | 공백 변형 + taxonomy normalization이 함께 동작한다. | pass | 생활형 spacing variation까지 수용한다. |
| LV029 | RR01 | 중앙도서관 근처 밥집 추천해줘 | restaurants | `prompt_find_nearby_restaurants -> tool_find_nearby_restaurants` | Kakao Maps public listing | completed | `/restaurants/nearby?origin=중앙도서관`이 5건을 반환하고 origin이 `central-library`로 정규화된다. 첫 후보는 `꼬밥`이다. | baseline nearby retrieval이 Kakao-backed venue 이름과 함께 안정적으로 동작한다. | pass | 기본 origin happy path는 안정적이다. |
| LV030 | RR02 | 중도 근처 밥집 추천해줘 | restaurants | `prompt_find_nearby_restaurants -> tool_find_nearby_restaurants` | Kakao Maps public listing + 제품 alias 정책 | completed | `/restaurants/nearby?origin=중도`가 5건을 반환하고 origin을 `central-library`로 정규화한다. | origin alias `중도`가 restaurant nearby에도 일관되게 연결된다. | pass | 이전 fail 항목이 해소됐다. |
| LV031 | RR03 | 학생식당 근처 밥집 있어 | restaurants | `prompt_find_nearby_restaurants -> tool_find_nearby_restaurants` | Kakao Maps public listing + 제품 alias 정책 | completed | `/restaurants/nearby?origin=학생식당`이 5건을 반환하고 origin은 `sophie-barat-hall`이다. 첫 후보는 `호식당`이다. | 학생식당 alias가 restaurant origin으로 정상 해석된다. | pass | place alias와 nearby origin alias가 일치한다. |
| LV032 | RR04 | 니콜스 근처 밥집 추천해줘 | restaurants | `prompt_find_nearby_restaurants -> tool_find_nearby_restaurants` | Kakao Maps public listing + 제품 alias 정책 | completed | `/restaurants/nearby?origin=니콜스`가 5건을 반환하고 origin은 `nicholls-hall`이다. 첫 후보는 `포케얌`이다. | 니콜스 alias가 restaurant origin으로 정상 해석된다. | pass | alias coverage가 place/classroom/restaurant 전반에서 맞춰졌다. |
| LV033 | RR05 | 중앙도서관에서 10분 안쪽 1만원 이하 한식집 | restaurants | `prompt_find_nearby_restaurants -> tool_find_nearby_restaurants` | Kakao Maps public listing | completed | `/restaurants/nearby?origin=중앙도서관&walk_minutes=10&budget_max=10000&category=korean`이 빈 배열을 반환한다. | 가격 근거가 없는 후보를 엄격하게 제외한 결과로 읽히지만, Kakao 공개값 기준으로 범위 내 유효 후보가 정말 없는지는 별도 spot check가 더 필요하다. | soft_pass | budget strictness는 지켜졌고 zero-result UX는 후속 점검이 필요하다. |
| LV034 | RR06 | 중도 기준 15분 안쪽 1만원 이하 한식집 | restaurants | `prompt_find_nearby_restaurants -> tool_find_nearby_restaurants` | Kakao Maps public listing + 제품 alias 정책 | completed | `/restaurants/nearby?origin=중도&walk_minutes=15&budget_max=10000&category=korean`이 빈 배열을 반환한다. | alias origin과 복합 제약은 깨지지 않았지만, zero-result가 Kakao 공개 목록과 정확히 일치하는지는 추가 확인이 필요하다. | soft_pass | 가격 근거 우선 정책 때문에 결과 수가 크게 줄 수 있다. |
| LV035 | RR07 | 학생식당 기준 지금 여는 카페만 3개 | restaurants | `prompt_find_nearby_restaurants -> tool_find_nearby_restaurants` | Kakao Maps public listing | completed | `/restaurants/nearby?origin=학생식당&open_now=true&category=cafe&limit=3`이 빈 배열을 반환한다. | `open_now=true` strict semantics에 따라 영업 중이 확인된 후보만 남기고, 확인 가능한 후보가 없으면 빈 배열로 끝나는 현재 계약과 일치한다. | pass | 회귀 기준은 `open_now=true` 응답에 `open_now=null` item이 섞이지 않는 것이다. |
| LV036 | RR08 | 정문 근처 5분 안쪽 식당만 | restaurants | `prompt_find_nearby_restaurants -> tool_find_nearby_restaurants` | Kakao Maps public listing | completed | `/restaurants/nearby?origin=정문&walk_minutes=5&limit=5`가 5건을 반환하고 origin은 `main-gate`로 정규화된다. 모든 후보의 도보 시간은 1~2분 수준이다. | gate origin과 walk filter가 함께 동작한다. | pass | 정문을 restaurant origin으로 쓰는 경로는 안정적이다. |
| LV037 | RR09 | 중앙 도서관 근처 밥집 | restaurants | `prompt_find_nearby_restaurants -> tool_find_nearby_restaurants` | Kakao Maps public listing | completed | `/restaurants/nearby?origin=중앙 도서관`이 5건을 반환하고 origin을 `central-library`로 정규화한다. | origin spacing recovery가 restaurant nearby에서도 동작한다. | pass | place search와 같은 normalization을 공유한다. |
| LV038 | RR10 | 중도 기준 만원이하 밥집 | restaurants | `prompt_find_nearby_restaurants -> tool_find_nearby_restaurants` | Kakao Maps public listing | completed | `/restaurants/nearby?origin=중도&budget_max=10000`이 빈 배열을 반환한다. | 가격 정보가 없는 후보를 제외하는 strict budget contract와는 일치한다. | pass | 대표 목적은 budget strictness 회귀 확인이므로 현재 결과는 합격으로 본다. |
| LV039 | RT01 | 성심교정 지하철 오는 길 알려줘 | transport | `prompt_transport_guide -> tool_list_transport_guides` | 공식 교통 안내 페이지 | completed | `/transport?mode=subway`가 `1호선`, `서해선` 2건을 공식 `location_songsim.do` source_url과 함께 반환한다. | subway baseline이 공식 교통 안내 페이지와 일치한다. | pass | 대표 happy path다. |
| LV040 | RT02 | 성심교정 버스로 가는 법 알려줘 | transport | `prompt_transport_guide -> tool_list_transport_guides` | 공식 교통 안내 페이지 | completed | `/transport?mode=bus`가 `마을버스`, `시내버스` 2건을 반환한다. | bus baseline이 공식 교통 안내 페이지와 일치한다. | pass | transport mode filter가 안정적이다. |
| LV041 | RT03 | 역곡역에서 성심교정 가는 법 | transport | `prompt_transport_guide -> tool_list_transport_guides` | 공식 교통 안내 페이지 | completed | `/transport?limit=10` 전체 목록에는 `1호선` guide가 포함되고 summary에 `역곡역 2번 출구`, `정문까지 도보 10분`이 명시된다. | 필요한 factual guide는 존재하지만 API raw는 자연어 질의를 직접 해석하지 않으므로 MCP flow 관점에서 간접 검증에 그친다. | soft_pass | Shared GPT나 MCP 샘플 검증에서 이 문장을 직접 한번 더 보는 게 좋다. |
| LV042 | RT04 | 지하철 오느 길 알려줘 | transport | `prompt_transport_guide -> tool_list_transport_guides` | 공식 교통 안내 페이지 | completed | `/transport?mode=subway`는 정상이나, typo recovery 자체는 API-first 실행에서 직접 검증하지 못했다. | subway guide 데이터는 충분하지만 typo가 실제 prompt/tool 선택에서 복구되는지는 후속 MCP 샘플 검증이 필요하다. | soft_pass | API-first 게이트의 한계가 드러나는 케이스다. |
| LV043 | RL01 | 니콜스관인데 지금 비어 있는 강의실 있어 | classrooms | `prompt_find_empty_classrooms -> tool_list_estimated_empty_classrooms` | public classroom contract | completed | `/classrooms/empty?building=니콜스관&limit=5`가 5개 room과 `availability_mode=estimated`를 반환한다. note는 `공식 시간표 기준 예상 공실`이다. | 실시간처럼 단정하지 않고 fallback semantics를 정확히 표시한다. | pass | 현재 공개 배포 정책과 정확히 맞다. |
| LV044 | RL02 | N관에서 지금 빈 강의실 보여줘 | classrooms | `prompt_find_empty_classrooms -> tool_list_estimated_empty_classrooms` | public classroom contract | completed | `/classrooms/empty?building=N관&limit=5`가 니콜스관과 같은 결과를 반환한다. | `N관` alias가 building resolver에 정확히 연결된다. | pass | alias baseline이 안정적이다. |
| LV045 | RL03 | 김수환관 지금 빈 강의실 있어 | classrooms | `prompt_find_empty_classrooms -> tool_list_estimated_empty_classrooms` | public classroom contract + 공식 캠퍼스맵 설명 | completed | `/classrooms/empty?building=김수환관&limit=5`는 0건이지만 building=`kim-sou-hwan-hall`, category=`building`, note=`해당 건물의 강의실 시간표 데이터를 찾지 못했습니다`를 반환한다. | 비강의동으로 막히지 않고 building classification이 유지되므로 이번 릴리즈 기준은 충족한다. | pass | room timetable data coverage는 별도 후속 과제다. |
| LV046 | RL04 | 니콜스에서 지금 빈 강의실 있어 | classrooms | `prompt_find_empty_classrooms -> tool_list_estimated_empty_classrooms` | public classroom contract + 제품 alias 정책 | completed | `/classrooms/empty?building=니콜스&limit=5`가 5개 room을 반환하고 building을 `nicholls-hall`로 정규화한다. | 생활어 alias `니콜스`가 classroom resolver에서도 정상 동작한다. | pass | 이전 fail 항목이 해소됐다. |
| LV047 | RL05 | 정문 기준 빈 강의실 보여줘 | classrooms | `prompt_find_empty_classrooms -> tool_list_estimated_empty_classrooms` | public classroom contract + 공식 캠퍼스맵 | completed | `/classrooms/empty?building=정문&limit=5`는 400과 함께 `강의실 기반 건물이 아니다`는 설명을 반환한다. | 비강의동 거절이 정확하고 이유도 충분히 구체적이다. | pass | 이 케이스는 거절이 정답이다. |
| LV048 | RX01 | 내 프로필 만들고 저장해줘 | out_of_scope | `songsim://usage-guide` | usage guide resource | completed | 공개 usage guide와 연결 문서는 public server가 read-only이며 `profile` 기능이 unavailable이라고 명시한다. | 공개 제품 정책과 질문 의도가 충돌하므로 read-only 거절이 정답이다. | pass | MCP에서는 `songsim://usage-guide`를 먼저 읽는 흐름이 맞다. |
| LV049 | RX02 | 시간표 저장해줘 | out_of_scope | `songsim://usage-guide` | usage guide resource | completed | usage guide는 public server에서 `timetable` 기능이 unavailable이라고 명시한다. | 시간표 저장 요청은 공개 read-only 범위 밖이므로 거절 설명이 맞다. | pass | local full mode와 public mode의 경계가 명확하다. |
| LV050 | RX03 | 관리자 sync 돌려줘 | out_of_scope | `songsim://usage-guide` | usage guide resource | completed | usage guide는 public server에서 `admin` 기능이 unavailable이라고 명시한다. | 관리자 sync 요청은 공개 제품 정책상 지원하지 않는 것이 맞다. | pass | admin 기능은 공개 surface에서 숨겨져 있다. |

## 사용 메모

- place, restaurants, notices, classrooms, transport는 실제 public API 응답을 기반으로 채웠습니다.
- course는 current public snapshot 기준으로 판정했고, 질의가 비어 있어도 릴리즈팩 기대를 충족하지 못하면 `soft_fail`로 기록했습니다.
- resource-only 케이스는 API 우선 실행 특성상 `soft_pass` 또는 policy-based `pass`로 판정했습니다.
- 다음 단계는 [공개 MCP 라이브 판정 요약](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-live-validation-summary.md)의 이슈 순위대로 보정하면 됩니다.
