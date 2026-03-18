# Source registry

스크래퍼/파서를 추가할 때 가장 먼저 업데이트할 문서입니다.

| source_id | 종류 | 원본 | 우선순위 | 파서 상태 | 비고 |
|---|---|---|---|---|---|
| cuk_campus_map | 공식 | https://www.catholic.ac.kr/ko/about/campus-map.do | 높음 | implemented | `mode=getPlaceListByCondition` 공개 JSON을 정규화하여 장소 동기화 |
| cuk_subject_search | 공식 | https://www.catholic.ac.kr/ko/support/subject.do | 높음 | implemented | 개설과목조회 HTML 테이블 + 팝업 상세 파싱 |
| cuk_campus_notices | 공식 | https://www.catholic.ac.kr/ko/campuslife/notice.do | 높음 | implemented | 목록 HTML + 상세 HTML 조합으로 최신 공지 동기화 |
| cuk_library_hours | 공식 | https://library.catholic.ac.kr/webcontent/info/45 | 중간 | implemented | 중앙도서관 개관시간 표를 `중앙도서관` place의 `opening_hours`로 병합 |
| cuk_library_seat_status | 공식 외부 링크 | http://203.229.203.240/8080/Domian5.asp | 높음 | implemented | 중앙도서관 열람실 좌석 현황을 query-time live fetch로 best-effort 조회하고, `library_seat_status_cache`에 짧은 TTL current snapshot을 유지합니다. public API automation은 5분 간격 prewarm으로 cache를 예열하고, source failure 시 15분 이내 stale cache를 우선 반환합니다. |
| cuk_facilities | 공식 | https://www.catholic.ac.kr/ko/campuslife/restaurant.do | 중간 | implemented | 식당/편의시설 운영시간을 위치 기준으로 기존 place의 `opening_hours`에 병합하고, 공식 학식 3곳의 주간 메뉴 PDF 링크와 추출 텍스트를 `campus_dining_menus` current snapshot으로 동기화하며, facility name snapshot/keyword index를 기반으로 place/facility query ranking(search)에도 활용 |
| cuk_transport | 공식 | https://www.catholic.ac.kr/ko/about/location_songsim.do | 중간 | implemented | 성심교정 정적 교통 안내를 `transport_guides`로 정규화 |
| cuk_certificate_guides | 공식 | https://www.catholic.ac.kr/ko/support/certificate.do | 중간 | implemented | 증명서 발급 정적 안내를 `certificate_guides` current snapshot으로 정규화 |
| cuk_leave_of_absence_guides | 공식 | https://www.catholic.ac.kr/ko/support/leave_of_absence.do | 중간 | implemented | 휴학 안내 정적 페이지를 `leave_of_absence_guides` current snapshot으로 정규화 |
| cuk_academic_status_guides | 공식 | https://www.catholic.ac.kr/ko/support/return_from_leave_of_absence.do | 중간 | implemented | 복학, 자퇴, 재입학 정적 페이지 3개를 `academic_status_guides` current snapshot family로 정규화 |
| cuk_scholarship_guides | 공식 | https://www.catholic.ac.kr/ko/support/scholarship_songsim.do | 중간 | implemented | 장학제도 안내 HTML과 공식 문서 링크를 `scholarship_guides` current snapshot으로 정규화 |
| cuk_academic_support_guides | 공식 | https://www.catholic.ac.kr/ko/support/academic_contact_information.do | 중간 | implemented | 학사지원팀 업무안내 표를 `academic_support_guides` current snapshot으로 정규화 |
| cuk_academic_status_guides | 공식 | https://www.catholic.ac.kr/ko/support/academic_contact_information.do | 중간 | implemented | 학적변동 관련 업무안내 표를 `academic_status_guides` current snapshot으로 정규화 |
| cuk_wifi_guides | 공식 | https://www.catholic.ac.kr/ko/campuslife/wifi.do | 중간 | implemented | 무선랜서비스 HTML 표를 `wifi_guides` current snapshot으로 정규화 |
| cuk_academic_calendar | 공식 | https://www.catholic.ac.kr/ko/support/calendar2024_list.do | 중간 | implemented | 공개 JSON feed(`mode=getCalendarData`)를 `academic_calendar` current snapshot으로 정규화 |
| kakao_local | 외부 API | https://developers.kakao.com/docs/latest/ko/local/common | 높음 | implemented | API 키가 있으면 `/restaurants/nearby`와 개인화 식사 추천에서 lazy cache 기반 실시간 장소 검색 사용 |
| kakao_place_detail | 외부 웹 | https://place.map.kakao.com/ | 중간 | implemented | Kakao place detail `panel3` 공개 흐름에서 영업시간을 best-effort로 가져와 `restaurant_hours_cache`에 lazy cache 저장 |

## 실시간 강의실 조사 메모

- 조사일: `2026-03-15`
- 조사 범위: 가톨릭대학교 공식 캠퍼스맵, 개설과목조회, 교내 시설/대관 관련 공개 페이지
- 결과: 공개 접근 가능한 `현재 강의실 점유/예약/배정 현황` 공식 feed나 API는 확인하지 못했습니다.
- 현재 정책: `/classrooms/empty`, `/gpt/classrooms/empty`, `tool_list_estimated_empty_classrooms`는 공식 실시간 source adapter를 먼저 시도하고, 기본 배포에서는 시간표 기준 예상 공실로 폴백합니다.

## 파서 원칙

1. 원본 HTML/JSON을 저장하지 않고도 테스트 가능한 **샘플 fixture**를 남긴다.
2. 파서는 **정규화된 스키마**를 반환한다.
3. 소스별 `source_tag`를 보존한다.
4. 데이터가 모호하면 과감히 버리고, `raw_*` 필드에만 남긴다.
5. 시간표/운영시간은 바뀔 수 있으므로 `last_synced_at`를 항상 기록한다.
