# Public API Live Validation Baseline

API-first public student surface baseline with live-synced truth.

## 실행 기준

- base_url: `https://songsim-public-api.onrender.com`
- evaluation mode: public API first
- truth mode: live-synced normalized truth
- shared GPT / `/gpt/*` / UI flows are excluded from this baseline

## 실행 메타

- checked_at: `2026-03-21T12:31:05+00:00`
- corpus_size: `1000`
- executed: `1005`
  - includes `5` watchlist rows
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
| pass | 896 |
| soft_pass | 0 |
| soft_fail | 0 |
| fail | 0 |
| watch | 5 |
| skip | 104 |

## 도메인 요약

| Domain | Cases | Pass-like |
| --- | --- | --- |
| academic_calendar | 55 | 55 |
| academic_milestone_guides | 25 | 25 |
| academic_support_guides | 12 | 12 |
| affiliated_notices | 35 | 35 |
| campus_life_notices | 25 | 25 |
| campus_life_support_guides | 30 | 30 |
| certificate_guides | 12 | 12 |
| class_guides | 35 | 35 |
| classrooms | 40 | 40 |
| courses | 140 | 140 |
| dormitory_guides | 20 | 20 |
| leave_of_absence_guides | 12 | 12 |
| notices | 80 | 80 |
| out_of_scope | 20 | 20 |
| pc_software_entries | 20 | 20 |
| phone_book | 35 | 35 |
| place | 140 | 136 |
| registration_guides | 25 | 25 |
| restaurants | 100 | 0 |
| scholarship_guides | 12 | 12 |
| seasonal_semester_guides | 10 | 10 |
| student_activity_guides | 25 | 25 |
| student_exchange_guides | 25 | 25 |
| student_exchange_partners | 32 | 32 |
| transport | 25 | 25 |
| wifi_guides | 10 | 10 |

## Guide-Domain Coverage

