# Main Site Coverage Audit

기준일: `2026-03-17`

감사 범위는 `https://www.catholic.ac.kr/ko/*`만 포함합니다. 홈과 전체메뉴에서 외부 도메인으로 나가는 링크는 `external / out of scope`로 분리했습니다.

## 결론

현재 이 MCP는 `www.catholic.ac.kr/ko/*`의 모든 것을 알 수 없습니다.

직접 지원하는 축은 성심교정 중심의 검증 가능한 데이터 도구 범위로 제한됩니다.

- 장소/건물과 캠퍼스맵
- 성심교정 교통 안내
- 개설과목 조회
- 최신 공지 조회
- 교시표
- 중앙도서관 열람실 좌석
- 공식 학식 메뉴
- 주변 식당/브랜드 식당 검색
- 시간표 기반 예상 빈 강의실

반대로 메인 사이트의 정적 안내, 행정, 홍보, 연구, 정책, 입학 상세, 170주년 섹션 대부분은 현재 공개 MCP/HTTP 표면에서 직접 질의할 수 없습니다.

## Coverage Matrix

| 대표 범주 | 대표 URL | 현재 MCP 질의 가능 여부 | 상태 | 근거(source/tool/doc) | 갭 이유 | 추가 adapter 후보 |
|---|---|---|---|---|---|---|
| 가대소개 | `https://www.catholic.ac.kr/ko/about/history.do` | 부분적으로 가능. `캠퍼스맵`, `장소/건물`, `오시는길`은 직접 질의 가능 | 부분지원 | [docs/source_registry.md](/Users/sungjh/Projects/songsim-campus-mcp/docs/source_registry.md) 의 `cuk_campus_map`, `cuk_transport`; [docs/connect-codex.md](/Users/sungjh/Projects/songsim-campus-mcp/docs/connect-codex.md); [src/songsim_campus/api.py](/Users/sungjh/Projects/songsim-campus-mcp/src/songsim_campus/api.py) 의 `/places`, `/places/{identifier}`, `/transport`; [src/songsim_campus/mcp_server.py](/Users/sungjh/Projects/songsim-campus-mcp/src/songsim_campus/mcp_server.py) 의 `tool_search_places`, `tool_get_place`, `tool_list_transport_guides` | `연혁`, `교육이념`, `총장실`, `경영정보`, `규정`, `요람`, `주요전화번호`, `캠퍼스투어`, `교회문헌`은 현재 source/tool이 없음 | `phone_book.do`, `budgetaccount.do`, `rule.do`, `univ_bulletin.do`, `campus_tour.do` 정적 파서 또는 resource 추가 |
| 입학ㆍ교육 | `https://www.catholic.ac.kr/ko/academics/edu_undergraduate1.do` | 간접적으로만 가능. 교육 관련 질문 중 `개설과목 조회` 수준만 직접 가능 | 부분지원 | [docs/source_registry.md](/Users/sungjh/Projects/songsim-campus-mcp/docs/source_registry.md) 의 `cuk_subject_search`; [docs/connect-codex.md](/Users/sungjh/Projects/songsim-campus-mcp/docs/connect-codex.md); [src/songsim_campus/api.py](/Users/sungjh/Projects/songsim-campus-mcp/src/songsim_campus/api.py) 의 `/courses`, `/periods`; [src/songsim_campus/mcp_server.py](/Users/sungjh/Projects/songsim-campus-mcp/src/songsim_campus/mcp_server.py) 의 `tool_search_courses`, `tool_get_class_periods` | `대학 입학`, `대학원 입학`, `외국인 입학`, `평생교육`, `대학/대학원 소개`는 현재 전용 source/tool이 없음 | `adm_general_graduate.do`, `adm_foreigner.do`, `edu_undergraduate*.do`, `edu_graduate*.do` 정적 안내 파서 |
| 연구ㆍ산학 | `https://www.catholic.ac.kr/ko/research/result.do` | 직접 질의 불가 | 비지원 | [docs/source_registry.md](/Users/sungjh/Projects/songsim-campus-mcp/docs/source_registry.md) 에 연구/산학 source 없음; [src/songsim_campus/api.py](/Users/sungjh/Projects/songsim-campus-mcp/src/songsim_campus/api.py) 와 [src/songsim_campus/mcp_server.py](/Users/sungjh/Projects/songsim-campus-mcp/src/songsim_campus/mcp_server.py) 에 대응 엔드포인트/도구 없음 | `연구성과`, `산학협력단`, `연구기관`, `국책사업단`은 현재 커버리지 밖 | `result.do`, `cukrnd.do`, `institute.do`, `national_rnd.do` 목록/상세 파서 |
| 학사지원 | `https://www.catholic.ac.kr/ko/support/calendar2024_list.do` | 부분적으로 가능. `개설과목`, `교시표`, `학사 관련 공지`, `예상 빈 강의실`은 직접 질의 가능 | 부분지원 | [docs/source_registry.md](/Users/sungjh/Projects/songsim-campus-mcp/docs/source_registry.md) 의 `cuk_subject_search`, `cuk_campus_notices`; [docs/connect-codex.md](/Users/sungjh/Projects/songsim-campus-mcp/docs/connect-codex.md); [src/songsim_campus/api.py](/Users/sungjh/Projects/songsim-campus-mcp/src/songsim_campus/api.py) 의 `/courses`, `/periods`, `/notices`, `/classrooms/empty`; [src/songsim_campus/mcp_server.py](/Users/sungjh/Projects/songsim-campus-mcp/src/songsim_campus/mcp_server.py) 의 `tool_search_courses`, `tool_get_class_periods`, `tool_list_latest_notices`, `tool_list_estimated_empty_classrooms` | `학사일정`, `등록`, `수업 안내`, `계절학기`, `학적변동`, `증명발급`, `장학제도`, `학생교류`, `업무안내`는 전용 source/tool이 없음 | `calendar*.do`, `certificate.do`, `scholarship_*.do`, `exchange_*.do`, `academic_contact_information.do` 파서 추가 |
| 대학생활 | `https://www.catholic.ac.kr/ko/campuslife/notice.do` | 부분적으로 가능. `공지`, `학식 메뉴`, `식당/편의시설 운영시간 일부`, `도서관 좌석`, `주변 식당`은 직접 질의 가능 | 부분지원 | [docs/source_registry.md](/Users/sungjh/Projects/songsim-campus-mcp/docs/source_registry.md) 의 `cuk_campus_notices`, `cuk_facilities`, `cuk_library_hours`, `cuk_library_seat_status`, `kakao_local`, `kakao_place_detail`; [docs/connect-codex.md](/Users/sungjh/Projects/songsim-campus-mcp/docs/connect-codex.md); [src/songsim_campus/api.py](/Users/sungjh/Projects/songsim-campus-mcp/src/songsim_campus/api.py) 의 `/notices`, `/dining-menus`, `/restaurants`, `/restaurants/nearby`, `/restaurants/search`, `/library-seats`, `/places`; [src/songsim_campus/mcp_server.py](/Users/sungjh/Projects/songsim-campus-mcp/src/songsim_campus/mcp_server.py) 의 `tool_list_latest_notices`, `tool_search_dining_menus`, `tool_find_nearby_restaurants`, `tool_search_restaurants`, `tool_get_library_seat_status`, `tool_search_places` | `행사안내`, `외부기관공지`, `학생활동`, `학생지원`, `WIFI`, `보건실`, `교내병원`, `주거정보`, `분실물`, `안전관리`는 전용 source/tool이 없거나 일부 장소 정보만 간접 지원 | `notice_event.do`, `notice_outside.do`, `wifi.do`, 복지/지원 정적 페이지 파서 추가 |
| CUK홍보 | `https://www.catholic.ac.kr/ko/newsroom/photonews.do` | 직접 질의 불가 | 비지원 | [docs/source_registry.md](/Users/sungjh/Projects/songsim-campus-mcp/docs/source_registry.md) 에 뉴스룸/홍보 source 없음; [docs/connect-codex.md](/Users/sungjh/Projects/songsim-campus-mcp/docs/connect-codex.md) 의 공개 사용 범위에도 없음; [src/songsim_campus/api.py](/Users/sungjh/Projects/songsim-campus-mcp/src/songsim_campus/api.py), [src/songsim_campus/mcp_server.py](/Users/sungjh/Projects/songsim-campus-mcp/src/songsim_campus/mcp_server.py) 에 대응 엔드포인트/도구 없음 | `포토뉴스`, `보도자료`, `언론에서 본 가톨릭대`, `브로슈어`, `CUK Story`, `갤러리`는 현재 커버리지 밖 | `photonews.do`, `press.do`, `interview.do`, `brochure.do`, `cukstory.do`, `gallery.do` 파서 추가 |
| 서비스이용안내 | `https://www.catholic.ac.kr/ko/service/Bidding.do` | 직접 질의 불가 | 비지원 | [docs/source_registry.md](/Users/sungjh/Projects/songsim-campus-mcp/docs/source_registry.md) 에 서비스/정책 source 없음; [src/songsim_campus/api.py](/Users/sungjh/Projects/songsim-campus-mcp/src/songsim_campus/api.py), [src/songsim_campus/mcp_server.py](/Users/sungjh/Projects/songsim-campus-mcp/src/songsim_campus/mcp_server.py) 에 대응 엔드포인트/도구 없음 | `입찰공고`, `채용공고`, `청탁금지법`, `영상정보처리기기 방침`, `개인정보처리방침` 등은 현재 public MCP 범위 밖 | `Bidding.do`, `Job-posting.do` 목록 파서와 `privacy.do`, `notice_cctv_regulation.do`, `anti_graft_law1.do` 정적 resource 추가 |
| 170주년 기념사업 | `https://www.catholic.ac.kr/ko/170ani/president-message-170.do` | 직접 질의 불가 | 비지원 | [docs/source_registry.md](/Users/sungjh/Projects/songsim-campus-mcp/docs/source_registry.md) 에 170주년 source 없음; [src/songsim_campus/api.py](/Users/sungjh/Projects/songsim-campus-mcp/src/songsim_campus/api.py), [src/songsim_campus/mcp_server.py](/Users/sungjh/Projects/songsim-campus-mcp/src/songsim_campus/mcp_server.py) 에 대응 엔드포인트/도구 없음 | `인사말`, `연혁`, `슬로건`, `홍보영상`, `온라인박물관`, `행사일정`, `기부 안내`는 현재 커버리지 밖 | `170ani/*` 정적 파서와 170주년 리소스 컬렉션 추가 |

