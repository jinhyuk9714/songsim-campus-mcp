# Public MCP Live Validation Summary

`Public MCP Release Pack (50)`를 2026-03-16 KST 기준 공개 배포에 대해 실제 실행한 요약본입니다. 이번 게이트는 **public API 우선**으로 돌렸고, `expected_mcp_flow`는 제품 관점의 MCP 기대 흐름으로 해석했습니다. course 10문장은 이번 날짜에 source-backed canary 기준으로 재조정했습니다.

## 집계

- release pack size: 50
- executed: 50 / 50
- current status: completed
- `pass`: 43
- `soft_pass`: 7
- `soft_fail`: 0
- `fail`: 0

## 도메인별 관찰

### place

- `중도`, `학생식당`, `니콜스`, `K관` alias는 live 배포에서 정상 작동했습니다.
- `정문` exact short-query는 이제 `main-gate` 1건만 반환합니다.
- `K관` exact short-query도 이제 `kim-sou-hwan-hall` 1건만 반환합니다.

### course

- 릴리즈 게이트는 현재 공개 source truth에 맞춰 **source-backed canary 10문장**으로 다시 잠갔습니다.
- gate canary는 `자료구조`, `객체지향`, `객체 지향`, `03149`, `전혜경`, `자료구조 교수가 누구야`, `객체지향 과목 2개만`, `자료 구조`, `C0 106`, `7교시 시작 과목`입니다.
- 이 10문장은 현재 모두 `pass`입니다.
- watchlist는 현재도 유지하지만, 상태를 `source-gap`과 `normalized recovery`로 나눠 보고 있습니다.
  - `데이터베이스` / `데이타베이스`: `데이터베이스활용` near match
  - `CSE 420`: `CSE420` direct hit recovered
  - `CSE301`
  - `김가톨`
- `CSE301`과 `김가톨`만 아직도 **source-backed direct hit 미확인** watchlist로 남고, 나머지 3건은 정규화로 회복된 관찰 항목입니다.

### notices

- `employment/career` 정규화와 `취 업` spacing recovery는 정상입니다.
- `latest`, `scholarship`, `employment`, `academic` 흐름이 현재 공개 snapshot에서 모두 재현됩니다.
- `Major Discovery Week` 같은 대표 학사 공지도 `academic`으로 정상 보입니다.
- metadata parity 후에는 `/notice-categories`, `/gpt/notice-categories`로 category enum과 compatibility alias를 직접 읽을 수 있습니다.

### restaurants

- `중도`, `학생식당`, `니콜스`, `정문`, `중앙 도서관` origin alias와 spacing recovery는 정상입니다.
- `K관` origin도 `kim-sou-hwan-hall`로 안정적으로 canonicalize되고, cached nearby 결과가 `10s` 안에 반환됩니다.
- `커피빈`은 extended-radius fallback 이후 nearest branch를 정상 반환합니다.
  - origin이 없으면 `커피빈 부천북부역사거리점`, `커피빈 부천스타필드시티점`이 반환됩니다.
  - `origin=중도`가 있으면 `1482m / 30분`, `3109m / 43분`으로 거리/도보 시간이 채워집니다.
- `budget_max` strict filtering은 기대대로 동작해 가격 근거가 없는 후보를 제거합니다.
- `open_now=true`는 이제 영업중이 확인된 후보만 남기도록 strict filtering으로 고정했습니다.
- representative query인 `학생식당 기준 지금 여는 카페만 3개`는 현재 빈 배열을 반환했고, `open_now=null` item이 섞이지 않았습니다.

### transport

- subway/bus mode baseline은 안정적입니다.
- `역곡역`, `지하철 오느 길` 같은 자연어/typo 케이스는 API-first 실행으로는 간접 검증만 했기 때문에 `soft_pass`로 남겼습니다.

### classrooms

- `니콜스관`, `N관`, `니콜스`는 모두 정상이고, `availability_mode=estimated` + fallback note도 정확합니다.
- `김수환관`은 더 이상 비강의동으로 막히지 않습니다.
- 다만 현재 공개 snapshot에는 `김수환관` room timetable data가 없어 빈 결과 + 안내 note로 끝납니다.

### metadata parity

- `/notice-categories`, `/gpt/notice-categories`가 추가되어 `공지 카테고리 종류`, `employment랑 career 차이` 같은 질문을 direct metadata path로 처리할 수 있습니다.
- `/gpt/periods`가 추가되어 `/periods`와 같은 교시표 truth를 GPT surface에서도 바로 읽을 수 있습니다.
- `/courses`에는 optional `period_start`가 추가되어 `7교시에 시작하는 과목`도 `/courses?year=2026&semester=1&period_start=7` 같은 direct filter로 처리할 수 있습니다.

