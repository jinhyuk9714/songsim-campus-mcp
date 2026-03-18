# Public MCP Course Watchlist

`release gate`에서 분리한 course source-gap 질의를 2026-03-16 KST 기준 공개 배포에서 다시 확인한 기록입니다. 이 문서는 제품 fail 목록이 아니라 **source-backed 여부 관찰용 watchlist**입니다. 같은 날짜의 post-rollout cleanup 재점검과 final Shared GPT recheck 시점에도 이 5건의 verdict는 바뀌지 않았습니다.

## 판정 기준

- `near_match_only`
  - direct hit는 없지만 source-backed 근사 결과가 있다
- `no_source_backed_hit`
  - direct hit가 없고 현재 공개 source truth 기준으로도 비어 있다
- `recovered`
  - 이전 watch 항목이 현재는 source-backed direct hit로 회복됐다

## Watchlist

| ID | User utterance | Endpoint | Source truth status | Observed response summary | Watch verdict | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| CW01 | 데이터베이스 과목 있어 | `GET /courses?query=데이터베이스&year=2026&semester=1&limit=5` | direct title hit 없음, near match 존재 | `데이터베이스활용` 1건 반환 | `near_match_only` | 현재는 `데이터베이스` 자체 canary가 아니라 근사 결과 관찰 항목이다 |
| CW02 | CSE301 과목 뭐야 | `GET /courses?query=CSE301&year=2026&semester=1&limit=5` | source-backed direct hit 미확인 | `[]` | `no_source_backed_hit` | release gate 바깥의 code watchlist 유지 |
| CW03 | 김가톨 교수 수업 있어 | `GET /courses?query=김가톨&year=2026&semester=1&limit=5` | source-backed professor hit 미확인 | `[]` | `no_source_backed_hit` | 교수명 watchlist로만 계속 추적한다 |
| CW04 | 데이타베이스 과목 있어 | `GET /courses?query=데이타베이스&year=2026&semester=1&limit=5` | typo direct hit 미확인 | `[]` | `no_source_backed_hit` | 현재 deterministic typo canary로 쓰지 않는다 |
| CW05 | CSE 420 과목 뭐야 | `GET /courses?query=CSE%20420&year=2026&semester=1&limit=5` | spacing code direct hit 미확인 | `[]` | `no_source_backed_hit` | code-spacing watchlist로 유지한다 |

## 해석

- 현재 5건 중 `recovered`는 없습니다.
- `데이터베이스`는 완전 빈 결과가 아니라 `데이터베이스활용` near match가 있어, source truth 변화가 생기면 가장 먼저 다시 볼 후보입니다.
- 나머지 4건은 아직도 `no_source_backed_hit`이며, 현재는 코드 수정보다 source truth 변화 모니터링이 우선입니다.
- 최근 brand long-tail 정리나 metadata parity 반영과는 별개로, course watchlist 상태 자체는 변하지 않았습니다.

## 관련 문서

- [Public MCP Live Validation Summary](public-mcp-live-validation-summary.md)
- [Public MCP Hidden Risk Summary](public-mcp-hidden-risk-summary.md)
