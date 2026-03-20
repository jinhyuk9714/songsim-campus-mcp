# Public Synthetic Smoke

공개 배포 직후 학생용 핵심 경로를 빠르게 확인하는 최소 runbook입니다.

## 목적

- Render health check가 가리키는 `/healthz`가 정상인지 확인
- `registration_guides`가 공개 HTTP와 MCP 양쪽에서 보이는지 확인
- `class_guides`가 공개 HTTP와 MCP 양쪽에서 보이는지 확인
- `seasonal_semester_guides`가 공개 HTTP와 MCP 양쪽에서 보이는지 확인
- `phone_book_entries`가 공개 HTTP와 MCP 양쪽에서 보이는지 확인
- `dormitory_guides`가 공개 HTTP와 MCP 양쪽에서 보이는지 확인
- `affiliated_notices`가 공개 HTTP와 MCP 양쪽에서 보이는지 확인
- `notices`의 `academic` 최신 3건이 공개 HTTP와 MCP 양쪽에서 보이는지 확인
- nearby restaurants의 대표 alias origin과 strict `open_now` 경로가 공개 HTTP/MCP에서 유지되는지 확인
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

## 4. Class guides HTTP smoke

```bash
curl -fsS "$PUBLIC_HTTP_URL/class-guides?topic=course_evaluation&limit=3"
```

기대값:

- HTTP `200`
- JSON array
- 첫 결과 또는 상위 결과 안에 `"topic":"course_evaluation"`
- `"source_tag":"cuk_class_guides"`가 보임

`jq` 예시:

```bash
curl -fsS "$PUBLIC_HTTP_URL/class-guides?topic=course_evaluation&limit=3" \
  | jq '.[0] | {topic, title, source_tag}'
```

## 5. Academic notices HTTP smoke

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

## 5.5 Affiliated notices HTTP smoke

```bash
curl -fsS "$PUBLIC_HTTP_URL/affiliated-notices?topic=international_studies&limit=3"
curl -fsS "$PUBLIC_HTTP_URL/affiliated-notices?topic=dorm_k_a_checkin_out&query=입퇴사&limit=3"
```

기대값:

- HTTP `200`
- JSON array
- 첫 결과 또는 상위 결과 안에 `"topic":"international_studies"` 또는 `"topic":"dorm_k_a_checkin_out"`
- `"source_tag":"cuk_affiliated_notice_boards"`가 보임

`jq` 예시:

```bash
curl -fsS "$PUBLIC_HTTP_URL/affiliated-notices?topic=international_studies&limit=3" \
  | jq '.[0] | {topic, title, published_at, source_tag}'
```

## 6. Seasonal semester guides HTTP smoke

```bash
curl -fsS "$PUBLIC_HTTP_URL/seasonal-semester-guides?topic=seasonal_semester&limit=2"
```

기대값:

- HTTP `200`
- JSON array
- 첫 결과 또는 상위 결과 안에 `"topic":"seasonal_semester"`
- `"source_tag":"cuk_seasonal_semester_guides"`가 보임

`jq` 예시:

```bash
curl -fsS "$PUBLIC_HTTP_URL/seasonal-semester-guides?topic=seasonal_semester&limit=2" \
  | jq '.[0] | {topic, title, source_tag}'
```

## 7. Phone book HTTP smoke

```bash
curl -fsS "$PUBLIC_HTTP_URL/phone-book?query=%EB%B3%B4%EA%B1%B4%EC%8B%A4&limit=1"
```

기대값:

- HTTP `200`
- JSON array
- 첫 결과 안에 `"department":"보건실"`
- `"source_tag":"cuk_phone_book"`가 보임

`jq` 예시:

```bash
curl -fsS "$PUBLIC_HTTP_URL/phone-book?query=%EB%B3%B4%EA%B1%B4%EC%8B%A4&limit=1" \
  | jq '.[0] | {department, phone, source_tag}'
```

## 8. Nearby restaurants HTTP smoke

```bash
curl -fsS "$PUBLIC_HTTP_URL/restaurants/nearby?origin=%EC%A4%91%EB%8F%84&limit=3"
curl -fsS "$PUBLIC_HTTP_URL/restaurants/nearby?origin=%ED%95%99%EC%83%9D%EC%8B%9D%EB%8B%B9&open_now=true&category=cafe&limit=3"
```

기대값:

- 두 요청 모두 HTTP `200`
- `origin=중도` 응답은 빈 배열이 아니고, 상위 결과들의 `"origin"`이 `"central-library"`로 정규화됨
- `origin=학생식당&open_now=true&category=cafe` 응답은 현재 contract상 빈 배열이어도 괜찮음
- 중요한 회귀 기준은 `open_now=true` 응답에 `open_now=null` item이 섞이지 않는 것

`jq` 예시:

```bash
curl -fsS "$PUBLIC_HTTP_URL/restaurants/nearby?origin=%EC%A4%91%EB%8F%84&limit=3" \
  | jq '.[0] | {name, origin, estimated_walk_minutes, source_tag}'
```

## 9. Dormitory guides HTTP smoke

