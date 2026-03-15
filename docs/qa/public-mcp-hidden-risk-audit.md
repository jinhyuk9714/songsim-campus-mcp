# Public MCP Hidden Risk Audit

`public API`를 2026-03-15 KST 기준으로 실측해, 릴리즈팩 50과 기존 라이브 검증에서 충분히 드러나지 않았던 운영 리스크를 따로 모은 감사 시트입니다. 이번 감사는 **오답 우선순위, timeout, short-query ambiguity, generic 생활어 coverage**를 우선순위로 삼았고, 코드는 수정하지 않았습니다.

## 실행 기준

- 대상: `https://songsim-public-api.onrender.com`
- 방식: public API raw endpoint 실측
- 보조 확인: `gpt/restaurants/search` 1건, course/open_now representative spot check 4건
- latency 등급
  - `fast`: `<2s`
  - `slow`: `2-10s`
  - `timeout`: `>10s` 또는 client timeout
- verdict
  - `pass`
  - `soft_pass`
  - `soft_fail`
  - `fail`

## 집계

| Metric | Count |
| --- | ---: |
| cases | 30 |
| `pass` | 11 |
| `soft_pass` | 4 |
| `soft_fail` | 4 |
| `fail` | 11 |
| `fast` | 21 |
| `slow` | 5 |
| `timeout` | 4 |

## 감사 시트

