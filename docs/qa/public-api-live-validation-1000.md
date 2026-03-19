# Public API Live Validation Baseline

API-first public student surface baseline with live-synced truth.

## 실행 기준

- base_url: `https://songsim-public-api.onrender.com`
- evaluation mode: public API first
- truth mode: live-synced normalized truth
- shared GPT / `/gpt/*` / UI flows are excluded from this baseline

## 실행 메타

- checked_at: `2026-03-19T02:09:28+00:00`
- corpus_size: `1009`
- executed: `1009`
- hard fail 45

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
| pass | 952 |
| soft_pass | 0 |
| soft_fail | 0 |
| fail | 45 |
| watch | 5 |
| skip | 7 |

## 도메인 요약

| Domain | Cases | Pass-like |
| --- | --- | --- |
| academic_calendar | 70 | 70 |
| academic_support_guides | 40 | 40 |
| certificate_guides | 40 | 40 |
| classrooms | 60 | 60 |
| courses | 160 | 160 |
| leave_of_absence_guides | 40 | 40 |
| notices | 110 | 66 |
| out_of_scope | 30 | 30 |
| place | 160 | 152 |
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
| PLC-0001 | place | 학생회관 어디야? | fail | exact_mismatch |
| PLC-0002 | place | K관 어디야? | skip | missing_truth |
| PLC-0003 | place | 중도 어디야? | skip | missing_truth |
| PLC-0004 | place | 니콜스관 어디야? | skip | missing_truth |
| PLC-0156 | place | 복사실이 어디야? | skip | missing_truth |
| PLC-0157 | place | 우리은행 전화번호 알려줘 | skip | missing_truth |
| PLC-0158 | place | 카페드림 어디야? | skip | missing_truth |
| PLC-0159 | place | 트러스트짐 어디야? | skip | missing_truth |
| NTC-0002 | notices | academic 공지 알려줘 | fail | set_mismatch |
| NTC-0003 | notices | scholarship 공지 알려줘 | fail | set_mismatch |
| NTC-0008 | notices | academic 최신 공지 보여줘 | fail | set_mismatch |
| NTC-0009 | notices | scholarship 최신 공지 보여줘 | fail | set_mismatch |
| NTC-0012 | notices | academic 공지 알려줘 | fail | set_mismatch |
| NTC-0013 | notices | scholarship 공지 알려줘 | fail | set_mismatch |
| NTC-0018 | notices | academic 최신 공지 보여줘 | fail | set_mismatch |
| NTC-0019 | notices | scholarship 최신 공지 보여줘 | fail | set_mismatch |
| NTC-0022 | notices | academic 공지 알려줘 | fail | set_mismatch |
| NTC-0023 | notices | scholarship 공지 알려줘 | fail | set_mismatch |
| NTC-0028 | notices | academic 최신 공지 보여줘 | fail | set_mismatch |
| NTC-0029 | notices | scholarship 최신 공지 보여줘 | fail | set_mismatch |
| NTC-0032 | notices | academic 공지 알려줘 | fail | set_mismatch |
| NTC-0033 | notices | scholarship 공지 알려줘 | fail | set_mismatch |
| NTC-0038 | notices | academic 최신 공지 보여줘 | fail | set_mismatch |
| NTC-0039 | notices | scholarship 최신 공지 보여줘 | fail | set_mismatch |
| NTC-0042 | notices | academic 공지 알려줘 | fail | set_mismatch |
| NTC-0043 | notices | scholarship 공지 알려줘 | fail | set_mismatch |
| NTC-0048 | notices | academic 최신 공지 보여줘 | fail | set_mismatch |
| NTC-0049 | notices | scholarship 최신 공지 보여줘 | fail | set_mismatch |
| NTC-0052 | notices | academic 공지 알려줘 | fail | set_mismatch |
| NTC-0053 | notices | scholarship 공지 알려줘 | fail | set_mismatch |
| NTC-0058 | notices | academic 최신 공지 보여줘 | fail | set_mismatch |
| NTC-0059 | notices | scholarship 최신 공지 보여줘 | fail | set_mismatch |
| NTC-0062 | notices | academic 공지 알려줘 | fail | set_mismatch |
| NTC-0063 | notices | scholarship 공지 알려줘 | fail | set_mismatch |
| NTC-0068 | notices | academic 최신 공지 보여줘 | fail | set_mismatch |
| NTC-0069 | notices | scholarship 최신 공지 보여줘 | fail | set_mismatch |
| NTC-0072 | notices | academic 공지 알려줘 | fail | set_mismatch |
| NTC-0073 | notices | scholarship 공지 알려줘 | fail | set_mismatch |
| NTC-0078 | notices | academic 최신 공지 보여줘 | fail | set_mismatch |
| NTC-0079 | notices | scholarship 최신 공지 보여줘 | fail | set_mismatch |
| NTC-0082 | notices | academic 공지 알려줘 | fail | set_mismatch |
| NTC-0083 | notices | scholarship 공지 알려줘 | fail | set_mismatch |
| NTC-0088 | notices | academic 최신 공지 보여줘 | fail | set_mismatch |
| NTC-0089 | notices | scholarship 최신 공지 보여줘 | fail | set_mismatch |
| NTC-0092 | notices | academic 공지 알려줘 | fail | set_mismatch |
| NTC-0093 | notices | scholarship 공지 알려줘 | fail | set_mismatch |
| NTC-0098 | notices | academic 최신 공지 보여줘 | fail | set_mismatch |
| NTC-0099 | notices | scholarship 최신 공지 보여줘 | fail | set_mismatch |
| NTC-0102 | notices | academic 공지 알려줘 | fail | set_mismatch |
| NTC-0103 | notices | scholarship 공지 알려줘 | fail | set_mismatch |

## 다음 액션

- `PLC-0155`는 이번 배포에서 pass로 회복됐으므로, 동일 계열 회귀는 place/facility canary로 계속 유지한다.
- 남은 `hard fail 45`는 현재 기준 `notices` academic/scholarship snapshot drift와 `PLC-0001` 1건이므로, 다음 조치는 public notice snapshot 복구와 `학생회관 어디야?` truth/actual 정렬이다.
- 남은 `skip 7`은 place truth를 만드는 DB 경로와 live public snapshot이 어긋난 상태이므로, QA truth env와 public DB를 먼저 일치시킨 뒤 재실행한다.
- course source-gap watchlist는 hard fail counts와 계속 분리한다.
- 최종 공개 배포 전에는 stable canary만 50문장 release gate로 승격한다.
