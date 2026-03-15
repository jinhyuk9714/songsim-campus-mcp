# Public MCP Live Validation Summary

`Public MCP Release Pack (50)`를 2026-03-15 KST 기준 공개 배포에 대해 실제 실행한 요약본입니다. 이번 게이트는 **public API 우선**으로 돌렸고, `expected_mcp_flow`는 제품 관점의 MCP 기대 흐름으로 해석했습니다.

## 집계

- release pack size: 50
- executed: 50 / 50
- current status: completed
- `pass`: 31
- `soft_pass`: 8
- `soft_fail`: 9
- `fail`: 2

## 도메인별 관찰

### place

- `중도`, `학생식당`, `니콜스`, `K관` alias는 live 배포에서 정상 작동했습니다.
- `정문`은 `main-gate`가 1순위로 오지만 `창업보육센터` 노이즈가 여전히 따라옵니다.
- `김수환관` 검색은 첫 결과가 올바르지만 `K관` alias 중복 때문에 기숙사 결과가 함께 붙습니다.

### course

- 가장 약한 도메인입니다. 릴리즈팩의 대표 CS 질의 9건이 모두 빈 결과였습니다.
- 큰 오류라기보다 current public snapshot coverage 부족 문제가 더 커 보입니다.
- `songsim://class-periods`와 `/periods` 자체는 정상입니다.
- 2026-03-15 source truth 재점검 기준으로, 공식 course source 전체 sweep에는
  - `데이터베이스`의 직접 hit는 없고 `데이터베이스활용` 1건만 존재했습니다.
  - `CSE301`, `김가톨`, `데이타베이스`, `CSE 420`는 공식 source raw parse 결과에도 없었습니다.
- 따라서 남은 대표 실패 질의 상당수는 현재 검색 버그보다 **source/snapshot coverage gap** 또는 **테스트 기대치 조정 문제**로 보는 편이 맞습니다.

### notices

- `employment/career` 정규화와 `취 업` spacing recovery는 정상입니다.
- `latest`, `scholarship`, `employment` 흐름도 안정적입니다.
- 다만 `academic` slice는 공식 사이트에 공지가 보이는 시점인데도 현재 공개 snapshot에서 비어 있어 이번 게이트의 유일한 notice 실패가 됐습니다.

### restaurants

- `중도`, `학생식당`, `니콜스`, `정문`, `중앙 도서관` origin alias와 spacing recovery는 정상입니다.
- `budget_max` strict filtering은 기대대로 동작해 가격 근거가 없는 후보를 제거합니다.
- `open_now=true`는 이제 영업중이 확인된 후보만 남기도록 strict filtering으로 고정했습니다. 앞으로 `open_now=true` 응답에 `open_now=null` item이 섞이면 회귀입니다.

### transport

- subway/bus mode baseline은 안정적입니다.
- `역곡역`, `지하철 오느 길` 같은 자연어/typo 케이스는 API-first 실행으로는 간접 검증만 했기 때문에 `soft_pass`로 남겼습니다.

### classrooms

- `니콜스관`, `N관`, `니콜스`는 모두 정상이고, `availability_mode=estimated` + fallback note도 정확합니다.
- `김수환관`은 더 이상 비강의동으로 막히지 않습니다.
- 다만 현재 공개 snapshot에는 `김수환관` room timetable data가 없어 빈 결과 + 안내 note로 끝납니다.

### out_of_scope

- public read-only 범위 설명은 명확합니다.
- profile, timetable, admin 요청은 모두 거절이 정답이며 usage guide와 문서가 일치합니다.

## 후속 재검증 (2026-03-15 KST)

- `public-api/public-mcp` 재배포와 공개 DB snapshot sync(`songsim-sync --year 2026 --semester 1 --notice-pages 3`) 이후, 대표 URL 3개를 다시 확인했습니다.
- 과목:
  - `/courses?query=자료구조&year=2026&semester=1`은 이제 `자료구조`, `자료구조기초`를 정상 반환합니다.
  - `/courses?query=객체지향&year=2026&semester=1`은 이제 `객체지향패러다임`, `객체지향프로그래밍`, `객체지향프로그래밍설계`를 정상 반환합니다.
  - 다만 `데이터베이스`, `CSE301`, `김가톨`, `데이타베이스`, `CSE 420`처럼 릴리즈팩의 일부 대표 질의는 여전히 빈 결과거나 근사 결과만 보여 course snapshot/운영 경로 이슈가 완전히 해소된 것은 아닙니다.
- 공지:
  - `/notices?category=academic&limit=10`과 `/gpt/notices?category=academic&limit=5`는 이제 `academic` 공지를 정상 반환합니다.
  - 대표 사례인 `Major Discovery Week` 공지도 `academic`으로 분류되어, 이전의 generic detail label(`공지`) 회귀는 해소됐습니다.

요약하면:
- `academic notice` 실패는 해결됐습니다.
- `course coverage`는 부분 개선됐고, 대표 과목명(`자료구조`, `객체지향`) 기준으로는 합격 수준까지 올라왔습니다.
- 남은 course 문제는 특정 코드/교수명/typo 질의의 **source coverage gap**과 **운영 경로 mismatch 가능성**을 분리해서 보는 편이 맞습니다.

## 즉시 수정 우선순위

1. course source coverage / 운영 경로 조사
   - 남은 대표 질의 중 상당수는 공식 source 자체에 row가 없어서, search bug와 source gap을 분리해서 봐야 합니다.
2. restaurant `open_now` spot revalidation
   - strict filtering은 코드/테스트 기준으로 잠겼고, 공개 배포에서 representative query를 다시 확인하면 됩니다.
3. short query ranking polish
   - `정문`의 2차 노이즈와 `K관` alias 중복을 조금 더 줄일 필요가 있습니다.
4. MCP resource/prompt spot check
   - 이번 게이트는 API-first라 `songsim://notice-categories`, 자연어 transport/typo recovery를 간접 검증만 했습니다.
5. release-pack course expectations 재조정
   - `데이터베이스`, `CSE301`, `김가톨`, `데이타베이스`, `CSE 420`는 source truth와 릴리즈 기대를 다시 맞출 필요가 있습니다.

## 다음 우선순위

- `restaurant open_now representative recheck -> short query ranking polish -> release-pack course expectations 재조정` 순서가 가장 효과적입니다.
- 그다음에 Shared GPT 핵심 10~15문장 샘플 검증으로 넘어가면 됩니다.

## 관련 문서

- [공개 MCP 500문장 코퍼스](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-corpus-500.md)
- [공개 MCP 릴리즈팩 50](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-release-pack-50.md)
- [공개 MCP 라이브 판정표 50](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-live-validation-50.md)
- [기존 20문장 실측 리포트](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-live-validation-20.md)