### out_of_scope

- public read-only 범위 설명은 명확합니다.
- profile, timetable, admin 요청은 모두 거절이 정답이며 usage guide와 문서가 일치합니다.

## 후속 재검증 (2026-03-16 KST)

- `public-api/public-mcp` 재배포와 공개 DB snapshot sync(`songsim-sync --year 2026 --semester 1 --notice-pages 3`) 이후, 대표 URL을 다시 확인했습니다.
- 과목:
  - `/courses?query=자료구조&year=2026&semester=1`은 이제 `자료구조`, `자료구조기초`를 정상 반환합니다.
  - `/courses?query=객체지향&year=2026&semester=1`은 이제 `객체지향패러다임`, `객체지향프로그래밍`, `객체지향프로그래밍설계`를 정상 반환합니다.
  - `/courses?query=03149&year=2026&semester=1`, `/courses?query=전혜경&year=2026&semester=1`, `/courses?query=C0%20106&year=2026&semester=1`도 정상 응답합니다.
  - `/courses?year=2026&semester=1&period_start=7&limit=5`는 `3D애니메이션1`을 포함한 7교시 시작 과목만 직접 반환합니다.
- 다만 `CSE301`과 `김가톨`은 여전히 source-gap watchlist로 남고, `데이터베이스` / `데이타베이스`는 near match, `CSE 420`은 direct hit recovered입니다.
- 공지:
  - `/notices?category=academic&limit=10`과 `/gpt/notices?category=academic&limit=5`는 이제 `academic` 공지를 정상 반환합니다.
  - 대표 사례인 `Major Discovery Week` 공지도 `academic`으로 분류되어, 이전의 generic detail label(`공지`) 회귀는 해소됐습니다.

요약하면:
- `academic notice` 실패는 해결됐고, 현재 release pack에는 hard fail이 없습니다.
- `course gate`는 source-backed canary 기준으로 재조정됐고, 현재 공개 배포에서 재현 가능합니다.
- 남은 course 문제는 릴리즈 fail이 아니라 **source-gap watchlist(`CSE301`, `김가톨`)**와 **normalized recovery(`데이터베이스`, `데이타베이스`, `CSE 420`)**를 분리해서 관리하는 편이 맞습니다.

## 즉시 수정 우선순위

1. course source-gap watchlist 유지
   - `CSE301`, `김가톨`는 source-backed direct hit가 아직 없으므로 gate가 아니라 watchlist로 계속 추적합니다.
   - `데이터베이스` / `데이타베이스`는 near match 관찰 항목, `CSE 420`은 direct hit recovered로 따로 보관합니다.
2. release-pack course watchlist 모니터링
   - gate 밖으로 뺀 source-gap 질의가 실제 source 변화로 회복되는지 주기적으로 다시 확인하면 됩니다.
3. Shared GPT actual UI soft watch
   - 실제 Shared GPT UI에서 `7교시에 시작하는 과목`을 post-rollout으로 다시 확인했습니다.
   - 현재도 `7교시 = 15:00~15:50`는 정확히 설명하지만, `/courses?period_start=7` direct filter를 바로 쓰기보다 학기/연도 외에 학과/전공, 요일까지 더 요구하는 보수적 답변이 나옵니다.
   - public API/MCP capability gap은 아니므로, 제품 fail이 아니라 actual UI behavior watch로만 유지합니다.

## 다음 우선순위

- `course source-gap watchlist 모니터링`이 여전히 1순위입니다.
- `7교시 시작 과목`은 public API/MCP 기준으로는 해소됐고, actual UI 쪽만 soft watch가 남아 있습니다.

## 관련 문서

- [공개 MCP 500문장 코퍼스](public-mcp-corpus-500.md)
- [공개 MCP 릴리즈팩 50](public-mcp-release-pack-50.md)
- [공개 MCP 라이브 판정표 50](public-mcp-live-validation-50.md)
- [기존 20문장 실측 리포트](public-mcp-live-validation-20.md)
- [공개 MCP Course Watchlist](public-mcp-course-watchlist.md)
- [공개 MCP GPT Metadata Spot Check](public-mcp-gpt-metadata-spot-check.md)
- [공개 MCP Shared GPT UI 샘플 점검](public-mcp-shared-gpt-ui-sample-check.md)
