# Source registry

스크래퍼/파서를 추가할 때 가장 먼저 업데이트할 문서입니다.

| source_id | 종류 | 원본 | 우선순위 | 파서 상태 | 비고 |
|---|---|---|---|---|---|
| cuk_campus_map | 공식 | https://www.catholic.ac.kr/ko/about/campus-map.do | 높음 | implemented | `mode=getPlaceListByCondition` 공개 JSON을 정규화하여 장소 동기화 |
| cuk_subject_search | 공식 | https://www.catholic.ac.kr/ko/support/subject.do | 높음 | implemented | 개설과목조회 HTML 테이블 + 팝업 상세 파싱 |
| cuk_campus_notices | 공식 | https://www.catholic.ac.kr/ko/campuslife/notice.do | 높음 | implemented | 목록 HTML + 상세 HTML 조합으로 최신 공지 동기화 |
| cuk_library_hours | 공식 | https://library.catholic.ac.kr/webcontent/info/45 | 중간 | implemented | 중앙도서관 개관시간 표를 `중앙도서관` place의 `opening_hours`로 병합 |
| cuk_facilities | 공식 | https://www.catholic.ac.kr/ko/campuslife/restaurant.do | 중간 | implemented | 식당/편의시설 운영시간을 위치 기준으로 기존 place의 `opening_hours`에 병합 |
| cuk_transport | 공식 | https://www.catholic.ac.kr/ko/about/location_songsim.do | 중간 | implemented | 성심교정 정적 교통 안내를 `transport_guides`로 정규화 |
| kakao_local | 외부 API | https://developers.kakao.com/docs/latest/ko/local/common | 높음 | implemented | API 키가 있으면 `/restaurants/nearby`와 개인화 식사 추천에서 lazy cache 기반 실시간 장소 검색 사용 |

## 파서 원칙

1. 원본 HTML/JSON을 저장하지 않고도 테스트 가능한 **샘플 fixture**를 남긴다.
2. 파서는 **정규화된 스키마**를 반환한다.
3. 소스별 `source_tag`를 보존한다.
4. 데이터가 모호하면 과감히 버리고, `raw_*` 필드에만 남긴다.
5. 시간표/운영시간은 바뀔 수 있으므로 `last_synced_at`를 항상 기록한다.
