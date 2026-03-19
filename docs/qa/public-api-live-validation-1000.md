# Public API Live Validation Baseline

API-first public student surface baseline with live-synced truth.

## 실행 기준

- base_url: `https://songsim-public-api.onrender.com`
- evaluation mode: public API first
- truth mode: live-synced normalized truth
- shared GPT / `/gpt/*` / UI flows are excluded from this baseline

## 실행 메타

- checked_at: `2026-03-19T00:59:18+00:00`
- corpus_size: `1009`
- executed: `1009`
- hard fail 22

## 판정 레벨

- `pass`: normalized truth or invariant matched
- `soft_pass`: reserved for future manual review overlay
- `soft_fail`: reserved for future manual review overlay
- `fail`: hard mismatch against normalized truth or invariants
- `watch`: source-gap watchlist item
- `skip`: truth unavailable in degraded mode

## 집계

| Verdict | Count |
| --- | --- |
| pass | 981 |
| soft_pass | 0 |
| soft_fail | 0 |
| fail | 22 |
| watch | 5 |
| skip | 1 |

## 도메인 요약

| Domain | Cases | Pass-like |
| --- | --- | --- |
| academic_calendar | 70 | 70 |
| academic_support_guides | 40 | 40 |
| certificate_guides | 40 | 40 |
| classrooms | 60 | 60 |
| courses | 160 | 160 |
| leave_of_absence_guides | 40 | 40 |
| notices | 110 | 88 |
| out_of_scope | 30 | 30 |
| place | 160 | 159 |
| registration_guides | 4 | 4 |
| restaurants | 160 | 160 |
| scholarship_guides | 40 | 40 |
| transport | 50 | 50 |
| wifi_guides | 40 | 40 |

## Guide-Domain Coverage

| Domain | Cases | Pass-like |
| --- | --- | --- |
| academic_calendar | 70 | 70 |
| certificate_guides | 40 | 40 |
| registration_guides | 4 | 4 |
| scholarship_guides | 40 | 40 |
| wifi_guides | 40 | 40 |
| leave_of_absence_guides | 40 | 40 |
| academic_support_guides | 40 | 40 |

## Watchlist (hard fail 제외)

| ID | User utterance | Verdict | Comparison |
| --- | --- | --- | --- |
| CW01 | 데이터베이스 과목 있어 | watch | watch_only |
| CW02 | CSE301 과목 뭐야 | watch | watch_only |
| CW03 | 김가톨 교수 수업 있어 | watch | watch_only |
| CW04 | 데이타베이스 과목 있어 | watch | watch_only |
| CW05 | CSE 420 과목 뭐야 | watch | watch_only |

## 주요 이슈

| ID | Domain | User utterance | Verdict | Comparison |
| --- | --- | --- | --- | --- |
| PLC-0155 | place | 학생회관 1층 24시간 편의점 어디야? | skip | missing_truth |
| NTC-0002 | notices | academic 공지 알려줘 | fail | set_mismatch |
| NTC-0008 | notices | academic 최신 공지 보여줘 | fail | set_mismatch |
| NTC-0012 | notices | academic 공지 알려줘 | fail | set_mismatch |
| NTC-0018 | notices | academic 최신 공지 보여줘 | fail | set_mismatch |
| NTC-0022 | notices | academic 공지 알려줘 | fail | set_mismatch |
| NTC-0028 | notices | academic 최신 공지 보여줘 | fail | set_mismatch |
| NTC-0032 | notices | academic 공지 알려줘 | fail | set_mismatch |
| NTC-0038 | notices | academic 최신 공지 보여줘 | fail | set_mismatch |
| NTC-0042 | notices | academic 공지 알려줘 | fail | set_mismatch |
| NTC-0048 | notices | academic 최신 공지 보여줘 | fail | set_mismatch |
| NTC-0052 | notices | academic 공지 알려줘 | fail | set_mismatch |
| NTC-0058 | notices | academic 최신 공지 보여줘 | fail | set_mismatch |
| NTC-0062 | notices | academic 공지 알려줘 | fail | set_mismatch |
| NTC-0068 | notices | academic 최신 공지 보여줘 | fail | set_mismatch |
| NTC-0072 | notices | academic 공지 알려줘 | fail | set_mismatch |
| NTC-0078 | notices | academic 최신 공지 보여줘 | fail | set_mismatch |
| NTC-0082 | notices | academic 공지 알려줘 | fail | set_mismatch |
| NTC-0088 | notices | academic 최신 공지 보여줘 | fail | set_mismatch |
| NTC-0092 | notices | academic 공지 알려줘 | fail | set_mismatch |
| NTC-0098 | notices | academic 최신 공지 보여줘 | fail | set_mismatch |
| NTC-0102 | notices | academic 공지 알려줘 | fail | set_mismatch |
| NTC-0108 | notices | academic 최신 공지 보여줘 | fail | set_mismatch |

## 다음 액션

- `notices` freshness를 먼저 복구한 뒤 `songsim-eval-public sync-truth`를 다시 돌려 이 리포트를 재생성한다.
- `PLC-0155`는 place/facility runtime fix를 적용한 뒤 다시 평가해서 skip을 제거한다.
- `hard fail 22`와 `skip 1`은 현재 스냅샷의 상태이므로, 배포 후 재실행 전까지는 임의로 조정하지 않는다.
- course source-gap watchlist는 hard fail counts와 계속 분리한다.
- 최종 공개 배포 전에는 stable canary만 50문장 release gate로 승격한다.
