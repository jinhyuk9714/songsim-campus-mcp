# Repository guidance for Codex

## Goal
이 저장소의 목표는 **가톨릭대학교 성심교정 전용 MCP + HTTP API**를 만드는 것입니다.
핵심은 챗봇이 아니라 **검증 가능한 도구 서버**입니다.

## Non-negotiables
- 비즈니스 로직은 `src/songsim_campus/services.py`에 둡니다.
- DB 접근은 `src/songsim_campus/repo.py`에서 처리합니다.
- HTTP 라우트와 MCP 도구는 얇게 유지합니다.
- 외부 공개 데이터를 추가/변경하면 `docs/source_registry.md`를 반드시 갱신합니다.
- 데모 데이터는 `data/`에만 둡니다. 서비스 코드에 하드코딩하지 마세요.
- 학교 데이터가 비어 있거나 불확실하면 만들어내지 말고 `null` 또는 빈 결과를 반환하세요.

## Implementation rules
- 새 기능은 항상 **작게 자른 수직 슬라이스**로 끝내세요.
- 먼저 service 테스트를 추가하고, 필요하면 API 테스트를 추가하세요.
- 크롤러를 만들면 HTML fixture 또는 parser contract test도 같이 추가하세요.
- 검색/추천은 먼저 결정론적 필터와 정렬을 만들고, 나중에 LLM을 붙이세요.
- `source_tag`, `last_synced_at`는 가능하면 보존하세요.

## Commands to run after edits
- `pytest`
- `ruff check .`

## Good first tasks
1. 공식 캠퍼스맵 HTML 파서 추가
2. 개설과목조회 파서 추가
3. Kakao Local 식당 검색 어댑터 추가
4. 공지 카테고리 분류 규칙 추가
5. MCP resource로 source registry 노출 강화
