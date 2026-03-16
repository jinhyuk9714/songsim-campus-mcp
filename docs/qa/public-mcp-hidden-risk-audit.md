# Public MCP Hidden Risk Audit

`public API`를 2026-03-16 KST 기준으로 다시 실측해, 최근 성능/검색/transport/brand 보정과 metadata parity 반영 이후의 **현재 운영 baseline**을 재작성한 감사 시트입니다. 이번 감사는 새 기능 추가 없이 문서만 갱신했고, 이미 해결된 리스크는 내리고 아직 남은 리스크만 `short-query`, `metadata parity`, `brand long-tail`, `course watchlist`, `latency/strict semantics` 기준으로 다시 분류했습니다.

## 실행 기준

- 대상: `https://songsim-public-api.onrender.com`
- 방식: public API raw endpoint 실측
- 보조 확인: read-only 정책 2건, generic facility spot check 4건
- latency 등급
  - `fast`: `<2s`
  - `slow`: `2-10s`
  - `timeout`: `>10s`
- verdict
  - `pass`
  - `soft_pass`
  - `soft_fail`
  - `fail`

## 집계

| Metric | Count |
| --- | ---: |
| cases | 30 |
| `pass` | 24 |
| `soft_pass` | 6 |
| `soft_fail` | 0 |
| `fail` | 0 |
| `fast` | 19 |
| `slow` | 11 |
| `timeout` | 0 |

## 감사 시트

