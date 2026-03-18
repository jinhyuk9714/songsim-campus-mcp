# Songsim Campus MCP

가톨릭대학교 성심교정 전용 데이터를 **원격 MCP 서버 + HTTP API**로 제공하는 프로젝트입니다.

공개 배포에서는 **read-only Remote MCP**가 학생용 기본 입구이고, HTTP API는 같은 데이터를 직접 확인하거나 연동할 때 쓰는 얇은 companion layer입니다. 로컬 full 모드에서는 profile, admin, sync, observability, automation 같은 운영 기능도 함께 사용할 수 있습니다.

공개 MCP는 기본적으로 익명 read-only로 열려 있고, 운영자가 필요하면 OAuth 보호 모드로 바꿀 수 있습니다. 공개 HTTP API는 계속 익명 read-only입니다.

## 학생용 한눈에 보기

- **Primary surface:** Remote MCP
  - ChatGPT, Claude, Codex 같은 MCP 클라이언트에서 바로 연결해서 사용
- **Companion surface:** HTTP API
  - `/places`, `/courses`, `/academic-calendar`처럼 같은 데이터를 직접 확인하거나 외부 앱에서 연동할 때 사용
- **학생이 실제로 묻는 질문 중심**
  - 위치
  - 전화번호
  - 운영시간
  - 학사일정
  - 등록/증명서/휴학/복학/자퇴/장학 안내
  - 공지
  - 학식/근처 식당
  - 도서관 좌석 / 빈 강의실
  - 교통 / WIFI

## 이 MCP가 답할 수 있는 질문

| 영역 | 어떤 질문을 받나 | 대표 질문 | 대표 MCP resource/tool | 대표 HTTP companion |
| --- | --- | --- | --- | --- |
| 장소 / 시설 | 건물, 별칭, 편의시설 위치와 시설 전화번호/운영시간 | `학생회관 어디야?` `복사실이 어디야?` `우리은행 전화번호 알려줘` `트러스트짐 운영시간 알려줘` | `songsim://usage-guide` `tool_search_places` `tool_get_place` | `/places` `/places/{identifier}` |
| 과목 / 교시 / 학사일정 | 개설과목 검색, 교시 시간, 월별/키워드별 학사일정 | `7교시가 몇 시야?` `2026년 1학기 객체지향 과목 찾아줘` `2026학년도 3월 학사일정 보여줘` | `tool_search_courses` `tool_get_class_periods` `tool_list_academic_calendar` | `/courses` `/periods` `/academic-calendar` |
| 학사지원 가이드 | 등록금 고지서/납부/반환, 증명발급, 휴학, 복학/자퇴/재입학, 학사지원 업무안내, 장학제도 | `등록금 고지서 조회 방법 알려줘` `등록금 반환 기준 알려줘` `재학증명서 발급 방법 알려줘` `자퇴 절차 알려줘` | `tool_list_registration_guides` `tool_list_certificate_guides` `tool_list_leave_of_absence_guides` `tool_list_academic_status_guides` `tool_list_academic_support_guides` `tool_list_scholarship_guides` | `/registration-guides` `/certificate-guides` `/leave-of-absence-guides` `/academic-status-guides` `/academic-support-guides` `/scholarship-guides` |
| 공지 | 최신 공지 목록, 카테고리별 공지, 카테고리 정규화 | `최신 학사 공지 2개 보여줘` `최신 취업 공지 3개 보여줘` `employment랑 career 차이 알려줘` | `tool_list_latest_notices` `songsim://notice-categories` | `/notices` `/notice-categories` |
| 식당 / 학식 | 교내 공식 학식 메뉴, 근처 식당 추천, 브랜드 검색 | `학생식당 메뉴 보여줘` `카페 보나 이번 주 메뉴 알려줘` `중앙도서관 근처 한식집 찾아줘` `매머드커피 어디 있어?` | `tool_search_dining_menus` `tool_find_nearby_restaurants` `tool_search_restaurants` | `/dining-menus` `/restaurants/nearby` `/restaurants/search` |
| 도서관 / 빈 강의실 | 중앙도서관 열람실 좌석, 현재 빈 강의실 | `중앙도서관 열람실 남은 좌석 알려줘` `제1자유열람실 남은 좌석 알려줘` `K관 지금 빈 강의실 있어?` | `tool_get_library_seat_status` `tool_list_estimated_empty_classrooms` | `/library-seats` `/classrooms/empty` |
| 교통 / WIFI | 지하철·버스 접근 안내, 건물별 WIFI 안내 | `성심교정 지하철 오는 길 알려줘` `니콜스관 WIFI 안내 알려줘` | `tool_list_transport_guides` `tool_list_wifi_guides` `songsim://transport-guide` `songsim://wifi-guide` | `/transport` `/wifi-guides` |

