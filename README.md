# Songsim Campus MCP

가톨릭대학교 성심교정 학생이 학기 중 실제로 처리해야 하는 질문을  
**공식 source 기반 Remote MCP + HTTP API**로 연결하는 프로젝트입니다.

공개 배포에서는 **read-only Remote MCP**가 학생용 기본 입구이고,  
**HTTP API**는 같은 결과를 직접 검증하거나 외부 앱에서 연동할 때 쓰는 companion layer입니다.
Local Full Mode는 운영과 개인화용 별도 모드입니다.

[Public API](https://songsim-public-api.onrender.com) · [Connect ChatGPT](docs/connect-chatgpt.md) · [Connect Codex](docs/connect-codex.md) · [Connect Claude](docs/connect-claude.md) · [Source Registry](docs/source_registry.md) · [QA Baseline](docs/qa/public-api-live-validation-1000.md)

## Why this project

학생은 생각보다 비슷한 질문을 자주 반복합니다.

- `학생회관 어디야?`
- `우리은행 전화번호 알려줘`
- `2026학년도 3월 학사일정 보여줘`
- `등록금 반환 기준 알려줘`
- `재학증명서 발급 방법 알려줘`
- `최신 학사 공지 2개 보여줘`
- `학생식당 메뉴 보여줘`
- `중앙도서관 열람실 남은 좌석 알려줘`
- `니콜스관 지금 예상 빈 강의실 있어?`
- `성심교정 지하철 오는 길 알려줘`

이 프로젝트는 그런 질문을 **공식 source 기반 structured answer**로 연결하는 캠퍼스 전용 도구 서버입니다. 핵심은 챗봇 흉내가 아니라, 검증 가능한 student-facing MCP product를 만드는 데 있습니다.

## What Makes It Strong

### MCP-first

학생이 실제로 쓰는 입구는 Remote MCP입니다. ChatGPT, Codex, Claude 같은 MCP 클라이언트에서 바로 연결해서 사용할 수 있습니다.

### Student-first

질문 축이 추상적이지 않습니다. `오늘 할 일`, `어디/연락처`, `절차/제도`, `공부공간/자원`, `특수 경로`처럼 학생이 바로 행동으로 옮기는 여정을 먼저 다룹니다.

### Trust-first

학교 공식 source에 없는 값은 만들지 않습니다. 없거나 불확실하면 `null` 또는 빈 결과를 반환합니다.

### Proof-first

기능 설명만 하지 않고, source policy와 live QA baseline을 같이 공개합니다.

## Student-Facing Surfaces

### 1. Remote MCP

학생용 **primary surface**입니다.

대표 resource / tool:

- `songsim://usage-guide`
- `songsim://academic-calendar`
- `songsim://registration-guide`
- `songsim://class-guide`
- `songsim://academic-milestone-guide`
- `songsim://student-exchange-guide`
- `songsim://student-exchange-partners`
- `songsim://phone-book`
- `songsim://campus-life-support-guide`
- `songsim://dormitory-guide`
- `songsim://certificate-guide`
- `songsim://scholarship-guide`
- `songsim://affiliated-notices`
- `songsim://campus-life-notices`
- `songsim://transport-guide`
- `songsim://wifi-guide`
- `tool_search_places`
- `tool_search_courses`
- `tool_search_phone_book`
- `tool_search_pc_software`
- `tool_list_latest_notices`
- `tool_list_affiliated_notices`
- `tool_list_campus_life_notices`
- `tool_search_dining_menus`
- `tool_find_nearby_restaurants`
- `tool_get_library_seat_status`
- `tool_list_estimated_empty_classrooms`

### 2. HTTP API

같은 데이터를 직접 확인하거나 앱에 붙일 때 쓰는 **companion layer**입니다.

대표 endpoint:

- `/places`
- `/phone-book`
- `/courses`
- `/periods`
- `/academic-calendar`
- `/registration-guides`
- `/class-guides`
- `/seasonal-semester-guides`
- `/academic-milestone-guides`
- `/student-exchange-guides`
- `/student-exchange-partners`
- `/certificate-guides`
- `/leave-of-absence-guides`
- `/academic-status-guides`
- `/academic-support-guides`
- `/scholarship-guides`
- `/notices`
- `/affiliated-notices`
- `/campus-life-notices`
- `/dormitory-guides`
- `/campus-life-support-guides`
- `/pc-software`
- `/dining-menus`
- `/restaurants/nearby`
- `/restaurants/search`
- `/library-seats`
- `/classrooms/empty`
- `/transport`
- `/wifi-guides`

## What This Project Can Answer

| 영역 | 어떤 질문을 받나 | 대표 질문 | 대표 MCP resource/tool | 대표 HTTP companion |
| --- | --- | --- | --- | --- |
| 오늘 할 일 | 최신 공지, 소속기관 공지, 행사/대외 프로그램, 월별 학사일정 | `최신 학사 공지 2개 보여줘` `국제학부 최신 공지 알려줘` `행사안내 보여줘` `2026학년도 3월 학사일정 보여줘` | `tool_list_latest_notices` `tool_list_affiliated_notices` `tool_list_campus_life_notices` `tool_list_academic_calendar` | `/notices` `/affiliated-notices` `/campus-life-notices` `/academic-calendar` |
| 어디 / 연락처 | 건물, 별칭, 편의시설, 전화번호, 운영시간, 교통, Wi-Fi | `학생회관 어디야?` `복사실이 어디야?` `보건실 전화번호 알려줘` `니콜스관 WIFI 안내 알려줘` | `songsim://usage-guide` `tool_search_places` `tool_get_place` `tool_search_phone_book` `tool_list_transport_guides` `tool_list_wifi_guides` | `/places` `/places/{identifier}` `/phone-book` `/transport` `/wifi-guides` |
| 절차 / 제도 | 등록, 증명, 휴학, 복학/자퇴/재입학, 수업, 계절학기, 성적·졸업, 학생교류, 장학 | `등록금 반환 기준 알려줘` `재학증명서 발급 방법 알려줘` `공결 신청 방법 알려줘` `계절학기 신청 시기 알려줘` `졸업요건 알려줘` `국내 학점교류 신청대상 알려줘` | `tool_list_registration_guides` `tool_list_certificate_guides` `tool_list_leave_of_absence_guides` `tool_list_academic_status_guides` `tool_list_class_guides` `tool_list_seasonal_semester_guides` `tool_list_academic_milestone_guides` `tool_list_student_exchange_guides` `tool_search_student_exchange_partners` `tool_list_scholarship_guides` | `/registration-guides` `/certificate-guides` `/leave-of-absence-guides` `/academic-status-guides` `/class-guides` `/seasonal-semester-guides` `/academic-milestone-guides` `/student-exchange-guides` `/student-exchange-partners` `/scholarship-guides` |
| 공부공간 / 자원 | 과목, 교시, 도서관 좌석, 예상 빈 강의실, 학식, 주변 식당, PC 소프트웨어 | `7교시가 몇 시야?` `2026년 1학기 객체지향 과목 찾아줘` `중앙도서관 열람실 남은 좌석 알려줘` `K관 지금 예상 빈 강의실 있어?` `학생식당 메뉴 보여줘` `SPSS 설치된 컴퓨터실 어디야` | `tool_search_courses` `tool_get_class_periods` `tool_get_library_seat_status` `tool_list_estimated_empty_classrooms` `tool_search_dining_menus` `tool_find_nearby_restaurants` `tool_search_restaurants` `tool_search_pc_software` | `/courses` `/periods` `/library-seats` `/classrooms/empty` `/dining-menus` `/restaurants/nearby` `/restaurants/search` `/pc-software` |
| 특수 경로 | 기숙사, 생활지원, 상담·예비군·병원, 소속기관 공지 | `성심교정 기숙사 안내해줘` `학생상담 어디서 받아?` `예비군 신고 시기 알려줘` `부속병원 이용 안내해줘` `프란치스코관 입퇴사공지 알려줘` | `tool_list_dormitory_guides` `tool_list_campus_life_support_guides` `tool_list_affiliated_notices` | `/dormitory-guides` `/campus-life-support-guides` `/affiliated-notices` |

질문 패턴 예시:

- 오늘 할 일: `최신 학사 공지 2개 보여줘`, `행사안내 보여줘`, `3월 학사일정 알려줘`
- 어디 / 연락처: `학생회관 어디야?`, `보건실 전화번호 알려줘`, `트러스트짐 운영시간 알려줘`
- 절차 / 제도: `등록금 납부 방법 알려줘`, `공결 신청 방법 알려줘`, `졸업논문 제출 절차 알려줘`
- 공부공간 / 자원: `7교시에 시작하는 과목 찾고 싶어`, `중앙도서관 열람실 남은 좌석 알려줘`, `포토샵 있는 PC실 알려줘`
- 특수 경로: `기숙사 입사안내 어디서 봐?`, `학생상담 어디서 받아?`, `국제학부 최신 공지 알려줘`

## Reliability Contract

이 프로젝트는 **정답을 꾸며내는 대신 신뢰 경계를 드러내는 방식**을 택합니다.

- 학교 공식 source에 없는 값은 만들지 않음
- 없거나 불확실하면 `null` 또는 빈 결과 반환
- 일부 동적 도메인은 best-effort / fallback 정책을 명시적으로 사용

현재 기준 정책:

- 도서관 좌석: `live fetch + stale fallback`
- 예상 빈 강의실: `realtime` source를 먼저 시도하고, 없으면 시간표 기준 예상 공실로 폴백

## Quality Proof

공개 student surface는 설명만이 아니라 **live validation baseline**으로 관리합니다.

Public API live baseline 기준:

- checked_at: `2026-03-21T12:31:05+00:00`
- corpus size: `1000`
- executed: `1005`
- hard fail: `0`
- watch: `5`
- skip: `104`

`executed`는 main corpus 1000건에 watchlist 5건을 함께 실행한 값입니다. 현재 hard fail은 없고, watch item은 course source-gap 계열로 분리되어 있습니다. `skip`은 degraded truth 경로로 남은 케이스입니다. 자세한 내용은 [공개 API 1000문장 라이브 검증](docs/qa/public-api-live-validation-1000.md)에서 확인할 수 있습니다.

Public MCP는 별도 release pack과 live validation 문서로 관리합니다.

- [Public MCP Release Pack (50)](docs/qa/public-mcp-release-pack-50.md)
- [Public MCP Live Validation Summary](docs/qa/public-mcp-live-validation-summary.md)

## Quick MCP Flow

학생용 기본 흐름은 아래처럼 보면 됩니다.

1. `songsim://usage-guide`로 공개 범위와 규칙 확인
2. prompt / resource가 가리키는 tool 호출
3. 필요하면 HTTP API companion으로 같은 결과를 직접 검증

예시 흐름:

- 장소 검색: `prompt_find_place -> tool_search_places -> tool_get_place`
- 공지 조회: `prompt_latest_notices -> tool_list_latest_notices`
- 도서관 좌석: `prompt_library_seat_status -> tool_get_library_seat_status`
- 예상 빈 강의실: `prompt_find_empty_classrooms -> tool_list_estimated_empty_classrooms`
- 근처 식당: `prompt_find_nearby_restaurants -> tool_find_nearby_restaurants`

## Quick Start

### 1. Install

`uv` 기준:

```bash
uv sync --extra dev --extra mcp --extra scrape
```

`pip` 기준:

```bash
pip install -e '.[dev,mcp,scrape]'
```

### 2. Configure

```bash
cp .env.example .env
```

공개 read-only 배포 예시:

```bash
SONGSIM_APP_MODE=public_readonly
SONGSIM_PUBLIC_HTTP_URL=https://your-public-api-url
SONGSIM_PUBLIC_MCP_URL=https://your-public-mcp-url/mcp
SONGSIM_PUBLIC_MCP_AUTH_MODE=anonymous
```

공개 MCP를 OAuth로 보호하려면:

```bash
SONGSIM_PUBLIC_MCP_AUTH_MODE=oauth
SONGSIM_MCP_OAUTH_ENABLED=true
SONGSIM_MCP_OAUTH_ISSUER=https://your-tenant.us.auth0.com/
SONGSIM_MCP_OAUTH_AUDIENCE=https://your-public-mcp-url/mcp
SONGSIM_MCP_OAUTH_SCOPES=songsim.read
```

### 3. Run Local Postgres

```bash
docker compose up -d postgres
```

기본값은 로컬 Postgres/PostGIS(`127.0.0.1:55432`)를 가리킵니다.

### 4. Seed or Sync

데모 데이터:

```bash
uv run songsim-seed-demo --force
```

공식 데이터:

```bash
uv run songsim-sync --year <current-year> --semester <1-or-2> --notice-pages 1
```

앱 시작 시 공식 데이터를 자동 동기화하려면:

```bash
SONGSIM_SYNC_OFFICIAL_ON_START=true
SONGSIM_OFFICIAL_COURSE_YEAR=<current-year>
SONGSIM_OFFICIAL_COURSE_SEMESTER=<1-or-2>
```

처음 DB만 만들고 싶으면:

```bash
.venv/bin/python -c "from songsim_campus.db import init_db; init_db()"
```

### 5. Run HTTP API

```bash
uv run songsim-api
```

- docs: `http://127.0.0.1:8000/docs`
- shared GPT schema v2: `http://127.0.0.1:8000/gpt-actions-openapi-v2.json`
- legacy schema v1: `http://127.0.0.1:8000/gpt-actions-openapi.json`

### 6. Run MCP Server

stdio:

```bash
uv run songsim-mcp --transport stdio
```

streamable HTTP:

```bash
uv run songsim-mcp --transport streamable-http
```

공개 MCP에서 학생용으로 먼저 보면 좋은 resource:

- `songsim://usage-guide`
- `songsim://academic-calendar`
- `songsim://registration-guide`
- `songsim://certificate-guide`
- `songsim://scholarship-guide`
- `songsim://wifi-guide`
- `songsim://transport-guide`

필요하면 `songsim://place-categories`, `songsim://notice-categories`, `songsim://class-periods` 같은 metadata helper resource도 추가로 쓸 수 있습니다.

## Example HTTP Companion Calls

```bash
curl 'http://127.0.0.1:8000/places?query=학생회관%20어디야?'
curl 'http://127.0.0.1:8000/places?query=우리은행%20전화번호%20알려줘'
curl 'http://127.0.0.1:8000/courses?query=객체지향&year=2026&semester=1'
curl 'http://127.0.0.1:8000/academic-calendar?academic_year=2026&month=3'
curl 'http://127.0.0.1:8000/academic-status-guides?status=dropout'
curl 'http://127.0.0.1:8000/registration-guides?topic=payment_and_return&limit=2'
curl 'http://127.0.0.1:8000/notices?category=academic&limit=3'
curl 'http://127.0.0.1:8000/dining-menus?query=학생식당'
curl 'http://127.0.0.1:8000/restaurants/nearby?origin=central-library&budget_max=10000&walk_minutes=15'
curl 'http://127.0.0.1:8000/library-seats'
curl 'http://127.0.0.1:8000/classrooms/empty?building=%EB%8B%88%EC%BD%9C%EC%8A%A4%EA%B4%80&at=2026-03-16T10:15:00%2B09:00'
curl 'http://127.0.0.1:8000/transport?mode=subway'
curl 'http://127.0.0.1:8000/wifi-guides'
```

식당 조회에서 `budget_max`를 주면 가격 정보가 확인된 후보만 남고, 가격 정보가 없는 후보는 제외됩니다.

## Out Of Scope For The Public Student Surface

아래는 기본 공개 surface의 중심은 아닙니다.

- profile 개인화
- 시간표 저장
- 관심사 기반 추천
- `/admin/*`
- `/readyz`
- observability
- 내부 automation
- `/gpt/*` 및 GPT Actions packaging layer

## Local Full Mode

로컬 full 모드에서는 공개 student-facing read-only surface 외에 운영용 기능도 함께 씁니다.

- profile
- admin
- sync
- observability
- automation

## Docs

- [Connect ChatGPT](docs/connect-chatgpt.md)
- [Connect Codex](docs/connect-codex.md)
- [Connect Claude](docs/connect-claude.md)
- [Source Registry](docs/source_registry.md)
- [Render Deploy Guide](docs/deploy-render.md)
- [Public MCP Release Pack (50)](docs/qa/public-mcp-release-pack-50.md)
- [Public API Live Validation Baseline](docs/qa/public-api-live-validation-1000.md)
- [Public Synthetic Smoke Runbook](docs/qa/public-synthetic-smoke.md)

## Project Structure

```text
songsim-campus-mcp/
├─ data/
├─ docs/
├─ src/songsim_campus/
├─ tests/
├─ .env.example
├─ docker-compose.yml
├─ pyproject.toml
├─ render.yaml
└─ README.md
```

## Summary

Songsim Campus MCP는 **학생 질문을 공식 데이터 기반 답변으로 연결하는 campus-specific MCP product**입니다.

핵심은 세 가지입니다.

1. 학생이 실제로 묻는 질문을 다룬다
2. 공식 source에 없는 값은 지어내지 않는다
3. 공개 QA와 source policy를 함께 공개한다