| ID | User utterance | Surface | Expected behavior | Observed response summary | Latency | Verdict | Risk type | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SQ01 | 정문 위치 알려줘 | `GET /places?query=정문&limit=5` | `main-gate`가 canonical result 하나로 반환돼야 한다 | `main-gate` 1건만 반환 | fast | pass | `canonicalized` | exact short-query canonicalization이 live에 반영됐다 |
| SQ02 | K관 어디야 | `GET /places?query=K관&limit=5` | `kim-sou-hwan-hall`이 canonical result 하나로 반환돼야 한다 | `kim-sou-hwan-hall` 1건만 반환 | fast | pass | `canonicalized` | `K관` exact short-query가 dormitory 후보 없이 단일 수렴한다 |
| SQ03 | 도서관 어디야 | `GET /places?query=도서관&limit=5` | `central-library`가 안정적으로 1위여야 한다 | `central-library` 1건만 반환 | fast | pass | `exact_match` | short noun library query는 안정적이다 |
| SQ04 | 학생회관 어디야 | `GET /places?query=학생회관&limit=5` | `sophie-barat-hall`로 수렴해야 한다 | `sophie-barat-hall` 1건만 반환 | fast | pass | `alias_match` | 생활어 alias가 정상 동작한다 |
| SQ05 | 학생센터 어디야 | `GET /places?query=학생센터&limit=5` | `sophie-barat-hall`로 수렴해야 한다 | `sophie-barat-hall` 1건만 반환 | fast | pass | `alias_match` | `학생센터` alias도 안정적이다 |
| SQ06 | K관 근처 카페 보여줘 | `GET /restaurants/nearby?origin=K관&category=cafe&limit=5` | `kim-sou-hwan-hall` 기준 nearby가 정상 동작하고 stale/fresh cache로 `10s` 안에 끝나야 한다 | `origin=kim-sou-hwan-hall`로 정상 수렴했고 `매머드익스프레스 부천가톨릭대학교점`이 1위, 전체 응답은 `5.9s` | slow | pass | `cached_origin_ok` | stale-first 정책 이후 반복 요청 경로는 timeout 없이 응답한다 |
| SQ07 | K관 지금 빈 강의실 있어 | `GET /classrooms/empty?building=K관&limit=5` | ambiguity 없이 `김수환관` 기준 공실 결과가 나와야 한다 | `200`, `K107`, `K236` 등 5건 반환 | slow | pass | `resolver_fixed` | 과거 ambiguity 400은 해소됐다 |
| SQ08 | 정문 건물로 찾아줘 | `GET /places?query=정문&category=building&limit=5` | gate를 building으로 오인하지 않고 빈 결과를 반환해야 한다 | `[]` | fast | pass | `context_filtering` | building filter가 false positive를 막는다 |
| RG01 | 지하철 오느 길 알려줘 | `GET /transport?query=지하철 오느 길&limit=3` | subway guide가 1위여야 한다 | `1호선`, `서해선`이 모두 `mode=subway`로 반환 | fast | pass | `transport_inference` | typo 포함 natural-language query가 정상 해석된다 |
| RG02 | 역곡역에서 성심교정 가는 법 | `GET /transport?query=역곡역에서 성심교정 가는 법&limit=3` | 역곡역/지하철 intent가 subway guide 1위로 연결돼야 한다 | `1호선`, `서해선` 순으로 반환되고 둘 다 `mode=subway` | fast | pass | `transport_inference` | 과거 mode mismatch는 해소됐다 |
| RG03 | 공지 카테고리 종류부터 알려줘 | `GET /notice-categories` | API-first 경로에서 canonical category list를 직접 읽을 수 있어야 한다 | `academic`, `scholarship`, `employment`, `general`이 직접 반환되고 compatibility alias로 `career`, `place`가 함께 노출된다 | fast | pass | `metadata_parity` | `/gpt/notice-categories`도 같은 truth를 concise shape로 반환한다 |
| RG04 | 7교시에 시작하는 과목 찾고 싶어 | `GET /gpt/periods` + `GET /courses?year=2026&semester=1&limit=10` | period metadata를 직접 읽고 course search와 체인해서 7교시 시작 과목을 찾을 수 있어야 한다 | `/gpt/periods`가 1~10교시를 직접 반환하고 `/courses` sample에는 `3D애니메이션1`의 `period_start=7`이 보인다 | fast | pass | `metadata_parity` | `/periods`도 같은 truth를 반환해 HTTP/MCP/GPT parity가 맞는다 |
| RG05 | 내 프로필 만들고 저장해줘 | public read-only policy | write/profile persistence 요청은 read-only 범위 밖으로 거절돼야 한다 | usage guide와 공개 문서 기준으로 profile persistence는 미지원 | fast | pass | `policy_guardrail` | 현재 제품 계약과 일치하는 거절 범위다 |
| RG06 | 관리자 sync 돌려줘 | public read-only policy | admin/sync 실행 요청은 public surface에서 지원하지 않아야 한다 | usage guide와 공개 문서 기준으로 admin sync는 범위 밖 | fast | pass | `policy_guardrail` | public API/MCP의 read-only contract와 일치한다 |
| BR01 | 스타벅스 있어? | `GET /restaurants/search?query=스타벅스&limit=5` | brand result가 나오고 parking noise는 제거돼야 한다 | `스타벅스 역곡역DT점` 1건만 반환 | slow | pass | `brand_clean` | 과거 `주차장` 노이즈는 사라졌다 |
| BR02 | 중도 기준 스타벅스 어디 있어? | `GET /restaurants/search?query=스타벅스&origin=중도&limit=5` | origin 기준 거리/도보 시간이 채워져야 한다 | `스타벅스 역곡역DT점` 1위, `914m / 12분` | slow | pass | `brand_with_origin` | explicit origin direct search가 계약대로 동작한다 |
| BR03 | 커피빈 있어? | `GET /restaurants/search?query=커피빈&limit=5` | 주변 실재 후보가 없으면 empty가 가능하지만 parser failure와는 구분돼야 한다 | `[]` | fast | soft_pass | `brand_gap_or_no_candidate` | 현재는 empty가 정상 범주지만, campus-near 실재 후보 부재인지 watchlist로만 남긴다 |
| BR04 | 투썸 있어? | `GET /restaurants/search?query=투썸&limit=5` | long-tail alias가 정상 해석돼야 한다 | `투썸플레이스 부천MJ컨벤션점` 1위 | slow | pass | `brand_alias` | alias 확장이 live에서도 동작한다 |
| BR05 | 빽다방 있어? | `GET /restaurants/search?query=빽다방&limit=5` | 주변 지점이 있으면 direct search 결과가 나와야 한다 | `빽다방 소사역점`, `빽다방 부천소사본점` 등 3건 반환 | slow | pass | `brand_alias` | long-tail brand 검색이 동작한다 |
| BR06 | 중도 기준 빽다방 어디 있어? | `GET /restaurants/search?query=빽다방&origin=중도&limit=5` | origin 기준 거리/도보 시간이 채워져야 한다 | `빽다방 소사역점` 1위, `552m / 17분`; 2위 `977m / 20분` | slow | pass | `brand_with_origin` | campus-first + origin-aware ranking이 유지된다 |
| CW01 | 데이터베이스 과목 있어 | `GET /courses?query=데이터베이스&year=2026&semester=1&limit=5` | direct hit가 없으면 source-backed near match 여부를 기록해야 한다 | `데이터베이스활용` 1건만 반환 | fast | soft_pass | `source_gap_watchlist` | release gate가 아닌 watchlist로 계속 추적한다 |
| CW02 | CSE301 과목 뭐야 | `GET /courses?query=CSE301&year=2026&semester=1&limit=5` | empty면 source-backed 부재 여부를 watchlist로 남겨야 한다 | `[]` | fast | soft_pass | `source_gap_watchlist` | 현재는 source-backed 아님 쪽으로 본다 |
| CW03 | 김가톨 교수 수업 있어 | `GET /courses?query=김가톨&year=2026&semester=1&limit=5` | empty면 source-backed 부재 여부를 watchlist로 남겨야 한다 | `[]` | fast | soft_pass | `source_gap_watchlist` | release gate 바깥의 교수명 watchlist다 |
| CW04 | 데이타베이스 과목 있어 | `GET /courses?query=데이타베이스&year=2026&semester=1&limit=5` | typo recovery 미지원이면 watchlist로만 기록해야 한다 | `[]` | fast | soft_pass | `source_gap_watchlist` | 현재는 deterministic canary가 아니다 |
| CW05 | CSE 420 과목 뭐야 | `GET /courses?query=CSE%20420&year=2026&semester=1&limit=5` | spacing code query가 empty면 watchlist로만 남겨야 한다 | `[]` | fast | soft_pass | `source_gap_watchlist` | 검색 버그로 단정하지 않고 source-gap watchlist 유지 |
| LS01 | 니콜스에서 지금 빈 강의실 있어 | `GET /classrooms/empty?building=니콜스&limit=5` | valid building happy-path가 10초 안에 응답해야 한다 | `200`, 5건 반환 | slow | pass | `latency_ok` | 과거 timeout은 해소됐다 |
| LS02 | 김수환관 지금 빈 강의실 있어 | `GET /classrooms/empty?building=김수환관&limit=5` | valid building happy-path가 10초 안에 응답해야 한다 | `200`, 5건 반환 | slow | pass | `latency_ok` | resolver와 응답 시간이 모두 정상 범위다 |
| LS03 | 학생미래인재관 빈 강의실 있어 | `GET /classrooms/empty?building=학생미래인재관&limit=5` | room data가 있으면 결과를, 없으면 empty+note를 10초 안에 반환해야 한다 | `200`, 4건 반환 | slow | pass | `latency_ok` | 과거 timeout/empty note baseline은 더 이상 유효하지 않다 |
| LS04 | 정문 기준 빈 강의실 보여줘 | `GET /classrooms/empty?building=정문&limit=5` | 비강의동은 빠른 `400`이 정답이다 | `400`과 함께 non-building rejection 반환 | fast | pass | `valid_rejection` | invalid building contract가 안정적이다 |
| LS05 | 학생식당 기준 지금 여는 카페만 3개 | `GET /restaurants/nearby?origin=학생식당&open_now=true&category=cafe&limit=3` | strict filter 결과가 empty여도 되지만 `open_now=null` item이 섞이면 안 된다 | `[]`, `5.87s` | slow | pass | `strict_semantics` | strict `open_now=true` 계약은 현재 운영에서 지켜진다 |