## 질문 패턴 예시

- **위치**
  - `학생회관 어디야?`
  - `K관 어디야?`
  - `복사실이 어디야?`
- **전화번호**
  - `우리은행 전화번호 알려줘`
  - `카페드림 전화번호 알려줘`
- **운영시간**
  - `CU 운영시간 알려줘`
  - `트러스트짐 운영시간 알려줘`
- **일정**
  - `2026학년도 3월 학사일정 보여줘`
  - `추가 등록기간 일정 알려줘`
- **안내 / 절차**
  - `등록금 납부 방법 알려줘`
  - `등록금 반환 기준 알려줘`
  - `초과학기생 등록은 어떻게 해?`
  - `재학증명서 발급 방법 알려줘`
  - `휴학 신청 방법 알려줘`
  - `재입학 지원자격 알려줘`
  - `장학금 신청 안내 알려줘`
- **최신 목록**
  - `최신 학사 공지 2개 보여줘`
  - `장학 공지 최신순으로 3개 보여줘`
- **근처 추천**
  - `중앙도서관 근처 한식집 찾아줘`
  - `중앙도서관에서 10분 안쪽에 1만원 이하 식당 보여줘`

## 현재 공개 범위 밖

- profile 개인화, 시간표 저장, 관심사 기반 추천은 **로컬 full 모드** 영역입니다.
- `/admin/*`, `/readyz`, observability, 내부 automation은 **운영용 표면**입니다.
- `/gpt/*`, GPT Actions schema는 **선택적 포장층**이며, 학생용 기본 입구는 아닙니다.
- 학교 공식 source에 없는 값은 만들어내지 않습니다. 없거나 불확실하면 `null` 또는 빈 결과를 반환합니다.
- 일부 동적 도메인은 best-effort 또는 fallback이 있습니다.
  - 도서관 좌석: live fetch + stale fallback
  - 빈 강의실: realtime 우선, 없으면 시간표 기준 예상 공실

## 관련 문서

- [Codex 연결 가이드](docs/connect-codex.md)
- [ChatGPT 연결 가이드](docs/connect-chatgpt.md)
- [Claude 연결 가이드](docs/connect-claude.md)
- [Source Registry](docs/source_registry.md)
- [Render 배포 가이드](docs/deploy-render.md)
- [공개 MCP 릴리즈팩 50](docs/qa/public-mcp-release-pack-50.md)
- [공개 API 1000문장 라이브 검증](docs/qa/public-api-live-validation-1000.md)

README는 capability map과 빠른 입구만 설명합니다. 클라이언트별 연결 절차와 더 긴 prompt 예시는 연결 가이드 문서에서 다룹니다.

## 프로젝트 구조

```text
songsim-campus-mcp/
├─ AGENTS.md
├─ .codex/config.toml
├─ data/
│  ├─ sample_places.json
│  ├─ sample_courses.json
│  ├─ sample_restaurants.json
│  └─ sample_notices.json
├─ docs/
│  ├─ source_registry.md
│  ├─ roadmap.md
│  └─ codex_tasks.md
├─ src/songsim_campus/
│  ├─ api.py
│  ├─ db.py
│  ├─ ingest/
│  ├─ mcp_server.py
│  ├─ repo.py
│  ├─ schema.sql
│  ├─ schemas.py
│  ├─ seed.py
│  ├─ services.py
│  └─ settings.py
└─ tests/
```

