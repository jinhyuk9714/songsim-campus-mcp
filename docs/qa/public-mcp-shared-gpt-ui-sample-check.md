# Public MCP Shared GPT UI Sample Check

`Shared GPT` 실제 ChatGPT UI에서 metadata 질문 4개를 2026-03-16 KST 기준으로 확인한 기록입니다. 이 문서는 `HTTP/OpenAPI proxy` spot check를 실제 UI 답변으로 교차 검증하는 용도입니다.

## 점검 대상

- Shared GPT link
  - [가톨릭대 성심교정 도우미](https://chatgpt.com/g/g-69b526a162c48191843a6a7f469f5030-gatolrigdae-seongsimgyojeong-doumi)
- truth 비교용
  - `GET /gpt/notice-categories`
  - `GET /gpt/periods`
  - `GET /courses?year=2026&semester=1&limit=10`
  - `GET /gpt-actions-openapi-v2.json`

## UI Sample Check

| ID | User utterance | UI surface | Expected direct path | Observed UI summary | Verdict | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| SG01 | 공지 카테고리 종류 알려줘 | Shared GPT actual UI | `/gpt/notice-categories` | `academic`, `scholarship`, `employment (career)`, `general (place)` 4개를 직접 설명했다 | `pass` | category alias를 함께 노출해 proxy truth와 모순이 없다 |
| SG02 | employment랑 career 차이 설명해줘 | Shared GPT actual UI | `/gpt/notice-categories` | `차이 없다`, `employment`는 공식 이름이고 `career`는 alias라고 설명했다 | `pass` | `employment.aliases=[career]` truth와 일치한다 |
| SG03 | 7교시가 몇 시야 | Shared GPT actual UI | `/gpt/periods` | `7교시 = 15:00~15:50`로 정확히 답했고 6교시, 8교시도 함께 보여줬다 | `pass` | `/gpt/periods` truth와 일치한다 |
| SG04 | 7교시에 시작하는 과목 찾고 싶어 | Shared GPT actual UI | `/gpt/periods + /courses` | 7교시 시간을 바로 체인하지 않고, 학과/학년/학기 같은 추가 조건을 먼저 요청했다 | `soft_pass` | 사실 오류는 없지만 metadata + course chaining이 다소 간접적이다 |

## 결론

- Shared GPT 실제 UI에서도 metadata 질문 4개 중 3개는 direct path와 거의 동일하게 동작했습니다.
- 남은 soft item은 `7교시 시작 과목` 질문에서 metadata + course chaining이 즉답형이 아니라 추가 조건 요청형으로 나온다는 점입니다.
- 따라서 Shared GPT는 현재 운영 기준으로 metadata 설명용으로는 충분히 안정적이고, 남은 개선점은 `period -> course` chaining UX polish 쪽입니다.

## 관련 문서

- [Public MCP GPT Metadata Spot Check](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-gpt-metadata-spot-check.md)
- [Public MCP Hidden Risk Summary](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-hidden-risk-summary.md)
- [Public MCP Live Validation Summary](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-live-validation-summary.md)
