# Public MCP Hidden Risk Summary

`public API`를 2026-03-16 KST 기준으로 다시 돌린 숨은 운영 리스크 감사 요약입니다. 최근 `classrooms timeout`, `transport mode inference`, `generic facility search`, `brand direct search`, `course gate recalibration`이 순차 반영되면서, 예전 hidden-risk 문서에 있던 주요 fail 축 다수가 현재 운영 truth와 맞지 않게 됐습니다. 이번 summary는 **현재 남아 있는 리스크만** 다시 추린 버전입니다.

## 집계

- audit size: 30
- `pass`: 19
- `soft_pass`: 10
- `soft_fail`: 1
- `fail`: 0
- latency
  - `fast`: 19
  - `slow`: 10
  - `timeout`: 1

## 이번 감사에서 확인된 점

### 1. 예전 핵심 리스크 대부분은 해소됐다

- `classrooms` happy-path timeout은 현재 baseline에서 재현되지 않았습니다.
  - `니콜스`, `김수환관`, `학생미래인재관`이 모두 `10s` 안에 정상 응답했습니다.
- `transport` query-to-mode mismatch도 크게 줄었습니다.
  - `지하철 오느 길`, `역곡역에서 성심교정 가는 법`은 subway guide가 1위입니다.
- generic facility noun도 더 이상 대부분 `[]`가 아닙니다.
  - `헬스장`, `편의점`, `복사실`, `ATM`이 parent building 후보를 반환합니다.
- `스타벅스` direct search의 `주차장` 노이즈는 사라졌습니다.

### 2. 지금 남은 리스크는 “정답 우선화”와 “API-first 간접 경로” 쪽이다

- `정문`, `K관`은 정답이 1위로 오지만 여전히 2차 노이즈가 남습니다.
  - `정문` -> `main-gate` 뒤에 `창업보육센터`
  - `K관` -> `김수환관` 뒤에 `스테파노기숙사`
- `K관`을 origin으로 쓴 nearby 검색은 정확도는 맞지만 `12.7s`로 느립니다.
- `공지 카테고리 종류`, `7교시 시작 과목`은 API-first로는 **간접 확인**은 되지만, 한 번에 설명해 주는 단일 endpoint는 없습니다.

### 3. brand direct search는 안정권에 들어갔다

- `스타벅스`, `투썸`, `빽다방`은 현재 운영에서 정상입니다.
- `origin=중도`가 있으면 거리/도보 시간이 채워집니다.
- `커피빈`은 여전히 `[]`지만, 이번 정책상 이건 immediate bug라기보다
  - campus-near 실제 후보가 없는 것인지
  - curated alias 범위 밖인지
  를 구분하는 watch 상태로 두는 편이 맞습니다.

### 4. course는 여전히 “gate”가 아니라 “watchlist”다

- `데이터베이스`는 현재 `데이터베이스활용` 1건만 잡힙니다.
- `CSE301`, `김가톨`, `데이타베이스`, `CSE 420`는 여전히 빈 결과입니다.
- 하지만 이 축은 이번 release-pack에서 이미 분리되어 있으므로, 현재는 **제품 fail**이 아니라 **source-gap watchlist**로 기록하는 것이 맞습니다.

## 현재 남은 리스크

1. short-query residual noise
- `정문`, `K관` 모두 정답은 맞지만 후보 정리가 완전히 끝나진 않았습니다.
- 실제 체감상 가장 자주 보이는 “거슬리는 품질 저하”는 이 축입니다.

2. `origin=K관` nearby latency
- resolver는 맞게 고쳐졌지만, 대표 nearby query가 여전히 `10s`를 넘습니다.
- correctness issue보다는 latency hot spot에 가깝습니다.

3. API-first resource/prompt gap
- `공지 카테고리 종류`, `7교시 시작 과목`은 단일 endpoint로 바로 답하기보다 chaining/간접 해석이 필요합니다.
- product contract 위반은 아니지만, 문서/리소스 보강 여지는 남아 있습니다.

4. course source-gap watchlist
- release gate에서 빠졌기 때문에 지금 당장 구현 우선순위는 아니지만, source truth 변화가 생기면 다시 확인해야 합니다.

## 지금은 주요 리스크가 아닌 것

- `classrooms timeout`
- `transport mode mismatch`
- `generic facility noun -> []`
- `스타벅스 주차장 노이즈`
- `open_now=true`에 `null` item 섞임

이 다섯 가지는 이번 baseline에서는 더 이상 핵심 리스크로 분류하지 않습니다.

## 다음 구현 1순위

`short-query disambiguation polish`

이유:
- release-pack은 이미 안정적이고 hard fail이 없습니다.
- 남은 visible quality issue 중 가장 자주 보이고, place/classroom/origin 세 surface에 동시에 영향을 주는 축이 `정문`, `K관` residual noise입니다.
- `K관` nearby latency도 short-query resolver 경로에서 드러난 문제라, 같은 맥락에서 다루기 좋습니다.

## 관련 문서

- [Hidden Risk Audit](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-hidden-risk-audit.md)
- [Public MCP Release Pack 50](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-release-pack-50.md)
- [Public MCP Live Validation Summary](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-live-validation-summary.md)