## 빠른 시작

### 1. 의존성 설치

`uv` 기준:

```bash
uv sync --extra dev --extra mcp --extra scrape
```

`pip` 기준:

```bash
pip install -e '.[dev,mcp,scrape]'
```

### 2. 환경 변수

```bash
cp .env.example .env
```

공개 read-only 배포를 만들려면 아래 값을 사용합니다.

```bash
SONGSIM_APP_MODE=public_readonly
SONGSIM_PUBLIC_HTTP_URL=https://your-public-api-url
SONGSIM_PUBLIC_MCP_URL=https://your-public-mcp-url/mcp
SONGSIM_PUBLIC_MCP_AUTH_MODE=anonymous
```

OAuth로 보호된 공개 MCP가 필요하면 아래 값을 추가하세요.

```bash
SONGSIM_PUBLIC_MCP_AUTH_MODE=oauth
SONGSIM_MCP_OAUTH_ENABLED=true
SONGSIM_MCP_OAUTH_ISSUER=https://your-tenant.us.auth0.com/
SONGSIM_MCP_OAUTH_AUDIENCE=https://your-public-mcp-url/mcp
SONGSIM_MCP_OAUTH_SCOPES=songsim.read
```

### 3. 로컬 DB 실행

```bash
docker compose up -d postgres
```

기본값은 로컬 Postgres/PostGIS(`127.0.0.1:55432`)를 가리킵니다.

### 4. 데모 / 공식 데이터 적재

데모 데이터:

```bash
uv run songsim-seed-demo --force
```

공식 데이터:

```bash
uv run songsim-sync --year <current-year> --semester <1-or-2> --notice-pages 1
```

앱 시작 시 공식 데이터를 자동 동기화하려면 대상 학기를 명시해서 넣는 편이 안전합니다.

```bash
SONGSIM_SYNC_OFFICIAL_ON_START=true
SONGSIM_OFFICIAL_COURSE_YEAR=<current-year>
SONGSIM_OFFICIAL_COURSE_SEMESTER=<1-or-2>
```

처음 DB만 만들고 싶으면:

```bash
.venv/bin/python -c "from songsim_campus.db import init_db; init_db()"
```

### 5. HTTP API 실행

```bash
uv run songsim-api
```

- 문서: `http://127.0.0.1:8000/docs`
- 선택적 Shared GPT 포장용 v2 schema: `http://127.0.0.1:8000/gpt-actions-openapi-v2.json`
- 기존 Actions schema(v1, 회귀용): `http://127.0.0.1:8000/gpt-actions-openapi.json`

### 6. MCP 서버 실행

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

## 학생용 HTTP companion 예시

```bash
curl 'http://127.0.0.1:8000/places?query=학생회관%20어디야?'
curl 'http://127.0.0.1:8000/places?query=우리은행%20전화번호%20알려줘'
curl 'http://127.0.0.1:8000/courses?query=객체지향&year=2026&semester=1'
curl 'http://127.0.0.1:8000/academic-calendar?academic_year=2026&month=3'
curl 'http://127.0.0.1:8000/academic-status-guides?status=dropout'
curl 'http://127.0.0.1:8000/notices?category=academic&limit=3'
curl 'http://127.0.0.1:8000/dining-menus?query=학생식당'
curl 'http://127.0.0.1:8000/restaurants/nearby?origin=central-library&budget_max=10000&walk_minutes=15'
curl 'http://127.0.0.1:8000/library-seats'
curl 'http://127.0.0.1:8000/classrooms/empty?building=%EB%8B%88%EC%BD%9C%EC%8A%A4%EA%B4%80&at=2026-03-16T10:15:00%2B09:00'
curl 'http://127.0.0.1:8000/transport?mode=subway'
curl 'http://127.0.0.1:8000/wifi-guides'
```

식당 조회에서 `budget_max`를 주면 가격 정보가 확인된 후보만 남습니다. 가격 정보가 없는 후보는 제외됩니다.

## 로컬 full / 운영 기능

로컬 full 모드에서는 아래 기능이 추가됩니다.

