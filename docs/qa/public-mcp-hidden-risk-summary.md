# Public MCP Hidden Risk Summary

`public API`를 2026-03-16 KST 기준으로 다시 돌린 숨은 운영 리스크 감사 요약입니다. 최근 `classrooms timeout`, `transport mode inference`, `generic facility search`, `brand direct search`, `course gate recalibration`이 순차 반영되면서, 예전 hidden-risk 문서에 있던 주요 fail 축 다수가 현재 운영 truth와 맞지 않게 됐습니다. 이번 summary는 **현재 남아 있는 리스크만** 다시 추린 버전입니다.

## 집계

- audit size: 30
- `pass`: 22
- `soft_pass`: 8
- `soft_fail`: 0
- `fail`: 0
- latency
  - `fast`: 19
  - `slow`: 11
  - `timeout`: 0

## 이번 감사에서 확인된 점

### 1. 예전 핵심 리스크 대부분은 해소됐다

- `classrooms` happy-path timeout은 현재 baseline에서 재현되지 않았습니다.
  - `니콜스`, `김수환관`, `학생미래인재관`이 모두 `10s` 안에 정상 응답했습니다.
- `transport` query-to-mode mismatch도 크게 줄었습니다.
  - `지하철 오느 길`, `역곡역에서 성심교정 가는 법`은 subway guide가 1위입니다.
- generic facility noun도 더 이상 대부분 `[]`가 아닙니다.
  - `헬스장`, `편의점`, `복사실`, `ATM`이 parent building 후보를 반환합니다.
- `스타벅스` direct search의 `주차장` 노이즈는 사라졌습니다.

### 2. 지금 남은 리스크는 “API-first 간접 경로”와 “watchlist 관리” 쪽이다

- `정문`, `K관` exact short-query는 이제 canonical result 하나로 수렴합니다.
  - `정문` -> `main-gate` 1건
  - `K관` -> `김수환관` 1건
- `K관`을 origin으로 쓴 nearby 검색도 stale-first cache 정책 이후 `5.9s` 수준으로 내려와 timeout baseline에서 벗어났습니다.
- 현재 남은 soft item은 `공지 카테고리 종류`, `7교시 시작 과목`처럼 API-first로는 **간접 확인**은 되지만 한 번에 설명해 주는 단일 endpoint/resource가 없는 케이스들입니다.

### 3. brand direct search는 안정권이고 long-tail은 watch 상태다

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

1. API-first resource/prompt gap
- `공지 카테고리 종류`, `7교시 시작 과목`은 단일 endpoint로 바로 답하기보다 chaining/간접 해석이 필요합니다.
- product contract 위반은 아니지만, 문서/리소스 보강 여지는 남아 있습니다.

2. brand long-tail watch 상태
- `커피빈`은 여전히 `[]`지만 현재 정책상 immediate bug라기보다 “campus-near 실재 후보 없음 또는 curated alias 범위 밖”으로 보는 편이 맞습니다.

3. course source-gap watchlist
- release gate에서 빠졌기 때문에 지금 당장 구현 우선순위는 아니지만, source truth 변화가 생기면 다시 확인해야 합니다.

## 지금은 주요 리스크가 아닌 것

- `classrooms timeout`
- `transport mode mismatch`
- `generic facility noun -> []`
- `스타벅스 주차장 노이즈`
- `정문/K관` short-query residual noise
- `origin=K관` nearby timeout
- `open_now=true`에 `null` item 섞임

이 일곱 가지는 이번 baseline에서는 더 이상 핵심 리스크로 분류하지 않습니다.

## 다음 구현 1순위

`MCP resource/prompt spot check 강화`

이유:
- release-pack은 이미 안정적이고 hard fail이 없습니다.
- 남은 soft item 8건 중 다수가 `공지 카테고리 종류`, `7교시 시작 과목`처럼 API-first로는 chaining이 필요한 설명형 질문에 몰려 있습니다.
- `short-query`와 `nearby latency`는 현재 baseline에서 해소됐고, 남은 course/brand watchlist는 코드 변경보다 관찰 성격이 더 강합니다.

## 관련 문서

- [Hidden Risk Audit](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-hidden-risk-audit.md)
- [Public MCP Release Pack 50](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-release-pack-50.md)
- [Public MCP Live Validation Summary](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-live-validation-summary.md)