| ID | User utterance | Surface | Expected behavior | Observed response summary | Latency | Verdict | Risk type | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TR01 | 지하철로 가는 법 | `GET /transport?query=지하철` | subway 관련 guide가 첫 결과로 와야 한다 | 첫 3건이 `마을버스`, `시내버스`, `성심교정` 순으로 내려온다 | fast | fail | `mode_mismatch` | strong subway cue가 있어도 bus가 먼저 나온다 |
| TR02 | 1호선 타고 가는 법 | `GET /transport?query=1호선` | 1호선/지하철 guide가 첫 결과로 와야 한다 | 첫 3건이 `마을버스`, `시내버스`, `성심교정` 순이다 | fast | fail | `mode_mismatch` | `1호선` 질의가 mode selection에 반영되지 않는다 |
| TR03 | 역곡역에서 가는 법 | `GET /transport?query=역곡역` | 역곡역/지하철 접근이 우선 노출돼야 한다 | 첫 3건이 `마을버스`, `시내버스`, `성심교정`이다 | fast | soft_fail | `query_to_mode_gap` | 버스 안내가 완전히 틀린 것은 아니지만 역곡역 intent를 우선 반영하지 못한다 |
| TR04 | 셔틀 있나 | `GET /transport?query=셔틀` | 셔틀 미지원이면 그 사실을 드러내거나 관련 guide를 좁혀야 한다 | 첫 3건이 `마을버스`, `시내버스`, `성심교정`이다 | fast | fail | `unsupported_scope_handling` | unsupported query를 일반 bus 결과로 흘려보낸다 |
| TR05 | 버스만 타고 가는 법 | `GET /transport?query=버스만` | bus guide가 첫 결과여야 한다 | 첫 2건이 `마을버스`, `시내버스`다 | fast | pass | `mode_match` | query 해석이 약해도 결과 순서는 의도와 맞는다 |
| TR06 | 지하철만 타고 가는 법 | `GET /transport?query=지하철만` | subway guide가 첫 결과여야 한다 | 첫 3건이 `마을버스`, `시내버스`, `성심교정`이다 | fast | fail | `mode_mismatch` | `지하철만` 같은 강한 제약을 무시한다 |
| TR07 | subway로만 가는 경로 줘 | `GET /transport?query=subway` | subway guide가 첫 결과여야 한다 | 첫 3건이 `마을버스`, `시내버스`, `성심교정`이다 | fast | fail | `mode_mismatch` | 영문 cue도 mode로 연결되지 않는다 |
| TR08 | bus로만 가는 경로 줘 | `GET /transport?query=bus` | bus guide가 첫 결과여야 한다 | 첫 2건이 `마을버스`, `시내버스`다 | fast | pass | `mode_match` | 영문 bus cue는 결과상 문제 없다 |
| CL01 | 학생미래인재관 빈 강의실 있어 | `GET /classrooms/empty?building=학생미래인재관` | empty+note 또는 정상 결과가 10초 내 나와야 한다 | 12.1초 후 client timeout | timeout | fail | `timeout` | valid building happy path가 timeout난다 |
| CL02 | 김수환관 지금 빈 강의실 있어 | `GET /classrooms/empty?building=김수환관` | empty+note 또는 정상 결과가 10초 내 나와야 한다 | 12.1초 후 client timeout | timeout | fail | `timeout` | building classification은 맞지만 live 응답이 끝나지 않는다 |
| CL03 | 니콜스에서 지금 빈 강의실 있어 | `GET /classrooms/empty?building=니콜스` | nicholls-hall 공실 결과가 10초 내 나와야 한다 | 12.1초 후 client timeout | timeout | fail | `timeout` | 가장 대표적인 happy path가 timeout난다 |
| CL04 | 정문 기준 빈 강의실 보여줘 | `GET /classrooms/empty?building=정문` | 비강의동 거절이 빠르고 구체적이어야 한다 | `400`과 함께 `강의실 기반 건물이 아니다` 설명이 반환된다 | fast | pass | `valid_rejection` | invalid building rejection은 잘 동작한다 |
| CL05 | N관에서 자습 가능한 빈 강의실 있어 | `GET /classrooms/empty?building=N관` | 니콜스관과 같은 결과가 10초 내 나와야 한다 | 12.1초 후 client timeout | timeout | fail | `timeout` | alias happy path도 timeout으로 무너진다 |
| CL06 | K관 지금 빈 강의실 있어 | `GET /classrooms/empty?building=K관` | 김수환관으로 clean하게 수렴해야 한다 | `400`과 함께 `김수환관`, `스테파노기숙사` 두 후보가 반환된다 | fast | fail | `alias_collision` | `K관` collision이 classroom resolver에 그대로 남아 있다 |
| PL01 | 정문 | `GET /places?query=정문` | `main-gate`가 1위고 noise가 작아야 한다 | `정문` 1위, `창업보육센터` 2위 | fast | soft_pass | `ranking_noise` | 정답은 맞지만 gate query noise가 남아 있다 |
| PL02 | K관 | `GET /places?query=K관` | 김수환관이 1위이고 dormitory noise가 작아야 한다 | `김수환관` 1위, `스테파노기숙사` 2위 | fast | soft_pass | `alias_collision` | place search에서도 `K관` alias가 양쪽에 걸린다 |
| PL03 | 도서관 | `GET /places?query=도서관` | 중앙도서관이 1위여야 한다 | `central-library` 1건만 반환된다 | fast | pass | `exact_match` | short library noun은 안정적이다 |
| PL04 | 학생회관 | `GET /places?query=학생회관` | 학생미래인재관이 1위여야 한다 | `sophie-barat-hall` 1건만 반환된다 | fast | pass | `alias_match` | 생활어 alias가 안정적이다 |
| PL05 | 학생센터 | `GET /places?query=학생센터` | 학생미래인재관이 1위여야 한다 | `sophie-barat-hall` 1건만 반환된다 | fast | pass | `alias_match` | 확장한 facility alias가 잘 먹는다 |
| PL06 | B관 | `GET /places?query=B관` | 학생미래인재관이 1위여야 한다 | `sophie-barat-hall` 1건만 반환된다 | fast | pass | `alias_match` | building short alias는 안정적이다 |
| FA01 | 헬스장 어디야 | `GET /places?query=헬스장` | parent building으로라도 수렴해야 한다 | 빈 배열 `[]` | fast | fail | `facility_gap` | `트러스트짐`은 되지만 generic noun `헬스장`은 못 받는다 |
| FA02 | 편의점 어디 있어 | `GET /places?query=편의점` | parent building 또는 facility 결과가 있어야 한다 | 빈 배열 `[]` | slow | soft_fail | `facility_gap` | 실제 교내 시설 여부와 별개로 생활어 coverage가 비어 있다 |
| FA03 | 체육관 어디야 | `GET /places?query=체육관` | parent building 또는 facility 결과가 있어야 한다 | 빈 배열 `[]` | slow | soft_fail | `facility_gap` | generic facility noun 처리 정책이 없다 |
| FA04 | 카페 보나 어디야 | `GET /places?query=카페 보나` | 학생미래인재관으로 수렴해야 한다 | `sophie-barat-hall` 1건이 반환된다 | fast | pass | `facility_alias` | curated facility alias는 정상이다 |
| FA05 | 부온 프란조 어디야 | `GET /places?query=부온 프란조` | 학생미래인재관으로 수렴해야 한다 | `sophie-barat-hall` 1건이 반환된다 | fast | pass | `facility_alias` | curated facility alias는 정상이다 |
| FA06 | ATM 어디 있어 | `GET /places?query=ATM` | parent building 또는 facility 결과가 있어야 한다 | 빈 배열 `[]` | fast | soft_fail | `facility_gap` | uppercase generic facility noun을 전혀 받지 못한다 |
| BR01 | 커피빈 있어? | `GET /restaurants/search?query=커피빈` | 지원되면 campus-near branch가 먼저, 아니면 coverage 한계가 드러나야 한다 | 빈 배열 `[]` | fast | soft_pass | `brand_gap` | 빈 결과 자체는 가능하지만 curated brand coverage가 제한적이다 |
| BR02 | 스타벅스 있어? | `GET /restaurants/search?query=스타벅스` | campus-near branch 또는 가장 가까운 지점이 먼저 와야 한다 | `스타벅스 역곡역DT점` 1위, `스타벅스 역곡역DT점 주차장` 2위 | slow | soft_pass | `brand_ranking_noise` | 1위는 무난하지만 parking-like noisy entity가 함께 걸린다 |
| BR03 | 매머드커피 어디 있어? | `GET /restaurants/search?query=매머드커피` | campus-near 매머드 지점이 1위여야 한다 | `매머드익스프레스 부천가톨릭대학교점` 1위, `소사역점` 2위 | slow | pass | `brand_ranking` | no-origin campus-first ordering이 잘 동작한다 |
| BR04 | 중도 기준 메가커피 어디 있어? | `GET /restaurants/search?query=메가커피&origin=중도` | campus-near mega 지점이 1위이고 거리/도보 시간이 보여야 한다 | `메가MGC커피 부천가톨릭대점` 1위, `458m / 6분`이 채워진다 | slow | pass | `brand_with_origin` | explicit origin direct search는 계약대로 동작한다 |

