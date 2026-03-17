# Deploy On Render + Supabase

이 프로젝트는 저비용 공개 테스트용으로 `Render web service 2개 + Supabase Postgres 1개` 구성을 기준으로 둡니다.

## 구성

- `songsim-public-api`
  - `songsim-api`
  - 공개 landing page, `/docs`, read-only HTTP API
  - automation `ON`
- `songsim-public-mcp`
  - `songsim-mcp --transport streamable-http`
  - 공개 원격 MCP URL
  - automation `OFF`
- `Supabase`
  - 두 서비스가 함께 쓰는 Postgres

## 1. Supabase 준비

1. Supabase에서 새 프로젝트를 만듭니다.
2. Postgres 연결 문자열을 복사합니다.
3. 필요하면 SSL 옵션을 포함한 연결 문자열을 `SONGSIM_DATABASE_URL`로 사용합니다.

## 2. Render 배포

1. GitHub 저장소를 Render에 연결합니다.
2. 저장소 루트의 [render.yaml](/Users/sungjh/Projects/songsim-campus-mcp/render.yaml)을 사용해 Blueprint 배포를 만듭니다.
3. 두 서비스 모두에 아래 secret env를 채웁니다.
   - `SONGSIM_DATABASE_URL`
   - `SONGSIM_KAKAO_REST_API_KEY`
   - 공개 MCP를 OAuth로 보호할 때만 `songsim-public-mcp`에 아래 env를 추가합니다.
     - `SONGSIM_PUBLIC_MCP_AUTH_MODE=oauth`
     - `SONGSIM_MCP_OAUTH_ENABLED=true`
     - `SONGSIM_MCP_OAUTH_ISSUER=https://<your-auth0-domain>/`
     - `SONGSIM_MCP_OAUTH_AUDIENCE=https://<your-mcp-render-url>/mcp`
     - `SONGSIM_MCP_OAUTH_SCOPES=songsim.read`
4. 배포가 생성되면 실제 Render URL을 보고 아래 값을 다시 채웁니다.
   - `songsim-public-api`의 `SONGSIM_PUBLIC_HTTP_URL`
   - `songsim-public-mcp`의 `SONGSIM_PUBLIC_MCP_URL`
5. 두 서비스를 한 번 더 재배포합니다.

## 3. 권장 공개 설정

- `SONGSIM_APP_MODE=public_readonly`
- `SONGSIM_SEED_DEMO_ON_START=false`
- `SONGSIM_SYNC_OFFICIAL_ON_START=false`
- `songsim-public-api`만 `SONGSIM_AUTOMATION_ENABLED=true`
- `songsim-public-api`는 `SONGSIM_LIBRARY_SEAT_PREWARM_INTERVAL_MINUTES=5`
- `songsim-public-mcp`는 `SONGSIM_AUTOMATION_ENABLED=false`
- `songsim-public-mcp`는 기본적으로 익명 read-only
- 공개 MCP를 보호해야 하면 `SONGSIM_PUBLIC_MCP_AUTH_MODE=oauth`로 전환

## 4. 배포 후 확인

- API landing page: `https://.../`
- API docs: `https://.../docs`
- API liveness: `https://.../healthz`
- API readiness: `https://.../readyz`
- MCP endpoint: `https://.../mcp`

Render Blueprint health check는 `songsim-public-api`에서 `/healthz`를 사용합니다.
`/readyz`는 운영자 수동 확인용으로 보고, public data freshness나 DB 연결 상태를 점검할 때 별도로 확인합니다.

## 5. 주의

- Render free web service는 cold start가 생길 수 있습니다.
- Supabase free project는 장기간 무활동 시 pause될 수 있습니다.
- 공개 배포는 read-only입니다. profile/admin 경로는 숨겨집니다.
- `songsim-public-api` automation은 `snapshot`, `library_seat_prewarm`, `cache_cleanup`을 실행합니다.
- ChatGPT Actions는 HTTP API를 쓰므로 MCP OAuth와 무관합니다. MCP OAuth는 원할 때만 켜면 됩니다.
