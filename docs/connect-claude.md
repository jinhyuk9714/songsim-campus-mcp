# Connect From Claude

## 연결 정보

- 이름 예시: `Songsim Campus MCP`
- Streamable HTTP URL: `https://your-public-mcp-url/mcp`
- 기본 입구: student-facing primary surface는 Remote MCP, HTTP API는 companion layer
- 로그인: 현재 공개 배포 기본값은 익명 read-only, 운영자가 OAuth 모드로 바꾸면 로그인 필요

## Claude에서 먼저 물어보기 좋은 축

- 오늘 할 일: 최신 공지, 소속기관 공지, 행사안내, 학사일정
- 어디 / 연락처: 건물, 시설, 전화번호, 운영시간, 교통, Wi-Fi
- 절차 / 제도: 등록, 증명, 휴학, 수업, 계절학기, 성적·졸업, 교류, 장학
- 공부공간 / 자원: 과목, 도서관 좌석, 예상 빈 강의실, 학식, 주변 식당, PC 소프트웨어
- 특수 경로: 기숙사, 생활지원, 상담·예비군·병원, 소속기관 공지

## 추천 사용 흐름

1. `songsim://usage-guide`를 먼저 읽어 공개 범위를 확인
2. 질문과 가장 가까운 prompt / resource / tool을 선택
3. 필요하면 HTTP companion으로 같은 결과를 직접 검증

## 바로 해볼 질문

- `최신 학사 공지 2개 보여줘`
- `학생회관 어디야?`
- `보건실 전화번호 알려줘`
- `등록금 반환 기준 알려줘`
- `공결 신청 방법 알려줘`
- `졸업요건 알려줘`
- `중앙도서관 열람실 남은 좌석 알려줘`
- `학생식당 메뉴 보여줘`
- `SPSS 설치된 컴퓨터실 어디야`
- `성심교정 기숙사 안내해줘`
- `학생상담 어디서 받아?`
- `국제학부 최신 공지 알려줘`

## 공개 서버 제한

- read-only 조회 전용
- 운영자가 OAuth 모드로 바꾸면 로그인 필요
- profile, timetable, admin/sync 기능은 로컬 full 모드에서만 사용

## 검증 자산

- [공개 MCP 릴리즈팩 50](qa/public-mcp-release-pack-50.md)
- [공개 MCP 라이브 판정 요약](qa/public-mcp-live-validation-summary.md)
- [공개 API 1000문장 라이브 검증](qa/public-api-live-validation-1000.md)
