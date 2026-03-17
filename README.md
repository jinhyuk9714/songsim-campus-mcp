# Songsim Campus MCP

가톨릭대학교 성심교정 전용 데이터를 **원격 MCP 서버 + HTTP API**로 제공하는 프로젝트입니다.

공개 배포에서는 `read-only` 원격 MCP가 핵심 제품 표면으로 동작하고, HTTP API는 그 위에 붙는 얇은 companion layer 역할을 합니다. 로컬 full 모드에서는 admin, sync, observability, 개인화 실험까지 함께 쓸 수 있습니다.

공개 MCP는 기본적으로 익명 read-only로 열려 있고, 필요하면 OAuth 보호 모드로 전환할 수 있습니다. 공개 API는 계속 익명 read-only입니다.

## 공개 사용 방식

- Remote MCP: ChatGPT, Claude, Codex 같은 클라이언트에서 직접 연결
- HTTP API: 장소, 과목, 공지, 식당, 교통 안내 조회
- Shared GPT: ChatGPT GPT Builder에서 GPT 전용 v2 Actions schema로 붙여 `chatgpt.com/g/...` 링크로 공개
- Local full mode: profile, timetable, admin sync, observability, automation 운영

공개 MCP 사용 패턴은 이 순서를 기준으로 보면 됩니다.

1. `songsim://usage-guide` 같은 resource로 공개 surface를 먼저 확인
2. place / course / notice / restaurant / transport prompt로 첫 tool 선택
3. 해당 tool로 실제 조회

강의실 공실은 공식 실시간 source가 있으면 그것을 우선 사용하고, 공개 배포에서 실시간 coverage가 없으면 시간표 기준 예상 공실로 자동 폴백합니다.

## 대표 MCP 테스트 질문

- `성심교정 중앙도서관 위치 알려줘`
- `중도 어디야`
- `트러스트짐 어디야`
- `헬스장 어디야`
- `편의점 어디 있어`
- `ATM 어디 있어`
- `학생회관 어디야`
- `K관 어디야`
- `정문 위치 알려줘`
- `니콜스인데 2026-03-16 오전 10시 15분 기준 비어 있는 강의실 있어?`
- `K관 지금 빈 강의실 있어?`
- `김수환관 지금 비어 있는 강의실 있어?`
- `정문 기준 빈 강의실 보여줘`
- `7교시가 몇 시야`
- `7교시에 시작하는 과목 찾아줘`
- `장학 공지 최신순으로 3개 보여줘`
- `최신 취업 공지 3개 보여줘`
- `매머드커피 어디 있어?`
- `이디야 있나?`
- `스타벅스 있어?`
- `커피빈 있어?`
- `중앙도서관 근처 한식집 찾아줘`
- `중앙도서관에서 10분 안쪽에 1만원 이하 식당 보여줘`
- `성심교정 지하철 오는 길 알려줘`

식당 조회에서 `budget_max`를 주면 가격 정보가 확인된 후보만 남깁니다. 가격 정보가 없는 후보는 신뢰도 때문에 제외합니다.

전체 검증 자산은 `docs/qa/` 아래에서 운영합니다. 공개 문서에는 대표 10문장만 남기고, 전체 코퍼스와 릴리즈팩, 라이브 판정표는 별도 QA 문서로 분리합니다.

## 공개 테스트 배포 기준

- API URL 하나
- MCP URL 하나
- Render free web service 2개
- Supabase free Postgres 1개

관련 문서:

- [Render 배포 가이드](/Users/sungjh/Projects/songsim-campus-mcp/docs/deploy-render.md)
- [ChatGPT 연결 가이드](/Users/sungjh/Projects/songsim-campus-mcp/docs/connect-chatgpt.md)
- [Claude 연결 가이드](/Users/sungjh/Projects/songsim-campus-mcp/docs/connect-claude.md)
- [Codex 연결 가이드](/Users/sungjh/Projects/songsim-campus-mcp/docs/connect-codex.md)
- [공개 MCP 500문장 코퍼스](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-corpus-500.md)
- [공개 MCP 릴리즈팩 50](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-release-pack-50.md)
- [공개 MCP 라이브 판정표 50](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-live-validation-50.md)
- [공개 MCP 라이브 판정 요약](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-live-validation-summary.md)

이 스타터킷은 처음부터 복잡한 인프라를 얹지 않고, 아래 흐름을 가장 빠르게 검증하는 데 초점을 둡니다.

- 원격 MCP로 검증 가능한 학교 데이터 조회
- 교내 시설/건물 검색
- 생활 시설명으로 관련 건물 후보 검색
- 강의 시간표 검색
- 교시 ↔ 실제 시간 변환
- 주변 맛집 추천
- 공지 조회
- HTTP API와 GPT Actions는 같은 데이터를 얇게 재노출

