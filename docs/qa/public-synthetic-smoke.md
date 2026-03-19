# Public Synthetic Smoke

공개 배포 직후 학생용 핵심 경로를 빠르게 확인하는 최소 runbook입니다.

## 목적

- Render health check가 가리키는 `/healthz`가 정상인지 확인
- `registration_guides`가 공개 HTTP와 MCP 양쪽에서 보이는지 확인
- `notices`의 `academic` 최신 3건이 공개 HTTP와 MCP 양쪽에서 보이는지 확인
- 대표 `courses` watchlist query가 500/timeout 없이 처리되는지 확인
- 공개 MCP의 registration resource/tool contract가 깨지지 않았는지 확인

## 준비

아래 값을 실제 공개 배포 URL로 치환합니다.

```bash
export PUBLIC_HTTP_URL="https://your-public-api.onrender.com"
export PUBLIC_MCP_URL="https://your-public-mcp.onrender.com/mcp"
```

`jq`가 있으면 확인이 편하지만 필수는 아닙니다.

## 1. HTTP liveness

```bash
curl -fsS "$PUBLIC_HTTP_URL/healthz"
```

기대값:

- HTTP `200`
- body는 `{"ok":true}` 또는 공백 없는 동등 JSON

## 2. Registration guides HTTP smoke

```bash
curl -fsS "$PUBLIC_HTTP_URL/registration-guides?topic=payment_and_return&limit=3"
```

기대값:

- HTTP `200`
- JSON array
- 첫 결과 또는 상위 결과 안에 `"topic":"payment_and_return"`
- `"source_tag":"cuk_registration_guides"`가 보임

`jq` 예시:

```bash
curl -fsS "$PUBLIC_HTTP_URL/registration-guides?topic=payment_and_return&limit=3" \
  | jq '.[0] | {topic, title, source_tag}'
```

## 3. Representative courses watchlist query

watchlist canary는 현재 [public_api_eval_watchlist.jsonl](../../data/qa/public_api_eval_watchlist.jsonl)의 `CW02`를 기준으로 둡니다.

```bash
curl -fsS "$PUBLIC_HTTP_URL/courses?query=CSE301&year=2026&semester=1&limit=5"
```

기대값:

- HTTP `200`
- JSON array
- 비어 있어도 괜찮음
- 중요한 것은 `500`, HTML error page, timeout 없이 응답하는 것

이 쿼리는 학생-facing smoke라기보다 source-gap watchlist canary입니다. 결과 유무보다 응답 안정성을 봅니다.

## 4. Academic notices HTTP smoke

```bash
curl -fsS "$PUBLIC_HTTP_URL/notices?category=academic&limit=3"
```

기대값:

- HTTP `200`
- JSON array
- 첫 결과 또는 상위 결과 안에 `"category":"academic"`
- `"source_tag":"cuk_campus_notices"`가 보임

`jq` 예시:

```bash
curl -fsS "$PUBLIC_HTTP_URL/notices?category=academic&limit=3" \
  | jq '.[0] | {title, category, source_tag}'
```

## 5. MCP initialize + registration checks

아래 Python smoke는 live에서 검증한 payload 형태를 그대로 사용합니다.

```bash
./.venv/bin/python - <<'PY'
import httpx
from mcp.types import LATEST_PROTOCOL_VERSION

base = "https://songsim-public-mcp.onrender.com/mcp"
headers = {"accept": "application/json", "content-type": "application/json"}

with httpx.Client(timeout=20.0) as client:
    initialize = client.post(
        base,
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": LATEST_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "synthetic-smoke", "version": "1.0"},
            },
        },
    )
    print("initialize", initialize.status_code)
    session_id = initialize.headers["mcp-session-id"]

    call_headers = {
        **headers,
        "mcp-session-id": session_id,
        "mcp-protocol-version": LATEST_PROTOCOL_VERSION,
    }

    tool_call = client.post(
        base,
        headers=call_headers,
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "tool_list_registration_guides",
                "arguments": {"topic": "payment_and_return", "limit": 2},
            },
        },
    )
    print("tool_list_registration_guides", tool_call.status_code)

    notices_call = client.post(
        base,
        headers=call_headers,
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "tool_list_latest_notices",
                "arguments": {"category": "academic", "limit": 3},
            },
        },
    )
    print("tool_list_latest_notices", notices_call.status_code)

    resource_read = client.post(
        base,
        headers=call_headers,
        json={
            "jsonrpc": "2.0",
            "id": 4,
            "method": "resources/read",
            "params": {"uri": "songsim://registration-guide"},
        },
    )
    print("registration resource", resource_read.status_code)
PY
```

기대값:

- `initialize 200`
- `tool_list_registration_guides 200`
- `tool_list_latest_notices 200`
- `registration resource 200`
- `initialize` 응답의 `instructions`에 `registration` 문구가 포함됨
- `tool_list_registration_guides` payload가 빈 결과가 아님
- `tool_list_latest_notices` payload가 빈 결과가 아니고 academic 항목을 포함함
- `resources/read` 결과의 첫 항목에 `source_tag=cuk_registration_guides`가 포함됨

## Pass 기준

- `/healthz`가 `200`과 `{"ok":true}`를 반환
- `/registration-guides`가 `payment_and_return` topic과 `cuk_registration_guides` source tag를 반환
- `/notices?category=academic&limit=3`가 `academic` notice와 `cuk_campus_notices` source tag를 반환
- `/courses?query=CSE301...`가 빈 배열이어도 좋으니 `200`으로 안정 응답
- MCP initialize가 성공하고 `tool_list_registration_guides`, `tool_list_latest_notices`, `songsim://registration-guide`가 모두 노출
- MCP registration tool call이 에러 없이 응답

이 다섯 가지가 통과하면 registration-guides 공개 런치 closeout smoke는 충분합니다.
