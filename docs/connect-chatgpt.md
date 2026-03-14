# Connect From ChatGPT

## 연결 정보

- 이름 예시: `Songsim Campus MCP`
- URL: `https://your-public-mcp-url/mcp`
- 모드: read-only public server
- 로그인: Auth0 + Google login

## GPT 링크로 공개하고 싶을 때

ChatGPT의 `chatgpt.com/g/...` 링크를 만들고 싶다면 MCP connector 대신 GPT Builder의 `Actions`를 사용합니다.

- Actions schema URL: `https://your-public-api-url/gpt-actions-openapi.json`
- Privacy Policy URL: `https://your-public-api-url/privacy`
- 인증: `None`
- 추천 endpoint 집합: 장소, 과목, 공지, 주변 식당, 교통 안내

## 연결 후 바로 해볼 질문

- `성심교정 중앙도서관 위치 알려줘`
- `2026년 1학기 자료구조 과목 찾아줘`
- `중앙도서관 근처에서 걸어서 10분 안쪽 밥집 추천해줘`
- `최신 장학 공지 보여줘`
- `성심교정 지하철 오는 길 알려줘`

## 기대 동작

- 최초 연결 시 OAuth 링크 화면이 뜨고 Google 로그인 후 사용합니다.
- 장소, 과목, 공지, 주변 식당, 교통 안내 조회
- 프로필 생성, 시간표 저장, admin 기능은 공개 서버에서 제공하지 않음