| Domain | Cases | Pass-like |
| --- | --- | --- |
| academic_calendar | 55 | 55 |
| affiliated_notices | 35 | 35 |
| campus_life_notices | 25 | 25 |
| certificate_guides | 12 | 12 |
| dormitory_guides | 20 | 20 |
| campus_life_support_guides | 30 | 30 |
| pc_software_entries | 20 | 20 |
| registration_guides | 25 | 25 |
| class_guides | 35 | 35 |
| seasonal_semester_guides | 10 | 10 |
| academic_milestone_guides | 25 | 25 |
| student_activity_guides | 25 | 25 |
| phone_book | 35 | 35 |
| scholarship_guides | 12 | 12 |
| wifi_guides | 10 | 10 |
| leave_of_absence_guides | 12 | 12 |
| academic_support_guides | 12 | 12 |
| student_exchange_partners | 32 | 32 |

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
| PLC-0013 | place | 보건센터 어디야? | skip | missing_truth |
| PLC-0049 | place | 보건실 어디야? | skip | missing_truth |
| PLC-0083 | place | 보건실 알려줘 | skip | missing_truth |
| PLC-0117 | place | 보건실 보여줘 | skip | missing_truth |
| RST-0001 | restaurants | 학생식당 근처 한식집 추천해줘 | skip | missing_truth |
| RST-0002 | restaurants | 정문 근처 1만원 이하 밥집 추천해줘 먼저 알려주고 핵심만 같이 정리해줘 | skip | missing_truth |
| RST-0003 | restaurants | 중도 근처 밥집 추천해줘 | skip | missing_truth |
| RST-0004 | restaurants | 학 생 식 당 근처 밥집 추천해줘 | skip | missing_truth |
| RST-0005 | restaurants | K관 근처 카페 추천해줘 관련해서 뭐 보면 돼? | skip | missing_truth |
| RST-0006 | restaurants | 니콜스관 근처 카페 추천해줘 | skip | missing_truth |
| RST-0007 | restaurants | 중앙도서관 근처 카페 추천해줘 먼저 알려주고 핵심만 같이 정리해줘 | skip | missing_truth |
| RST-0008 | restaurants | 니콜스 근처 지금 여는 밥집 추천해줘 | skip | missing_truth |
| RST-0009 | restaurants | 정문 근처 밥집 추 천 해 줘 | skip | missing_truth |
| RST-0010 | restaurants | K관 근처 밥집 추천해줘 관련해서 뭐 보면 돼? | skip | missing_truth |
| RST-0011 | restaurants | 니콜스관 근처 밥집 추천해줘 | skip | missing_truth |
| RST-0012 | restaurants | 학생회관 근처 밥집 추천해줘 먼저 알려주고 핵심만 같이 정리해줘 | skip | missing_truth |
| RST-0013 | restaurants | K관 근처 메가커피 검색해줘 | skip | missing_truth |
| RST-0014 | restaurants | 중 앙 도 서 관 근처 스타벅스 | skip | missing_truth |
| RST-0015 | restaurants | 카페 관련해서 뭐 보면 돼? | skip | missing_truth |
| RST-0016 | restaurants | 맘스터치 검색해줘 | skip | missing_truth |
| RST-0017 | restaurants | 매머드커피 먼저 알려주고 핵심만 같이 정리해줘 | skip | missing_truth |
| RST-0018 | restaurants | 메가커피 검색해줘 | skip | missing_truth |
| RST-0019 | restaurants | 버거킹 검색해줘 | skip | missing_truth |
| RST-0020 | restaurants | 분식집 관련해서 뭐 보면 돼? | skip | missing_truth |
| RST-0021 | restaurants | 스타벅스 검색해줘 | skip | missing_truth |
| RST-0022 | restaurants | 이디야 먼저 알려주고 핵심만 같이 정리해줘 | skip | missing_truth |
| RST-0023 | restaurants | 치킨집 검색해줘 | skip | missing_truth |
| RST-0024 | restaurants | 커피빈 검색해줘 | skip | missing_truth |
| RST-0025 | restaurants | 컴포즈커피 관련해서 뭐 보면 돼? | skip | missing_truth |
| RST-0026 | restaurants | 학생식당 근처 한식집 추천해줘 알려줘 | skip | missing_truth |
| RST-0027 | restaurants | 정문 근처 1만원 이하 밥집 추천해줘 가능하면 바로 확인할 정보도 같이 알려줘 | skip | missing_truth |
| RST-0028 | restaurants | 중도 근처 밥집 추천해줘 알려줘 | skip | missing_truth |
| RST-0029 | restaurants | 학 생 식 당 근처 밥집 추천해줘 알려줘 | skip | missing_truth |
| RST-0030 | restaurants | K관 근처 카페 추천해줘 | skip | missing_truth |
| RST-0031 | restaurants | 니콜스관 근처 카페 추천해줘 먼저 알려주고 핵심만 같이 정리해줘 | skip | missing_truth |
| RST-0032 | restaurants | 중도 근처 카페 추천해줘 | skip | missing_truth |
| RST-0033 | restaurants | 니 콜 스 관 근처 지금 여는 밥집 추천해줘 | skip | missing_truth |
| RST-0034 | restaurants | 정문 근처 밥집 추천해줘 | skip | missing_truth |
| RST-0035 | restaurants | K관 근처 밥집 추천해줘 먼저 알려주고 핵심만 같이 정리해줘 | skip | missing_truth |
| RST-0036 | restaurants | 니콜스 근처 밥집 추천해줘 | skip | missing_truth |
| RST-0037 | restaurants | 학 생 회 관 근처 밥집 추천해줘 | skip | missing_truth |
| RST-0038 | restaurants | K관 근처 메가커피 검색해줘 지금 기준으로 | skip | missing_truth |
| RST-0039 | restaurants | 중앙도서관 근처 스타벅스 먼저 알려주고 핵심만 같이 정리해줘 | skip | missing_truth |
| RST-0040 | restaurants | 카페 검색해줘 | skip | missing_truth |
| RST-0041 | restaurants | 맘 스 터 치 | skip | missing_truth |
| RST-0042 | restaurants | 매머드커피 검색해줘 | skip | missing_truth |
| RST-0043 | restaurants | 메가커피 먼저 알려주고 핵심만 같이 정리해줘 | skip | missing_truth |
| RST-0044 | restaurants | 버거킹 검색해줘 지금 기준으로 | skip | missing_truth |
| RST-0045 | restaurants | 분식집 검색해줘 | skip | missing_truth |
| RST-0046 | restaurants | 스타벅스 알려줘 | skip | missing_truth |

## 다음 액션

- Keep the course source-gap watchlist separate from hard fail counts.
- Re-run `songsim-eval-public sync-truth` before large public releases.
- Promote only stable canaries into the 50-question release gate.
