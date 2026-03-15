# Public MCP Hidden Risk Summary

`public API`를 대상으로 한 숨은 운영 리스크 감사 요약입니다. 기존 릴리즈팩과 20/50문장 실측에서 충분히 부각되지 않았던 **mode mismatch, timeout, generic facility gap, short-query ambiguity**를 별도로 확인했습니다.

## 집계

- audit size: 30
- `pass`: 11
- `soft_pass`: 4
- `soft_fail`: 4
- `fail`: 11
- latency
  - `fast`: 21
  - `slow`: 5
  - `timeout`: 4

## 가장 큰 리스크

1. `classrooms` happy-path timeout
- `학생미래인재관`, `김수환관`, `니콜스`, `N관` 기준 공실 조회가 모두 `12s` client timeout으로 끝났습니다.
- 반대로 invalid building인 `정문`은 빠르게 `400`을 반환해서, 거절 경로보다 happy-path 계산 경로가 더 위험하다는 신호입니다.

2. `transport` query-to-mode mismatch
- `지하철`, `1호선`, `지하철만`, `subway`, `셔틀` 질의에서도 첫 결과가 계속 `마을버스`, `시내버스`로 나왔습니다.
- 즉 교통 데이터 자체보다 **질문 의도를 mode로 좁히는 랭킹/파라미터화**가 약합니다.

3. generic facility noun gap
- `헬스장`, `편의점`, `체육관`, `ATM`은 대부분 빈 결과였습니다.
- `트러스트짐`, `카페 보나`, `부온 프란조`처럼 curated alias는 되지만, 학생이 더 자주 쓰는 generic noun은 아직 못 받습니다.

4. short-query ambiguity remains
- `정문`은 정답이 1위지만 `창업보육센터`가 따라옵니다.
- `K관`은 place/classroom 양쪽에서 여전히 `김수환관`과 `스테파노기숙사`가 충돌합니다.

## 중간 위험

- 브랜드 direct search는 curated brand 기준으로는 좋아졌습니다.
  - `매머드커피`, `메가커피`는 캠퍼스 근접 지점이 1위입니다.
  - compact GPT route도 같은 순서를 따릅니다.
- 다만 long-tail brand는 coverage가 얕습니다.
  - `커피빈`은 빈 결과
  - `스타벅스`는 되지만 parking-like noisy entity가 같이 걸립니다.

## 보조 관찰

- `course`는 이번 감사의 주대상은 아니지만, representative spot check 기준으로
  - `데이터베이스` -> `데이터베이스활용` 1건
  - `데이타베이스`, `CSE 420` -> 빈 결과
- 따라서 남은 course 문제는 계속 `search bug`보다 `source/snapshot coverage gap` 쪽으로 보는 편이 맞습니다.

- `open_now` strict semantics는 이미 코드상으로 잠겼지만,
  - `학생식당 기준 지금 여는 카페만 3개`
  - representative live query 자체가 `12s` timeout이 났습니다.
- 즉 정확성 문제보다 **live latency risk**가 먼저입니다.

## 바로 다음 우선순위

1. `classrooms timeout/performance fix`
- happy-path building query를 10초 안으로 안정화하지 못하면 실제 사용성에 가장 치명적입니다.

2. `transport mode/ranking fix`
- `지하철`, `1호선`, `bus/subway` 같은 강한 cue를 mode 선택에 직접 연결해야 합니다.

3. `generic facility taxonomy expansion`
- `헬스장`, `편의점`, `체육관`, `ATM` 같은 생활어를 parent building alias나 dedicated facility vocabulary로 보강할 필요가 있습니다.

4. `short-query disambiguation polish`
- `K관`, `정문` 노이즈를 더 줄이면 place/classroom 품질이 같이 올라갑니다.

5. `brand search long-tail cleanup`
- `커피빈`, `스타벅스` 같은 long-tail brand coverage와 noisy Kakao entities 정리를 다음 순서로 잡는 편이 좋습니다.

## 관련 문서

- [Hidden Risk Audit](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-hidden-risk-audit.md)
- [Public MCP Release Pack 50](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-release-pack-50.md)
- [Public MCP Live Validation Summary](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-live-validation-summary.md)