## 보조 spot check

이 감사의 30건 범위에는 넣지 않았지만, 현재 운영 리스크를 읽는 데 도움이 되는 보조 확인입니다.

| ID | User utterance | Surface | Observed response summary | Takeaway |
| --- | --- | --- | --- | --- |
| SP01 | 데이터베이스 과목 있어 | `GET /courses?query=데이터베이스&year=2026&semester=1` | `데이터베이스활용` 1건만 반환 | search bug보다 `source/snapshot coverage gap` 가능성이 더 크다 |
| SP02 | 데이타베이스 과목 있어 | `GET /courses?query=데이타베이스&year=2026&semester=1` | 빈 배열 `[]` | typo recovery는 아직 증명되지 않았다 |
| SP03 | CSE 420 과목 뭐야 | `GET /courses?query=CSE 420&year=2026&semester=1` | 빈 배열 `[]` | code spacing 질의는 아직 약하다 |
| SP04 | 학생식당 기준 지금 여는 카페만 3개 | `GET /restaurants/nearby?origin=학생식당&open_now=true&category=cafe&limit=3` | 12.1초 후 client timeout | `open_now` strict semantics는 구현돼도 representative live query는 성능 리스크가 남아 있다 |
| SP05 | 매머드커피 어디 있어? (GPT compact) | `GET /gpt/restaurants/search?query=매머드커피&limit=5` | `부천가톨릭대학교점` 1위, `소사역점` 2위 | compact GPT route도 campus-first ordering을 그대로 따른다 |
