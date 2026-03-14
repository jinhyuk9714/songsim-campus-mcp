# Copy-paste tasks for Codex

## Task 1: 캠퍼스맵 파서 추가
`docs/source_registry.md`의 `cuk_campus_map`을 구현해줘. parser는 buildings/facilities를 정규화해서 place 레코드로 반환하고, fixture 기반 테스트도 추가해줘.

## Task 2: 개설과목조회 파서 추가
공식 개설과목조회 HTML에서 과목명, 교수, 강의실, raw schedule을 뽑아 `CourseRecord`로 변환하는 파서를 추가해줘. 실패 케이스가 생기면 fixture를 추가하고 parser contract test를 만들어줘.

## Task 3: Kakao Local 연동
식당 추천을 데모 JSON 대신 Kakao Local API로 가져오게 바꿔줘. 결과는 캐시 가능하게 설계하고, origin 장소 기준으로 distance + walk_minutes를 계산해줘.

## Task 4: 공지 분류 강화
공지 제목과 본문 일부를 바탕으로 academic / scholarship / event / cafeteria / urgent 분류 규칙을 추가하고 테스트도 작성해줘.

## Task 5: MCP 품질 강화
MCP tools description을 더 구체적으로 고쳐서 LLM이 적절한 tool을 고르게 만들고, `source_registry.md`를 resource로 노출해줘.