## 왜 이 스택인가

### 1) Python 3.12 + FastAPI
- 데이터 수집, 파싱, 검색, API, MCP를 한 언어로 끝낼 수 있습니다.
- Codex가 구조를 이해하고 수정하기 쉽습니다.
- 크롤러/스크립트/배치 작업까지 같은 저장소에서 관리하기 좋습니다.

### 2) PostgreSQL + PostGIS
- 공식 데이터, 개인화, 캐시, 운영 이력이 한 저장소 안에서 함께 움직이기 시작한 시점부터는 Postgres가 더 안전합니다.
- 식당 거리 후보 조회와 좌표 기반 질의는 PostGIS가 맡고, 캠퍼스 내부 경로망 보정은 서비스 로직이 계속 담당합니다.
- 로컬도 `docker compose` 한 번이면 같은 구조로 맞출 수 있어 운영과 개발 차이가 줄어듭니다.

### 3) 공식 MCP Python SDK(FastMCP) 연결 구조
- API가 먼저 있고, MCP는 얇은 어댑터로 두었습니다.
- 로직은 `services.py`, I/O는 `api.py`와 `mcp_server.py`에서 담당합니다.
- 그래서 ChatGPT, Codex, Claude 같은 MCP 클라이언트에서 먼저 쓰고, 필요하면 HTTP API와 GPT Actions로 같은 데이터를 재사용하기 쉽습니다.

## 프로젝트 구조

```text
songsim-campus-starterkit/
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

로컬 DB를 먼저 올립니다.

```bash
docker compose up -d postgres
```

기본값은 로컬 Postgres/PostGIS(`127.0.0.1:55432`)를 가리킵니다.

### 3. 데모 데이터 적재

```bash
uv run songsim-seed-demo --force
```

공식 데이터를 바로 적재하려면:

```bash
uv run songsim-sync --year 2026 --semester 1 --notice-pages 1
```

앱 시작 시 공식 데이터를 자동 동기화하려면 `.env`에 아래 값을 추가하세요.

```bash
SONGSIM_SYNC_OFFICIAL_ON_START=true
SONGSIM_OFFICIAL_COURSE_YEAR=2026
SONGSIM_OFFICIAL_COURSE_SEMESTER=1
```

앱 내부 자동화를 켜려면 `.env`에 아래 값을 추가하세요.

```bash
SONGSIM_AUTOMATION_ENABLED=true
SONGSIM_AUTOMATION_TICK_SECONDS=60
SONGSIM_AUTOMATION_SNAPSHOT_INTERVAL_MINUTES=360
SONGSIM_AUTOMATION_CACHE_CLEANUP_INTERVAL_MINUTES=720
```

처음 DB만 만들고 싶으면:

```bash
.venv/bin/python -c "from songsim_campus.db import init_db; init_db()"
```

### 4. HTTP API 실행

```bash
uv run songsim-api
```

문서: `http://127.0.0.1:8000/docs`
Shared GPT용 v2 schema: `http://127.0.0.1:8000/gpt-actions-openapi-v2.json`
기존 Actions schema(v1): `http://127.0.0.1:8000/gpt-actions-openapi.json`

### 5. MCP 서버 실행

stdio:

```bash
uv run songsim-mcp --transport stdio
```

streamable HTTP:

```bash
uv run songsim-mcp --transport streamable-http
```

공개 MCP에서 기본으로 노출되는 resource:

- `songsim://usage-guide`
- `songsim://source-registry`
- `songsim://transport-guide`
- `songsim://place-categories`
- `songsim://notice-categories`
- `songsim://class-periods`

## API 예시