```bash
curl -fsS "$PUBLIC_HTTP_URL/dormitory-guides?topic=hall_info&limit=2"
curl -fsS "$PUBLIC_HTTP_URL/dormitory-guides?topic=latest_notices&limit=2"
```

기대값:

- HTTP `200`
- JSON array
- `topic=hall_info` 결과는 `스테파노관` 또는 `안드레아관` 같은 기숙사 동을 포함
- `topic=latest_notices` 결과는 홈 최신 공지 카드를 반환
- `"source_tag":"cuk_dormitory_guides"`가 보임

`jq` 예시:

```bash
curl -fsS "$PUBLIC_HTTP_URL/dormitory-guides?topic=latest_notices&limit=2" \
  | jq '.[0] | {topic, title, source_tag}'
```

## 10. MCP initialize + guide checks

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

    class_call = client.post(
        base,
        headers=call_headers,
        json={
            "jsonrpc": "2.0",
            "id": 21,
            "method": "tools/call",
            "params": {
                "name": "tool_list_class_guides",
                "arguments": {"topic": "course_evaluation", "limit": 2},
            },
        },
    )
    print("tool_list_class_guides", class_call.status_code)

    seasonal_call = client.post(
        base,
        headers=call_headers,
        json={
            "jsonrpc": "2.0",
            "id": 22,
            "method": "tools/call",
            "params": {
                "name": "tool_list_seasonal_semester_guides",
                "arguments": {"topic": "seasonal_semester", "limit": 2},
            },
        },
    )
    print("tool_list_seasonal_semester_guides", seasonal_call.status_code)

    milestone_call = client.post(
        base,
        headers=call_headers,
        json={
            "jsonrpc": "2.0",
            "id": 23,
            "method": "tools/call",
            "params": {
                "name": "tool_list_academic_milestone_guides",
                "arguments": {"topic": "grade_evaluation", "limit": 2},
            },
        },
    )
    print("tool_list_academic_milestone_guides", milestone_call.status_code)

    phone_book_call = client.post(
        base,
        headers=call_headers,
        json={
            "jsonrpc": "2.0",
            "id": 24,
            "method": "tools/call",
            "params": {
                "name": "tool_search_phone_book",
                "arguments": {"query": "보건실", "limit": 1},
            },
        },
    )
    print("tool_search_phone_book", phone_book_call.status_code)

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

    affiliated_notices_call = client.post(
        base,
        headers=call_headers,
        json={
            "jsonrpc": "2.0",
            "id": 31,
            "method": "tools/call",
            "params": {
                "name": "tool_list_affiliated_notices",
                "arguments": {"topic": "international_studies", "limit": 3},
            },
        },
    )
    print("tool_list_affiliated_notices", affiliated_notices_call.status_code)

    nearby_call = client.post(
        base,
        headers=call_headers,
        json={
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "tool_find_nearby_restaurants",
                "arguments": {"origin": "중도", "limit": 3},
            },
        },
    )
    print("tool_find_nearby_restaurants", nearby_call.status_code)

    resource_read = client.post(
        base,
        headers=call_headers,
        json={
            "jsonrpc": "2.0",
            "id": 5,
            "method": "resources/read",
            "params": {"uri": "songsim://registration-guide"},
        },
    )
    print("registration resource", resource_read.status_code)

    class_resource_read = client.post(
        base,
        headers=call_headers,
        json={
            "jsonrpc": "2.0",
            "id": 6,
            "method": "resources/read",
            "params": {"uri": "songsim://class-guide"},
        },
    )
    print("class resource", class_resource_read.status_code)

    seasonal_resource_read = client.post(
        base,
        headers=call_headers,
        json={
            "jsonrpc": "2.0",
            "id": 7,
            "method": "resources/read",
            "params": {"uri": "songsim://seasonal-semester-guide"},
        },
    )
    print("seasonal semester resource", seasonal_resource_read.status_code)

    milestone_resource_read = client.post(
        base,
        headers=call_headers,
        json={
            "jsonrpc": "2.0",
            "id": 8,
            "method": "resources/read",
            "params": {"uri": "songsim://academic-milestone-guide"},
        },
    )
    print("academic milestone resource", milestone_resource_read.status_code)

    phone_book_resource_read = client.post(
        base,
        headers=call_headers,
        json={
            "jsonrpc": "2.0",
            "id": 9,
            "method": "resources/read",
            "params": {"uri": "songsim://phone-book"},
        },
    )
    print("phone book resource", phone_book_resource_read.status_code)

    affiliated_notices_resource_read = client.post(
        base,
        headers=call_headers,
        json={
            "jsonrpc": "2.0",
            "id": 32,
            "method": "resources/read",
            "params": {"uri": "songsim://affiliated-notices"},
        },
    )
    print("affiliated notices resource", affiliated_notices_resource_read.status_code)

    dormitory_tool_call = client.post(
        base,
        headers=call_headers,
        json={
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {
                "name": "tool_list_dormitory_guides",
                "arguments": {"topic": "latest_notices", "limit": 2},
            },
        },
    )
    print("tool_list_dormitory_guides", dormitory_tool_call.status_code)

    dormitory_resource_read = client.post(
        base,
        headers=call_headers,
        json={
            "jsonrpc": "2.0",
            "id": 11,
            "method": "resources/read",
            "params": {"uri": "songsim://dormitory-guide"},
        },
    )
    print("dormitory resource", dormitory_resource_read.status_code)
