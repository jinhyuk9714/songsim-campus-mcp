# Public MCP GPT Metadata Spot Check

`HTTP/OpenAPI proxy` 기준으로 Shared GPT metadata entrypoint를 2026-03-16 KST 공개 배포에서 다시 확인한 기록입니다. 이후 같은 날짜에 실제 Shared GPT UI 샘플 4문장도 별도로 점검했습니다.

## 점검 대상

- `GET /gpt/notice-categories`
- `GET /gpt/periods`
- `GET /gpt-actions-openapi-v2.json`
- truth 비교용
  - `GET /notice-categories`
  - `GET /periods`
  - `GET /courses?year=2026&semester=1&limit=10`

## Spot Check

| ID | User utterance | Proxy surface | Expected direct path | Observed response summary | Verdict | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| GM01 | 공지 카테고리 종류 알려줘 | `GET /gpt/notice-categories` | `/gpt/notice-categories` | `academic`, `scholarship`, `employment`, `general` 4개가 직접 반환된다 | `pass` | `/notice-categories`는 같은 truth를 한글 display로 반환한다 |
| GM02 | employment랑 career 차이 설명해줘 | `GET /gpt/notice-categories` | `/gpt/notice-categories` | `employment.aliases = [\"career\"]`가 직접 노출된다 | `pass` | compatibility alias를 API-first로 직접 읽을 수 있다 |
| GM03 | 7교시가 몇 시야 | `GET /gpt/periods` | `/gpt/periods` | `period=7, start=15:00, end=15:50`가 직접 반환된다 | `pass` | `/periods`도 같은 truth를 반환한다 |
| GM04 | 7교시에 시작하는 과목 찾고 싶어 | `GET /gpt/periods` + `GET /courses?year=2026&semester=1&period_start=7&limit=10` | `/gpt/periods + /courses(period_start=7)` | `/gpt/periods`에서 7교시 시각을 확인할 수 있고 `/courses?...period_start=7`은 `3D애니메이션1`을 포함한 7교시 시작 과목만 직접 반환한다 | `pass` | direct metadata + direct course filter 경로가 이제 충분히 명확하다 |

## OpenAPI 확인

- `GET /gpt-actions-openapi-v2.json`
  - `/gpt/notice-categories`
  - `/gpt/periods`

즉 GPT Actions v2 schema에도 metadata endpoint가 정상 포함되어 있습니다.

## 결론

- `공지 카테고리`와 `7교시` 계열 질문은 이제 간접 추론이 아니라 **direct metadata + direct course filter path**로 설명 가능합니다.
- 이 축은 더 이상 hidden-risk의 핵심 soft item으로 두지 않아도 됩니다.

## Actual UI Note

- 실제 Shared GPT UI 수동 샘플 확인은 별도 문서로 기록했습니다.
- 기존 UI 샘플은 이번 `period_start` direct filter rollout 이전 결과라서, UI 쪽은 별도 재확인이 필요합니다.

## 관련 문서

- [Public MCP Hidden Risk Summary](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-hidden-risk-summary.md)
- [Public MCP Live Validation Summary](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-live-validation-summary.md)
- [Public MCP Shared GPT UI Sample Check](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-shared-gpt-ui-sample-check.md)