## 보조 generic facility spot check

이 4건은 main 30에 포함하지 않았지만, 기존 hidden-risk 문서에서 크게 보였던 `generic facility gap`이 얼마나 해소됐는지 읽는 데 도움이 됩니다.

| ID | User utterance | Surface | Observed response summary | Takeaway |
| --- | --- | --- | --- | --- |
| GF01 | 헬스장 어디야 | `GET /places?query=헬스장&limit=5` | `dormitory-stephen` 1위, `sophie-barat-hall` 2위 | 더 이상 `[]`는 아니고 관련 건물 후보를 반환한다. 다만 랭킹은 더 다듬을 여지가 있다 |
| GF02 | 편의점 어디 있어 | `GET /places?query=편의점&limit=5` | `dormitory-stephen` 1건 반환 | generic facility noun gap은 크게 줄었다 |
| GF03 | 복사실 어디야 | `GET /places?query=복사실&limit=5` | `dormitory-stephen` 1건 반환 | parent building 후보형 응답으로는 정상 범위다 |
| GF04 | ATM 어디 있어 | `GET /places?query=ATM&limit=5` | `dormitory-stephen` 1건 반환 | uppercase generic noun도 이제 빈 결과가 아니다 |

## 보조 메모

- `classrooms timeout`, `transport mode mismatch`, `generic facility noun -> []`, `스타벅스 주차장 노이즈`, `정문/K관` residual noise는 더 이상 현재 운영 baseline의 핵심 리스크가 아니다.
- 현재 남아 있는 눈에 띄는 리스크는 `공지/교시 API-first chaining`, `커피빈 empty semantics`, `course source-gap watchlist` 쪽이다.
- `course`는 release gate가 아니라 watchlist라는 현재 정책을 유지한다. `데이터베이스`, `CSE301`, `김가톨`, `데이타베이스`, `CSE 420`는 계속 source-backed 여부 중심으로만 추적한다.