PY
```

기대값:

- `initialize 200`
- `tool_list_registration_guides 200`
- `tool_list_class_guides 200`
- `tool_list_seasonal_semester_guides 200`
- `tool_list_academic_milestone_guides 200`
- `tool_search_phone_book 200`
- `tool_list_affiliated_notices 200`
- `tool_list_latest_notices 200`
- `tool_find_nearby_restaurants 200`
- `registration resource 200`
- `class resource 200`
- `seasonal semester resource 200`
- `academic milestone resource 200`
- `phone book resource 200`
- `affiliated notices resource 200`
- `tool_list_dormitory_guides 200`
- `dormitory resource 200`
- `initialize` 응답의 `instructions`에 `registration` 문구가 포함됨
- `tool_list_registration_guides` payload가 빈 결과가 아님
- `tool_list_class_guides` payload가 빈 결과가 아니고 `course_evaluation` 항목을 포함함
- `tool_list_seasonal_semester_guides` payload가 빈 결과가 아니고 `seasonal_semester` 항목을 포함함
- `tool_list_academic_milestone_guides` payload가 빈 결과가 아니고 `grade_evaluation` 항목을 포함함
- `tool_search_phone_book` payload가 빈 결과가 아니고 `보건실` 항목을 포함함
- `tool_list_affiliated_notices` payload가 빈 결과가 아니고 `international_studies` 또는 dorm topic 항목을 포함함
- `tool_list_dormitory_guides` payload가 빈 결과가 아니고 `latest_notices` 또는 `hall_info` 항목을 포함함
- `tool_list_latest_notices` payload가 빈 결과가 아니고 academic 항목을 포함함
- `tool_find_nearby_restaurants` payload가 빈 결과가 아니고 nearby 식당 요약 payload를 반환함
- `resources/read` 결과의 첫 항목에 `source_tag=cuk_registration_guides`가 포함됨
- `class` resource 결과의 첫 항목에 `source_tag=cuk_class_guides`가 포함됨
- `seasonal semester` resource 결과의 첫 항목에 `source_tag=cuk_seasonal_semester_guides`가 포함됨
- `academic milestone` resource 결과의 첫 항목에 `source_tag=cuk_academic_milestone_guides`가 포함됨
- `phone book` resource 결과의 첫 항목에 `source_tag=cuk_phone_book`가 포함됨
- `affiliated notices` resource 결과의 첫 항목에 `source_tag=cuk_affiliated_notice_boards`가 포함됨
- `dormitory resource` 결과의 첫 항목에 `source_tag=cuk_dormitory_guides`가 포함됨

## Pass 기준

- `/healthz`가 `200`과 `{"ok":true}`를 반환
- `/registration-guides`가 `payment_and_return` topic과 `cuk_registration_guides` source tag를 반환
- `/class-guides`가 `course_evaluation` topic과 `cuk_class_guides` source tag를 반환
- `/seasonal-semester-guides`가 `seasonal_semester` topic과 `cuk_seasonal_semester_guides` source tag를 반환
- `/academic-milestone-guides`가 `grade_evaluation` topic과 `cuk_academic_milestone_guides` source tag를 반환
- `/phone-book`가 `보건실` 또는 질의한 부서의 `cuk_phone_book` source tag를 반환
- `/affiliated-notices`가 `international_studies` 또는 질의한 dorm/topic의 `cuk_affiliated_notice_boards` source tag를 반환
- `/notices?category=academic&limit=3`가 `academic` notice와 `cuk_campus_notices` source tag를 반환
- `/restaurants/nearby?origin=중도`가 `central-library` origin으로 nearby 결과를 반환
- `/restaurants/nearby?origin=학생식당&open_now=true&category=cafe&limit=3`가 `200`으로 안정 응답하고, 빈 배열이어도 `open_now` strict contract와 일치
- `/courses?query=CSE301...`가 빈 배열이어도 좋으니 `200`으로 안정 응답
- MCP initialize가 성공하고 `tool_list_registration_guides`, `tool_list_class_guides`, `tool_list_seasonal_semester_guides`, `tool_list_academic_milestone_guides`, `tool_search_phone_book`, `tool_list_affiliated_notices`, `tool_list_dormitory_guides`, `tool_list_latest_notices`, `tool_find_nearby_restaurants`, `songsim://registration-guide`, `songsim://class-guide`, `songsim://seasonal-semester-guide`, `songsim://academic-milestone-guide`, `songsim://phone-book`, `songsim://affiliated-notices`, `songsim://dormitory-guide`가 모두 노출
- MCP registration/affiliated/nearby tool call이 에러 없이 응답

이 기준이 통과하면 class-guides + registration-guides + seasonal-semester-guides + academic-milestone-guides + phone-book + affiliated notices + dormitory + nearby restaurant 공개 smoke는 충분합니다.
