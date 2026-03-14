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

### 2) SQLite 먼저, Postgres는 나중
- 학교 전용 프로젝트의 초기 병목은 DB 성능보다 **데이터 정규화와 소스 신뢰성**입니다.
- SQLite면 로컬에서 바로 시작할 수 있어 Codex 반복 속도가 빠릅니다.
- 실제 사용자 붙고 데이터/동시성이 늘면 Postgres/PostGIS로 올리면 됩니다.

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

기본값은 SQLite를 사용하므로 바로 시작 가능합니다.

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
curl 'http://127.0.0.1:8000/transport?mode=subway'
curl -X POST 'http://127.0.0.1:8000/profiles' -H 'content-type: application/json' -d '{"display_name":"성심학생"}'
curl -X PUT 'http://127.0.0.1:8000/profiles/{profile_id}/timetable' -H 'content-type: application/json' -d '[{"year":2026,"semester":1,"code":"07487","section":"01"}]'
curl -X PUT 'http://127.0.0.1:8000/profiles/{profile_id}/notice-preferences' -H 'content-type: application/json' -d '{"categories":["academic"],"keywords":["장학"]}'
curl 'http://127.0.0.1:8000/profiles/{profile_id}/meal-recommendations?origin=central-library&year=2026&semester=1'
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

## 이 스타터킷에서 먼저 해야 할 일

1. `docs/source_registry.md`의 implemented 소스를 현재 운영 구조와 계속 맞춘다.
2. `data/` 데모 의존 없이 공식 동기화만으로도 핵심 조회가 되도록 보강한다.
3. `tests/`에 새 파서 계약 테스트와 service 회귀 테스트를 계속 추가한다.
4. HTTP API 결과를 MCP 도구와 resource에서 그대로 재사용하게 유지한다.
5. 이후 웹 UI가 필요하면 Next.js 같은 프런트만 별도 추가한다.

## 현재 개인화 범위

1. 로컬 프로필 생성
2. 공식 과목 키 기준 시간표 저장
3. 관심 카테고리/키워드 기반 공지 필터링
4. 다음 수업까지 남은 시간 기반 식사 추천

## 추천 확장 순서

1. 식당 캐시 + 영업 여부 필터
2. 길찾기/이동시간 추정 고도화
3. 관리자 동기화 대시보드
4. 관측성/캐시 계층
5. 학과/학년/관심사 기반 개인화

## 주의

- `data/`는 **데모용**입니다. 실제 운영 데이터로 착각하면 안 됩니다.
- 강의실/운영시간은 학교 공지에 따라 바뀔 수 있으니 `last_synced_at`를 항상 노출하세요.
- 맛집 추천은 LLM 자유생성보다 **거리, 예산, 영업 여부** 같은 하드 필터를 먼저 태우는 쪽이 안전합니다.