```bash
curl 'http://127.0.0.1:8000/places?query=도서관'
curl 'http://127.0.0.1:8000/courses?query=객체지향&year=2026&semester=1'
curl 'http://127.0.0.1:8000/notice-categories'
curl 'http://127.0.0.1:8000/periods'
curl 'http://127.0.0.1:8000/library-seats'
curl 'http://127.0.0.1:8000/library-seats?query=%EC%A0%9C1%EC%9E%90%EC%9C%A0%EC%97%B4%EB%9E%8C%EC%8B%A4'
curl 'http://127.0.0.1:8000/gpt/notice-categories'
curl 'http://127.0.0.1:8000/gpt/periods'
curl 'http://127.0.0.1:8000/gpt/library-seats?query=%EC%97%B4%EB%9E%8C%EC%8B%A4%20%EB%82%A8%EC%9D%80%20%EC%A2%8C%EC%84%9D'
curl 'http://127.0.0.1:8000/classrooms/empty?building=%EB%8B%88%EC%BD%9C%EC%8A%A4%EA%B4%80&at=2026-03-16T10:15:00%2B09:00'
curl 'http://127.0.0.1:8000/restaurants/nearby?origin=central-library&budget_max=10000&walk_minutes=15'
curl 'http://127.0.0.1:8000/restaurants/nearby?origin=central-library&open_now=true&at=2026-03-15T11:00:00%2B09:00'
curl 'http://127.0.0.1:8000/restaurants/search?query=%EB%A7%A4%EB%A8%B8%EB%93%9C%EC%BB%A4%ED%94%BC'
curl 'http://127.0.0.1:8000/dining-menus'
curl 'http://127.0.0.1:8000/dining-menus?query=%ED%95%99%EC%83%9D%EC%8B%9D%EB%8B%B9'
curl 'http://127.0.0.1:8000/gpt/dining-menus?query=%EC%B9%B4%ED%8E%98%20%EB%B3%B4%EB%82%98'
curl 'http://127.0.0.1:8000/transport?mode=subway'
curl 'http://127.0.0.1:8000/readyz'
curl -X POST 'http://127.0.0.1:8000/profiles' -H 'content-type: application/json' -d '{"display_name":"성심학생"}'
curl -X PUT 'http://127.0.0.1:8000/profiles/{profile_id}/timetable' -H 'content-type: application/json' -d '[{"year":2026,"semester":1,"code":"07487","section":"01"}]'
curl -X PUT 'http://127.0.0.1:8000/profiles/{profile_id}/notice-preferences' -H 'content-type: application/json' -d '{"categories":["academic"],"keywords":["장학"]}'
curl 'http://127.0.0.1:8000/profiles/{profile_id}/meal-recommendations?origin=central-library&year=2026&semester=1'

# 로컬 운영용 동기화 대시보드
SONGSIM_ADMIN_ENABLED=true uv run songsim-api
# 브라우저에서 http://127.0.0.1:8000/admin/sync 열기
# 관측성 JSON은 http://127.0.0.1:8000/admin/observability.json
# 자동화를 켜면 같은 앱 안에서 snapshot sync + cache cleanup이 주기적으로 실행됨
```

`budget_max`는 엄격 필터입니다. 가격 정보가 없는 식당은 결과에서 제외됩니다.
브랜드 direct search는 `origin`이 없어도 동작하고, 먼저 캠퍼스에 가까운 후보를 찾습니다. 근처에 없으면 더 가까운 외부 지점을 보여줄 수 있습니다. `스타벅스`, `커피빈`, `투썸`, `빽다방`처럼 long-tail 브랜드도 direct search로 먼저 확인합니다.
교내 공식 학식 3곳의 이번 주 메뉴는 `/dining-menus`와 `/gpt/dining-menus`로 조회할 수 있습니다. 현재는 주간 메뉴 텍스트와 원본 PDF 링크를 함께 반환하고, `오늘 메뉴`나 `내일 메뉴`도 이번 주 메뉴 기준으로 안내합니다.
중앙도서관 열람실 좌석은 `/library-seats`와 `/gpt/library-seats`로 best-effort 실시간 조회할 수 있습니다. source가 응답하지 않으면 stale cache 또는 unavailable note로 안전하게 폴백합니다.
공지 카테고리 설명은 `/notice-categories` 또는 `songsim://notice-categories`로 바로 읽을 수 있고, 교시표는 `/periods`, `/gpt/periods`, `songsim://class-periods`로 바로 확인할 수 있습니다. 교시 기반 과목 조회는 `/courses?year=2026&semester=1&period_start=7`처럼 direct filter로도 처리할 수 있습니다.

## 대표 MCP 테스트 질문

- `성심교정 중앙도서관 위치 알려줘`
- `중도 어디야?`
- `K관 어디야?`
- `정문 위치 알려줘`
- `니콜스인데 지금 비어 있는 강의실 있어?`
- `K관 지금 빈 강의실 있어?`
- `김수환관 지금 비어 있는 강의실 있어?`
- `N관 기준으로 오늘 비어 있는 강의실 보여줘`
- `2026년 1학기 객체지향 과목 찾아줘`
- `김가톨 교수 수업 알려줘`
- `최신 학사 공지 2개 보여줘`
- `장학 공지 최신순으로 3개 보여줘`
- `중앙도서관 근처 한식만 찾아줘`
- `학생식당 메뉴 보여줘`
- `카페 보나 이번 주 메뉴 알려줘`
- `중앙도서관 열람실 남은 좌석 알려줘`
- `제1자유열람실 남은 좌석 알려줘`
- `성심교정 지하철 오는 길 알려줘`

## 이미 들어있는 도메인 모델