- profile 생성과 시간표 저장
- 관심 카테고리/키워드 기반 공지 relevance 정렬
- 프로필 기반 과목/식사 추천
- `/admin/sync`, `/admin/observability*`, `/readyz`
- 내부 automation loop

예시:

```bash
curl 'http://127.0.0.1:8000/readyz'
curl -X POST 'http://127.0.0.1:8000/profiles' -H 'content-type: application/json' -d '{"display_name":"성심학생"}'
curl -X PUT 'http://127.0.0.1:8000/profiles/{profile_id}/timetable' -H 'content-type: application/json' -d '[{"year":2026,"semester":1,"code":"07487","section":"01"}]'
curl -X PUT 'http://127.0.0.1:8000/profiles/{profile_id}/notice-preferences' -H 'content-type: application/json' -d '{"categories":["academic"],"keywords":["장학"]}'
curl 'http://127.0.0.1:8000/profiles/{profile_id}/meal-recommendations?origin=central-library&year=2026&semester=1'
```

로컬 운영용 동기화 대시보드:

```bash
SONGSIM_ADMIN_ENABLED=true uv run songsim-api
```

- 브라우저에서 `http://127.0.0.1:8000/admin/sync`
- 관측성 JSON은 `http://127.0.0.1:8000/admin/observability.json`

## 현재 개인화 범위

1. 로컬 프로필 생성
2. 학과 / 학년 / 입학유형 저장
3. 관심사 태그 저장
4. 공식 과목 키 기준 시간표 저장
5. 관심 카테고리 / 키워드 + 프로필 속성 기반 공지 relevance 정렬
6. 학과 / 학년 기반 과목 추천과 code별 대표 분반 정리
7. 다음 수업까지 남은 시간 기반 식사 추천

## 주의

- `data/`는 **데모용**입니다. 실제 운영 데이터로 착각하면 안 됩니다.
- 저장소는 `SONGSIM_DATABASE_URL`만 지원합니다. 예전 `SONGSIM_DATABASE_PATH`가 남아 있으면 앱이 시작하지 않습니다.
- 강의실/운영시간은 학교 공지에 따라 바뀔 수 있으니 `last_synced_at`를 항상 노출하세요.
- 맛집 추천은 LLM 자유생성보다 **거리, 예산, 영업 여부** 같은 하드 필터를 먼저 태우는 쪽이 안전합니다.
- Kakao 식당 결과는 lazy cache로 재사용되므로 같은 조건의 재조회에서는 `source_tag`가 `kakao_local_cache`로 보일 수 있습니다.
- `K관`, `정문` 같은 exact short-query는 canonical campus place로 바로 수렴하도록 우선 처리합니다.
- 교내 식당은 학교 공식 운영시간을 우선 사용하고, 교외 Kakao 식당은 detail 페이지 기반 운영시간을 best-effort로 붙입니다.
- 식당 추천의 이동시간은 캠퍼스 내부 구간만 정적 경로망으로 보정하고, 캠퍼스 밖 구간은 좌표 기반 추정을 유지합니다.
- 외부 구간의 후보 식당 조회와 거리 계산은 PostGIS를 사용합니다.
- `/admin/sync`는 `SONGSIM_ADMIN_ENABLED=true`일 때만 열리고, loopback 클라이언트에서만 접근됩니다.
- `/readyz`는 DB와 공개 core snapshot(`places`, `notices`, `academic_calendar`, 주요 guide/transport`) 접근성을 점검합니다. `campus_facilities`, `campus_dining_menus`는 best-effort, `courses`는 운영 시점 학기 지정 전까지 optional로 봅니다.
- `/admin/observability`와 `/admin/observability.json`은 최근 sync/cache 상태를 로컬에서만 보여줍니다.
- `SONGSIM_AUTOMATION_ENABLED=true`이면 앱 내부 스케줄러가 advisory lock 기반으로 `snapshot`, `library_seat_prewarm`, `cache_cleanup` job을 자동 실행합니다.
- `SONGSIM_APP_MODE=public_readonly`이면 공개 read-only surface만 노출하고 `/profiles/*`, `/admin/*`는 숨겨집니다.