## Live Site Verification Notes

홈과 전체메뉴 기준으로 다음 대표 링크를 확인했습니다.

- `가대소개` -> `/ko/about/history.do`
- `입학ㆍ교육` -> `/ko/academics/edu_undergraduate1.do`
- `연구ㆍ산학` -> `/ko/research/result.do`
- `학사지원` -> `/ko/support/calendar2024_list.do`
- `대학생활` -> `/ko/campuslife/notice.do`
- `CUK홍보` -> `/ko/newsroom/photonews.do`
- `170주년 기념사업` -> `/ko/170ani/president-message-170.do`

홈의 `성심 Link`와 footer 기준으로도 현재 지원/미지원 경계가 분명했습니다.

- 지원 축과 직접 연결되는 링크: `캠퍼스맵`, `식당메뉴안내`, `오시는길`
- 현재 비지원 축으로 남는 링크: `증명발급`, `WIFI`, `주요전화번호`, `입찰공고`, `채용공고`, `청탁금지법`, `개인정보처리방침`, `영상정보처리기기 방침`

## External / Out of Scope

다음 링크는 `www.catholic.ac.kr/ko/*` 범위를 벗어나므로 본 감사표에서는 외부 도메인으로 분리했습니다.

- `https://ipsi.catholic.ac.kr/`
- `https://uportal.catholic.ac.kr/`
- `https://e-cyber.catholic.ac.kr/`
- `https://songeui.catholic.ac.kr/`
- `https://songsin.catholic.ac.kr/`
- `https://irb.catholic.ac.kr/irb/index.do`
- `https://cuk.elsevierpure.com/`
- `https://giving.catholic.ac.kr/`
- Instagram, YouTube, Facebook, Naver Blog 등 SNS 링크

## Next Adapter Priorities

메인 사이트 대비 체감 커버리지를 빠르게 넓히려면 아래 순서가 효율적입니다.

1. `학사지원`의 `학사일정`, `증명발급`, `장학제도` 정적 안내 파서
2. `대학생활`의 `행사안내`, `외부기관공지`, `WIFI`, 학생지원 페이지 파서
3. `가대소개`의 `주요전화번호`와 주요 정적 안내 resource
4. `CUK홍보`의 `보도자료` 또는 `포토뉴스` 목록 파서
5. `서비스이용안내`의 `입찰공고`, `채용공고` 목록 파서

이 순서를 따르면 성심교정 사용자 질문 빈도가 높은 영역부터 `부분지원`을 `지원`으로 끌어올릴 수 있습니다.