### Place
- 건물
- 편의시설
- 도서관
- 정문/버스정류장 같은 기준 위치
- `opening_hours`에 도서관/시설 운영시간 병합

### Course
- 학년도 / 학기
- 과목명 / 과목코드 / 교수
- 요일 / 시작교시 / 종료교시
- 강의실 / 원본 시간표 문자열

### Restaurant
- 카테고리
- 가격대
- 좌표
- 태그

### CampusDiningMenu
- 공식 학식 매장명
- 연결된 교내 place
- 이번 주 라벨 / 주간 범위
- 추출 메뉴 텍스트
- 원본 PDF 링크

### Notice
- 제목
- 카테고리
- 게시일
- 요약
- 레이블

### TransportGuide
- 교통수단 모드
- 안내 제목
- 요약
- 단계별 이동 안내
- 원본 링크

### Profile
- 로컬 `profile_id`
- 표시 이름
- 생성 시각 / 수정 시각

### MealRecommendation
- 추천 식당
- 다음 수업
- 다음 수업 건물
- 총 예상 도보 시간
- 추천 불가 사유

### NearbyRestaurant
- 도보 거리 / 예상 도보 시간
- 출발 장소 slug
- `open_now` 영업 상태 (`true`, `false`, `null`)
- 캠퍼스 내부 구간은 정적 경로망으로, 외부 구간은 좌표 거리로 보정한 예상 도보 시간

## 이 스타터킷에서 먼저 해야 할 일

1. `docs/source_registry.md`의 implemented 소스를 현재 운영 구조와 계속 맞춘다.
2. `data/` 데모 의존 없이 공식 동기화만으로도 핵심 조회가 되도록 보강한다.
3. `tests/`에 새 파서 계약 테스트와 service 회귀 테스트를 계속 추가한다.
4. HTTP API 결과를 MCP 도구와 resource에서 그대로 재사용하게 유지한다.
5. 이후 웹 UI가 필요하면 Next.js 같은 프런트만 별도 추가한다.

## 현재 개인화 범위

1. 로컬 프로필 생성
2. 학과/학년/입학유형 저장
3. 관심사 태그 저장
4. 공식 과목 키 기준 시간표 저장
5. 관심 카테고리/키워드 + 프로필 속성 기반 공지 relevance 정렬
6. 학과/학년 기반 과목 추천과 code별 대표 분반 정리
7. 다음 수업까지 남은 시간 기반 식사 추천

## 추천 확장 순서

1. 개인화 품질 고도화
2. 관리자 운영 흐름 보강

## 주의

- `data/`는 **데모용**입니다. 실제 운영 데이터로 착각하면 안 됩니다.
- 저장소는 이제 `SONGSIM_DATABASE_URL`만 지원합니다. 예전 `SONGSIM_DATABASE_PATH`가 남아 있으면 앱이 시작하지 않습니다.
- 강의실/운영시간은 학교 공지에 따라 바뀔 수 있으니 `last_synced_at`를 항상 노출하세요.
- 맛집 추천은 LLM 자유생성보다 **거리, 예산, 영업 여부** 같은 하드 필터를 먼저 태우는 쪽이 안전합니다.
- Kakao 식당 결과는 lazy cache로 재사용되므로 같은 조건의 재조회에서는 `source_tag`가 `kakao_local_cache`로 보일 수 있습니다.
- `K관`, `정문` 같은 exact short-query는 canonical campus place로 바로 수렴하도록 우선 처리합니다.
- 교내 식당은 학교 공식 운영시간을 우선 사용하고, 교외 Kakao 식당은 detail 페이지 기반 운영시간을 best-effort로 붙입니다.
- 식당 추천의 이동시간은 캠퍼스 내부 구간만 정적 경로망으로 보정하고, 캠퍼스 밖 구간은 좌표 기반 추정을 유지합니다.
- 외부 구간의 후보 식당 조회와 거리 계산은 PostGIS를 사용합니다.
- `/admin/sync`는 `SONGSIM_ADMIN_ENABLED=true`일 때만 열리고, loopback 클라이언트에서만 접근됩니다.
- `/readyz`는 DB와 핵심 테이블 접근성을 점검하고, `/admin/observability`와 `/admin/observability.json`은 최근 sync/cache 상태를 로컬에서만 보여줍니다.
- `SONGSIM_AUTOMATION_ENABLED=true`이면 앱 내부 스케줄러가 advisory lock 기반으로 `snapshot`과 `cache_cleanup` job을 자동 실행합니다.
- `SONGSIM_APP_MODE=public_readonly`이면 공개 read-only surface만 노출하고 `/profiles/*`, `/admin/*`는 숨겨집니다.
