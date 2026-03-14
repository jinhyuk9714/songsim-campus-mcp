# Public MCP Live Validation Summary

2026-03-15 KST 기준으로 배포된 공개 surface를 `균형형 20문장`으로 점검한 요약입니다.

## 총평

- pass: 10
- soft_pass: 3
- soft_fail: 2
- fail: 5

공식 캠퍼스맵, 공식 공지 페이지, 공식 교통 안내와 맞닿는 `장소/교통/장학 공지`는 전반적으로 안정적입니다. 반면 `alias 해석`, `공지 taxonomy`, `식당 가격/출발지 제약`, `강의실 building 분류`는 live 배포에서 여전히 눈에 띄는 차이가 있습니다.

## 도메인별 요약

### 장소

- `중앙도서관`, `학생식당 있는 건물`, `니콜스관`은 공식 캠퍼스맵과 잘 맞았습니다.
- `정문`은 첫 결과는 정확했지만 `창업보육센터`가 같이 섞여 soft pass로 남았습니다.
- `중도`는 공식값과 직접 모순되지는 않지만, 실제 학생 alias를 못 받아 usability gap이 보였습니다.

### 빈 강의실

- `니콜스관`, `N관` 기준 공실 조회는 `availability_mode=estimated`와 fallback note를 정확히 노출했습니다.
- `정문`은 강의실 건물이 아니므로 거절이 정상입니다.
- `니콜스` alias는 아직 classroom resolver에 붙지 않았고, `김수환관`은 공식 설명에 강의실이 있는데도 비강의동으로 막혔습니다.

### 공지

- 최신 공지 최신순과 장학 공지 필터는 잘 동작했습니다.
- 다만 latest payload에 `category=place` 같은 비자연스러운 분류가 남아 있고, `employment` filter는 실제 `career/취창업` 성격 공지를 못 잡았습니다.

### 주변 식당

- `중앙도서관`처럼 정식 origin을 넣으면 nearby 추천은 동작합니다.
- `중도`, `학생식당` 같은 origin alias는 live 배포에서 아직 풀리지 않습니다.
- `budget_max` 제약은 결과 payload의 가격 정보가 대부분 `null`이라 신뢰도가 낮습니다.

### 교통

- 지하철과 버스는 공식 안내 페이지와 비교했을 때 큰 차이가 보이지 않았습니다.
- 현재 공개 surface에서 가장 안정적인 도메인 중 하나입니다.

## 즉시 수정이 필요한 상위 이슈

1. place/classroom/restaurant 사이 alias coverage가 일관되지 않습니다.
   - `중도`, `니콜스`, `학생식당`이 대표 사례입니다.
2. `김수환관`이 classroom lookup에서 비강의동으로 잘못 분류됩니다.
   - 공식 캠퍼스맵 설명에는 강의실이 포함됩니다.
3. notice taxonomy normalization이 아직 거칩니다.
   - latest notice의 `place` category, `employment` vs `career` mismatch가 대표적입니다.
4. restaurant budget filtering은 price coverage가 부족해 결과 신뢰도가 떨어집니다.
   - `budget_max=10000`인데 price fields가 `null`인 item이 그대로 남습니다.
5. place search short query에 노이즈가 남습니다.
   - `정문` 조회에 `창업보육센터`가 함께 노출됩니다.

## 바로 이어갈 우선순위

1. alias/naming 보정
   - `중도`, `니콜스`, `학생식당`을 place/classroom/restaurant 전체에서 같은 방식으로 받게 만들기
2. classroom building classification 보정
   - `김수환관`과 room-to-building mapping 재검토
3. notice category normalization 보정
   - `employment`, `career`, `place` 계열 재매핑
4. restaurant pricing coverage 보강
   - `budget_max`가 실제 evidence를 갖고 동작하게 만들기
5. 그다음 Shared GPT 응답 품질 보정
   - alias와 taxonomy가 먼저 안정화된 뒤 진행하는 편이 효율적입니다.

## 원문 리포트

- [공개 MCP 20문장 실측 검증](/Users/sungjh/Projects/songsim-campus-mcp/docs/qa/public-mcp-live-validation-20.md)
