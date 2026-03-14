# Songsim Campus Starter Kit

가톨릭대학교 성심교정 전용 생활 도우미를 만들기 위한 **Codex 친화형 스타터킷**입니다.

이 스타터킷은 처음부터 복잡한 인프라를 얹지 않고, 아래 흐름을 가장 빠르게 검증하는 데 초점을 둡니다.

- 교내 시설/건물 검색
- 강의 시간표 검색
- 교시 ↔ 실제 시간 변환
- 주변 맛집 추천
- 공지 조회
- HTTP API + MCP 도구 동시 제공

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
- 그래서 웹앱, Claude Desktop, ChatGPT, Codex 어디서든 재사용이 쉽습니다.

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

처음 DB만 만들고 싶으면:

```bash
.venv/bin/python -c "from songsim_campus.db import init_db; init_db()"
```

### 4. HTTP API 실행

```bash
uv run songsim-api
```

문서: `http://127.0.0.1:8000/docs`

### 5. MCP 서버 실행

stdio:

```bash
uv run songsim-mcp --transport stdio
```

streamable HTTP:

```bash
uv run songsim-mcp --transport streamable-http
```

## API 예시

```bash
curl 'http://127.0.0.1:8000/places?query=도서관'
curl 'http://127.0.0.1:8000/courses?query=객체지향&year=2026&semester=1'
curl 'http://127.0.0.1:8000/restaurants/nearby?origin=central-library&budget_max=10000&walk_minutes=15'
curl 'http://127.0.0.1:8000/restaurants/nearby?origin=central-library&open_now=true&at=2026-03-15T11:00:00%2B09:00'
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
```

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
5. 관심 카테고리/키워드 + 프로필 속성 기반 공지 필터링
6. 학과/학년 기반 과목 추천
7. 다음 수업까지 남은 시간 기반 식사 추천

## 추천 확장 순서

1. 공지/과목 개인화 품질 개선
2. 식당 영업 데이터 소스 확보
3. 운영 자동화

## 주의

- `data/`는 **데모용**입니다. 실제 운영 데이터로 착각하면 안 됩니다.
- 저장소는 이제 `SONGSIM_DATABASE_URL`만 지원합니다. 예전 `SONGSIM_DATABASE_PATH`가 남아 있으면 앱이 시작하지 않습니다.
- 강의실/운영시간은 학교 공지에 따라 바뀔 수 있으니 `last_synced_at`를 항상 노출하세요.
- 맛집 추천은 LLM 자유생성보다 **거리, 예산, 영업 여부** 같은 하드 필터를 먼저 태우는 쪽이 안전합니다.
- Kakao 식당 결과는 lazy cache로 재사용되므로 같은 조건의 재조회에서는 `source_tag`가 `kakao_local_cache`로 보일 수 있습니다.
- 식당 추천의 이동시간은 캠퍼스 내부 구간만 정적 경로망으로 보정하고, 캠퍼스 밖 구간은 좌표 기반 추정을 유지합니다.
- 외부 구간의 후보 식당 조회와 거리 계산은 PostGIS를 사용합니다.
- `/admin/sync`는 `SONGSIM_ADMIN_ENABLED=true`일 때만 열리고, loopback 클라이언트에서만 접근됩니다.
- `/readyz`는 DB와 핵심 테이블 접근성을 점검하고, `/admin/observability`와 `/admin/observability.json`은 최근 sync/cache 상태를 로컬에서만 보여줍니다.
