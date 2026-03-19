# Public API Live Validation Baseline

API-first public student surface baseline with live-synced truth.

## 실행 기준

- base_url: `https://songsim-public-api.onrender.com`
- evaluation mode: public API first
- truth mode: live-synced normalized truth
- shared GPT / `/gpt/*` / UI flows are excluded from this baseline

## 실행 메타

- checked_at: `2026-03-19T03:42:22+00:00`
- corpus_size: `1009`
- executed: `1009`
- hard fail 0

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
| pass | 1004 |
| soft_pass | 0 |
| soft_fail | 0 |
| fail | 0 |
| watch | 5 |
| skip | 0 |

## 도메인 요약

| Domain | Cases | Pass-like |
| --- | --- | --- |
| academic_calendar | 70 | 70 |
| academic_support_guides | 40 | 40 |
| certificate_guides | 40 | 40 |
| classrooms | 60 | 60 |
| courses | 160 | 160 |
| leave_of_absence_guides | 40 | 40 |
| notices | 110 | 110 |
| out_of_scope | 30 | 30 |
| place | 160 | 160 |
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

_No hard issues._

## 다음 액션

- Keep the course source-gap watchlist separate from hard fail counts.
- Re-run `songsim-eval-public sync-truth` before large public releases.
- Promote only stable canaries into the 50-question release gate.
