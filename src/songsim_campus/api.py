from __future__ import annotations

import asyncio
import copy
import html
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from urllib.parse import parse_qs

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from .db import connection, get_connection, init_db
from .schemas import (
    Course,
    EstimatedEmptyClassroomResponse,
    GptNearbyRestaurantResult,
    GptNoticeResult,
    GptPlaceResult,
    MatchedCourse,
    MatchedNotice,
    McpCoordinates,
    MealRecommendationResponse,
    NearbyRestaurant,
    Notice,
    Period,
    Place,
    Profile,
    ProfileCourseRef,
    ProfileCreateRequest,
    ProfileInterests,
    ProfileNoticePreferences,
    ProfileUpdateRequest,
    Restaurant,
    TransportGuide,
)
from .seed import seed_demo
from .services import (
    InvalidRequestError,
    NotFoundError,
    create_profile,
    find_nearby_restaurants,
    get_class_periods,
    get_observability_snapshot,
    get_place,
    get_profile_course_recommendations,
    get_profile_interests,
    get_profile_meal_recommendations,
    get_profile_timetable,
    get_readiness_snapshot,
    get_sync_dashboard_state,
    list_estimated_empty_classrooms,
    list_latest_notices,
    list_profile_notices,
    list_restaurants,
    list_transport_guides,
    release_automation_leader,
    run_admin_sync,
    run_automation_tick,
    search_courses,
    search_places,
    set_automation_leader,
    set_profile_interests,
    set_profile_notice_preferences,
    set_profile_timetable,
    sync_official_snapshot,
    try_acquire_automation_leader,
    update_profile,
)
from .settings import get_settings

logger = logging.getLogger(__name__)

GPT_ACTION_PATHS: dict[str, dict[str, str]] = {
    "/places": {
        "operationId": "searchPlaces",
        "summary": "Search campus places",
        "description": (
            "Search Songsim campus places by building name, alias, or facility keyword. "
            "Use this for locations such as 중앙도서관, 베리타스관, or student facilities."
        ),
    },
    "/courses": {
        "operationId": "searchCourses",
        "summary": "Search public course offerings",
        "description": (
            "Search public Songsim course offerings by title and optional year or semester."
        ),
    },
    "/notices": {
        "operationId": "listLatestNotices",
        "summary": "List latest public notices",
        "description": "List the latest public Songsim campus notices.",
    },
    "/restaurants/nearby": {
        "operationId": "findNearbyRestaurants",
        "summary": "Find nearby restaurants",
        "description": (
            "Find walkable restaurants near a Songsim campus building or landmark."
        ),
    },
    "/transport": {
        "operationId": "listTransportGuides",
        "summary": "List transit guides",
        "description": "List public Songsim campus transit and access guides.",
    },
}

GPT_ACTION_V2_PATHS: dict[str, dict[str, str]] = {
    "/gpt/places": {
        "operationId": "searchPlacesForGpt",
        "summary": "Find campus places with concise summaries",
        "description": (
            "Use when the user asks where a Songsim campus building, landmark, or facility is. "
            "Returns concise names, aliases, short location hints, and coordinates "
            "that are easy to summarize."
        ),
    },
    "/gpt/notices": {
        "operationId": "listLatestNoticesForGpt",
        "summary": "List latest public notices with short previews",
        "description": (
            "Use when the user wants the latest Songsim public notices. "
            "Returns normalized notice categories and short summary previews."
        ),
    },
    "/gpt/restaurants/nearby": {
        "operationId": "findNearbyRestaurantsForGpt",
        "summary": "Find nearby restaurants with concise hints",
        "description": (
            "Use when the user asks for food near a Songsim campus place. "
            "Returns concise restaurant summaries with distance, walk time, price "
            "hints, and open_now."
        ),
    },
    "/gpt/classrooms/empty": {
        "operationId": "listEstimatedEmptyClassroomsForGpt",
        "summary": "Find estimated empty classrooms in a building",
        "description": (
            "Use when the user asks which classrooms are likely empty right now in a "
            "Songsim lecture building. Returns timetable-based estimated availability, "
            "not live occupancy."
        ),
    },
}

GPT_NOTICE_CATEGORY_DISPLAY = {
    "academic": "academic",
    "scholarship": "scholarship",
    "employment": "employment",
    "event": "event",
    "facility": "facility",
    "library": "library",
    "general": "general",
    "place": "general",
}

GPT_RESTAURANT_CATEGORY_DISPLAY = {
    "korean": "한식",
    "western": "양식",
    "japanese": "일식",
    "chinese": "중식",
    "cafe": "카페",
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    settings = get_settings()
    stop_event = asyncio.Event()
    automation_task: asyncio.Task[None] | None = None
    if settings.sync_official_on_start:
        with connection() as conn:
            sync_official_snapshot(conn)
    elif settings.seed_demo_on_start:
        seed_demo(force=False)
    if settings.automation_enabled:
        set_automation_leader(False)

        async def automation_loop() -> None:
            lock_conn = get_connection()
            leader = False
            try:
                while not stop_event.is_set():
                    if not leader:
                        leader = await asyncio.to_thread(try_acquire_automation_leader, lock_conn)
                        if not leader:
                            logger.info("event=automation_lock_skipped")
                    if leader:
                        await asyncio.to_thread(run_automation_tick)
                    try:
                        await asyncio.wait_for(
                            stop_event.wait(),
                            timeout=settings.automation_tick_seconds,
                        )
                    except TimeoutError:
                        continue
            finally:
                if leader:
                    await asyncio.to_thread(release_automation_leader, lock_conn)
                lock_conn.close()
                set_automation_leader(False)

        automation_task = asyncio.create_task(automation_loop(), name="songsim-automation")
    try:
        yield
    finally:
        stop_event.set()
        if automation_task is not None:
            await automation_task


def create_app() -> FastAPI:
    settings = get_settings()
    public_readonly = settings.app_mode == "public_readonly"
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

    def _truncate_preview(text: str, *, limit: int) -> str:
        normalized = " ".join(text.split())
        if len(normalized) <= limit:
            return normalized
        return normalized[: max(0, limit - 3)].rstrip() + "..."

    def _format_opening_hours_preview(opening_hours: dict[str, str]) -> str | None:
        if not opening_hours:
            return None
        preview_items = []
        for key, value in sorted(opening_hours.items()):
            preview_items.append(f"{key}: {value}")
            if len(preview_items) == 2:
                break
        return " / ".join(preview_items)

    def _restaurant_price_hint(restaurant: NearbyRestaurant) -> str | None:
        if restaurant.min_price is not None and restaurant.max_price is not None:
            if restaurant.min_price == restaurant.max_price:
                return f"{restaurant.min_price:,}원"
            return f"{restaurant.min_price:,}~{restaurant.max_price:,}원"
        if restaurant.min_price is not None:
            return f"{restaurant.min_price:,}원부터"
        if restaurant.max_price is not None:
            return f"{restaurant.max_price:,}원 이하"
        return None

    def _gpt_restaurant_category_label(restaurant: NearbyRestaurant) -> str:
        return GPT_RESTAURANT_CATEGORY_DISPLAY.get(
            restaurant.category,
            restaurant.tags[0] if restaurant.tags else "식당",
        )

    def _serialize_gpt_place(place: Place) -> dict[str, object]:
        highlights: list[str] = []
        if place.aliases:
            highlights.append(f"별칭: {', '.join(place.aliases[:3])}")
        if place.description:
            highlights.append(_truncate_preview(place.description, limit=80))
        opening_preview = _format_opening_hours_preview(place.opening_hours)
        if opening_preview:
            highlights.append(f"운영: {opening_preview}")
        coordinates = None
        if place.latitude is not None and place.longitude is not None:
            coordinates = McpCoordinates(latitude=place.latitude, longitude=place.longitude)
        return GptPlaceResult(
            name=place.name,
            canonical_name=place.name,
            aliases=place.aliases,
            category=place.category,
            short_location=place.description or None,
            coordinates=coordinates,
            highlights=highlights,
        ).model_dump(exclude_none=True)

    def _serialize_gpt_notice(notice: Notice) -> dict[str, object]:
        return GptNoticeResult(
            title=notice.title,
            category_display=GPT_NOTICE_CATEGORY_DISPLAY.get(notice.category, "general"),
            published_at=notice.published_at,
            summary=_truncate_preview(notice.summary, limit=120),
            source_url=notice.source_url,
        ).model_dump(exclude_none=True)

    def _serialize_gpt_nearby_restaurant(restaurant: NearbyRestaurant) -> dict[str, object]:
        return GptNearbyRestaurantResult(
            name=restaurant.name,
            category_display=_gpt_restaurant_category_label(restaurant),
            distance_meters=restaurant.distance_meters,
            estimated_walk_minutes=restaurant.estimated_walk_minutes,
            price_hint=_restaurant_price_hint(restaurant),
            open_now=restaurant.open_now,
            location_hint=(
                _truncate_preview(restaurant.description, limit=80)
                if restaurant.description
                else None
            ),
        ).model_dump()

    def _build_filtered_openapi(
        request: Request,
        *,
        title: str,
        description: str,
        path_metadata: dict[str, dict[str, str]],
    ) -> dict[str, object]:
        source_spec = copy.deepcopy(app.openapi())
        public_http_url = settings.public_http_url or str(request.base_url).rstrip("/")
        filtered_paths: dict[str, object] = {}
        for path, metadata in path_metadata.items():
            operation = copy.deepcopy(source_spec["paths"][path]["get"])
            operation["operationId"] = metadata["operationId"]
            operation["summary"] = metadata["summary"]
            operation["description"] = metadata["description"]
            filtered_paths[path] = {"get": operation}
        return {
            "openapi": source_spec["openapi"],
            "info": {
                "title": title,
                "version": source_spec["info"]["version"],
                "description": description,
            },
            "servers": [{"url": public_http_url}],
            "paths": filtered_paths,
            "components": source_spec.get("components", {}),
        }

    def build_gpt_actions_openapi(request: Request) -> dict[str, object]:
        return _build_filtered_openapi(
            request,
            title="Songsim Campus GPT Actions",
            description="Slimmed-down read-only actions schema for ChatGPT GPT Actions.",
            path_metadata=GPT_ACTION_PATHS,
        )

    def build_gpt_actions_openapi_v2(request: Request) -> dict[str, object]:
        return _build_filtered_openapi(
            request,
            title="Songsim Campus GPT Actions v2",
            description=(
                "GPT-focused actions schema with concise place, notice, and nearby "
                "restaurant responses."
            ),
            path_metadata=GPT_ACTION_V2_PATHS,
        )

    def ensure_admin_request_allowed(request: Request) -> None:
        client_host = request.client.host if request.client else ""
        if client_host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
            raise HTTPException(
                status_code=403,
                detail="Admin dashboard is only available from loopback clients.",
            )

    def render_admin_sync_page(state: dict[str, object]) -> str:
        datasets = state["datasets"]
        recent_runs = state["recent_runs"]
        automation = state["automation"]

        def render_field(name: str, label: str, value: str = "") -> str:
            return (
                f'<label><span>{html.escape(label)}</span>'
                f'<input type="text" name="{html.escape(name)}" '
                f'value="{html.escape(value)}"></label>'
            )

        forms = [
            {
                "title": "snapshot",
                "fields": [
                    render_field("campus", "campus", settings.official_campus_id),
                    render_field(
                        "year",
                        "year",
                        str(settings.official_course_year or ""),
                    ),
                    render_field(
                        "semester",
                        "semester",
                        str(settings.official_course_semester or ""),
                    ),
                    render_field(
                        "notice_pages",
                        "notice_pages",
                        str(settings.official_notice_pages),
                    ),
                ],
            },
            {
                "title": "places",
                "fields": [render_field("campus", "campus", settings.official_campus_id)],
            },
            {"title": "library_hours", "fields": []},
            {"title": "facility_hours", "fields": []},
            {
                "title": "courses",
                "fields": [
                    render_field(
                        "year",
                        "year",
                        str(settings.official_course_year or ""),
                    ),
                    render_field(
                        "semester",
                        "semester",
                        str(settings.official_course_semester or ""),
                    ),
                ],
            },
            {
                "title": "notices",
                "fields": [
                    render_field(
                        "notice_pages",
                        "notice_pages",
                        str(settings.official_notice_pages),
                    )
                ],
            },
            {"title": "transport_guides", "fields": []},
        ]

        dataset_cards = "".join(
            (
                "<article class='card'>"
                f"<h3>{html.escape(str(item['name']))}</h3>"
                f"<p class='count'>{int(item['row_count'])}</p>"
                "<p class='meta'>last_synced_at: "
                f"{html.escape(str(item['last_synced_at'] or '-'))}</p>"
                "</article>"
            )
            for item in datasets
        )
        automation_rows = "".join(
            (
                "<tr>"
                f"<td>{html.escape(job.name)}</td>"
                f"<td>{job.interval_minutes}</td>"
                f"<td>{html.escape(str(job.last_run_at or '-'))}</td>"
                f"<td>{html.escape(str(job.last_status or '-'))}</td>"
                f"<td>{html.escape(str(job.next_due_at or '-'))}</td>"
                "</tr>"
            )
            for job in automation.jobs
        ) or "<tr><td colspan='5'>No automation jobs configured.</td></tr>"
        forms_html = "".join(
            (
                "<form method='post' action='/admin/sync/run' class='card sync-form'>"
                f"<h3>{html.escape(form['title'])}</h3>"
                f"<input type='hidden' name='target' value='{html.escape(form['title'])}'>"
                f"{''.join(form['fields'])}"
                "<button type='submit'>Run</button>"
                "</form>"
            )
            for form in forms
        )
        runs_html = "".join(
            (
                "<tr>"
                f"<td>{run.id}</td>"
                f"<td>{html.escape(run.target)}</td>"
                f"<td>{html.escape(run.status)}</td>"
                f"<td><code>{html.escape(json.dumps(run.params, ensure_ascii=False))}</code></td>"
                f"<td><code>{html.escape(json.dumps(run.summary, ensure_ascii=False))}</code></td>"
                f"<td>{html.escape(run.error_text or '-')}</td>"
                f"<td>{html.escape(run.started_at)}</td>"
                f"<td>{html.escape(run.finished_at or '-')}</td>"
                "</tr>"
            )
            for run in recent_runs
        ) or (
            "<tr><td colspan='8'>No sync runs yet.</td></tr>"
        )
        return f"""
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Songsim Admin Sync</title>
    <style>
      :root {{
        color-scheme: light;
        --bg: #f5f1e7;
        --surface: #fffdf8;
        --ink: #162126;
        --muted: #5f6b6f;
        --line: #d5ccb6;
        --accent: #1c7c54;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        font-family: Georgia, "Noto Serif KR", serif;
        background:
          radial-gradient(circle at top left, rgba(28,124,84,0.08), transparent 30%),
          linear-gradient(180deg, #f9f4ea 0%, var(--bg) 100%);
        color: var(--ink);
      }}
      main {{ max-width: 1080px; margin: 0 auto; padding: 32px 20px 48px; }}
      h1 {{ margin: 0 0 8px; font-size: 2.2rem; }}
      p.lead {{ margin: 0 0 24px; color: var(--muted); }}
      .grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 14px;
      }}
      .card {{
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 16px;
        padding: 16px;
        box-shadow: 0 12px 30px rgba(22,33,38,0.06);
      }}
      .count {{ font-size: 2rem; margin: 8px 0 6px; }}
      .meta {{ color: var(--muted); font-size: 0.92rem; }}
      section {{ margin-top: 28px; }}
      .forms {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 14px;
      }}
      .sync-form {{
        display: flex;
        flex-direction: column;
        gap: 10px;
      }}
      label {{ display: flex; flex-direction: column; gap: 6px; font-size: 0.92rem; }}
      input {{
        padding: 10px 12px;
        border-radius: 10px;
        border: 1px solid var(--line);
        background: white;
      }}
      button {{
        margin-top: auto;
        border: 0;
        border-radius: 999px;
        padding: 10px 14px;
        background: var(--accent);
        color: white;
        font-weight: 700;
        cursor: pointer;
      }}
      table {{
        width: 100%;
        border-collapse: collapse;
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 16px;
        overflow: hidden;
      }}
      th, td {{
        padding: 12px;
        border-bottom: 1px solid #ebe3d1;
        text-align: left;
        vertical-align: top;
        font-size: 0.92rem;
      }}
      th {{ background: #f0e8d4; }}
      code {{ white-space: pre-wrap; word-break: break-word; }}
    </style>
  </head>
  <body>
    <main>
      <h1>Songsim Admin Sync</h1>
      <p class="lead">
        Run official syncs from the browser and inspect the latest results.
        <a href="/admin/observability">Open observability</a>
      </p>
      <section>
        <h2>Dataset Status</h2>
        <div class="grid">{dataset_cards}</div>
      </section>
      <section>
        <h2>Automation Status</h2>
        <p class="meta">
          enabled: {'yes' if automation.enabled else 'no'} · leader:
          {'yes' if automation.leader else 'no'}
        </p>
        <table>
          <thead>
            <tr>
              <th>job</th>
              <th>interval_minutes</th>
              <th>last_run_at</th>
              <th>last_status</th>
              <th>next_due_at</th>
            </tr>
          </thead>
          <tbody>{automation_rows}</tbody>
        </table>
      </section>
      <section>
        <h2>Run Sync</h2>
        <div class="forms">{forms_html}</div>
      </section>
      <section>
        <h2>Recent Runs</h2>
        <table>
          <thead>
            <tr>
              <th>id</th>
              <th>target</th>
              <th>status</th>
              <th>params</th>
              <th>summary</th>
              <th>error</th>
              <th>started_at</th>
              <th>finished_at</th>
            </tr>
          </thead>
          <tbody>{runs_html}</tbody>
        </table>
      </section>
    </main>
  </body>
</html>
"""

    def render_landing_page(request: Request) -> str:
        public_http_url = settings.public_http_url or str(request.base_url).rstrip("/")
        docs_url = f"{public_http_url}/docs"
        privacy_url = f"{public_http_url}/privacy"
        mcp_url = (
            settings.public_mcp_url
            or "Set SONGSIM_PUBLIC_MCP_URL to show the public MCP URL."
        )
        oauth_enabled = (
            settings.app_mode == "public_readonly" and settings.mcp_oauth_enabled
        )
        example_prompts = [
            "성심교정 중앙도서관 위치 알려줘",
            "2026년 1학기 객체지향 과목 찾아줘",
            "니콜스관인데 지금 예상 빈 강의실 있어?",
            "중앙도서관 근처 밥집 추천해줘",
            "최신 장학 공지 보여줘",
            "성심교정 지하철 오는 길 알려줘",
            "도보 10분 안쪽 카페만 보여줘",
        ]
        product_mode = "Public Read-only" if public_readonly else "Local Full"
        admin_link = (
            '<a class="pill" href="/admin/sync">Admin Sync</a>'
            if settings.admin_enabled and not public_readonly
            else ""
        )
        examples_html = "".join(
            f"<li>{html.escape(prompt)}</li>"
            for prompt in example_prompts
        )
        return f"""
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Songsim Campus MCP</title>
    <style>
      :root {{
        color-scheme: light;
        --bg: #f5f1e7;
        --surface: #fffdf8;
        --ink: #162126;
        --muted: #5f6b6f;
        --line: #d5ccb6;
        --accent: #174f7a;
        --accent-2: #1c7c54;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        font-family: Georgia, "Noto Serif KR", serif;
        background:
          radial-gradient(circle at top left, rgba(23,79,122,0.08), transparent 32%),
          linear-gradient(180deg, #faf5ea 0%, var(--bg) 100%);
        color: var(--ink);
      }}
      main {{ max-width: 1080px; margin: 0 auto; padding: 36px 20px 56px; }}
      h1 {{ margin: 0 0 10px; font-size: 2.4rem; }}
      p.lead {{ margin: 0 0 24px; color: var(--muted); font-size: 1.04rem; }}
      .hero {{
        display: grid;
        grid-template-columns: 1.4fr 1fr;
        gap: 18px;
        align-items: stretch;
      }}
      .card {{
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 18px;
        box-shadow: 0 12px 30px rgba(22,33,38,0.06);
      }}
      .meta {{ color: var(--muted); font-size: 0.92rem; }}
      .pill {{
        display: inline-flex;
        align-items: center;
        border-radius: 999px;
        padding: 8px 12px;
        background: #eaf2f7;
        color: var(--accent);
        text-decoration: none;
        font-weight: 700;
        margin-right: 8px;
      }}
      .primary {{ background: var(--accent-2); color: white; }}
      code {{
        display: block;
        padding: 12px;
        border-radius: 12px;
        background: #f3efe5;
        border: 1px solid #e0d6bf;
        overflow-x: auto;
        white-space: pre-wrap;
        word-break: break-word;
      }}
      ul {{ margin: 12px 0 0; padding-left: 18px; }}
      section {{ margin-top: 28px; }}
      .grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
        gap: 14px;
      }}
      @media (max-width: 800px) {{
        .hero {{ grid-template-columns: 1fr; }}
      }}
    </style>
  </head>
  <body>
    <main>
      <h1>Songsim Campus MCP</h1>
      <p class="lead">
        Verified Catholic University Songsim campus data server for places, courses,
        notices, restaurants, and transit. The remote MCP endpoint is the primary
        public product surface, and the HTTP API is the thin companion layer.
      </p>
      <div class="hero">
        <section class="card">
          <p class="meta">Mode: {html.escape(product_mode)}</p>
          <p>
            This server exposes verified Songsim campus data through a remote read-only MCP
            endpoint for ChatGPT, Claude, and Codex-style clients, plus a companion HTTP API
            for direct integrations and GPT Actions.
          </p>
          <p class="meta">
            {
              (
                "Remote MCP access is the core public interface and requires "
                "OAuth login via Auth0 and Google login."
              )
              if oauth_enabled
              else (
                "Remote MCP access is the core public interface and is currently "
                "configured without OAuth."
              )
            }
          </p>
          <p>
            <a class="pill primary" href="{html.escape(docs_url)}">Open API Docs</a>
            <a class="pill" href="/openapi.json">OpenAPI JSON</a>
            <a class="pill" href="/gpt-actions-openapi-v2.json">GPT Actions OpenAPI v2</a>
            <a class="pill" href="/gpt-actions-openapi.json">GPT Actions OpenAPI v1</a>
            <a class="pill" href="{html.escape(privacy_url)}">Privacy Policy</a>
            {admin_link}
          </p>
        </section>
        <section class="card">
          <h2>Public URLs</h2>
          <p class="meta">Remote MCP</p>
          <code>{html.escape(mcp_url)}</code>
          <p class="meta">HTTP API</p>
          <code>{html.escape(public_http_url)}</code>
        </section>
      </div>
      <section class="grid">
        <article class="card">
          <h2>What To Ask</h2>
          <ul>{examples_html}</ul>
        </article>
        <article class="card">
          <h2>MCP-Backed HTTP Endpoints</h2>
          <ul>
            <li><code>/places</code> campus places and landmarks</li>
            <li><code>/courses</code> public course offerings</li>
            <li><code>/classrooms/empty</code> timetable-based estimated empty classrooms</li>
            <li><code>/restaurants/nearby</code> walkable food recommendations</li>
            <li><code>/notices</code> latest public campus notices</li>
            <li><code>/transport</code> Songsim transit guides</li>
            <li><code>/gpt/*</code> concise GPT-friendly summaries for shared GPT actions</li>
          </ul>
        </article>
        <article class="card">
          <h2>Remote MCP Pattern</h2>
          <ul>
            <li>Read <code>songsim://usage-guide</code> for the public MCP rules</li>
            <li>
              Use prompts to pick the first tool for places, empty classrooms,
              notices, restaurants, or transport
            </li>
            <li>Call tools after the prompt narrows the correct public read-only flow</li>
          </ul>
        </article>
      </section>
    </main>
  </body>
</html>
"""

    def render_privacy_page(request: Request) -> str:
        public_http_url = settings.public_http_url or str(request.base_url).rstrip("/")
        return f"""
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Songsim Campus Privacy Policy</title>
    <style>
      :root {{
        color-scheme: light;
        --bg: #f5f1e7;
        --surface: #fffdf8;
        --ink: #162126;
        --muted: #5f6b6f;
        --line: #d5ccb6;
        --accent: #174f7a;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        font-family: Georgia, "Noto Serif KR", serif;
        background:
          radial-gradient(circle at top left, rgba(23,79,122,0.08), transparent 30%),
          linear-gradient(180deg, #f9f4ea 0%, var(--bg) 100%);
        color: var(--ink);
      }}
      main {{ max-width: 920px; margin: 0 auto; padding: 36px 20px 56px; }}
      .card {{
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 20px;
        box-shadow: 0 12px 30px rgba(22,33,38,0.06);
      }}
      h1 {{ margin: 0 0 10px; font-size: 2.2rem; }}
      h2 {{ margin-top: 28px; }}
      p, li {{ line-height: 1.65; }}
      .meta {{ color: var(--muted); }}
      code {{
        display: inline-block;
        padding: 2px 6px;
        border-radius: 8px;
        background: #f3efe5;
        border: 1px solid #e0d6bf;
      }}
      a {{ color: var(--accent); }}
    </style>
  </head>
  <body>
    <main>
      <article class="card">
        <h1>Songsim Campus Privacy Policy</h1>
        <p class="meta">
          Effective date: 2026-03-14 · Service: Songsim Campus HTTP API,
          ChatGPT Actions, and Remote MCP
        </p>

        <h2>1. What this service does</h2>
        <p>
          Songsim Campus provides read-only access to Catholic University
          Songsim campus information such as
          places, public courses, notices, nearby restaurants, and transport guides.
        </p>

        <h2>2. Data we process</h2>
        <ul>
          <li>
            Request metadata needed to operate the service, such as timestamps,
            endpoint usage, and basic server logs.
          </li>
          <li>
            Query values you send to the API, ChatGPT Actions, or Remote MCP,
            such as place names or course search terms.
          </li>
          <li>
            Cached restaurant lookups from Kakao Local and Kakao place detail
            pages to improve response quality.
          </li>
        </ul>

        <h2>3. What we do not collect intentionally</h2>
        <ul>
          <li>We do not require account creation for the public read-only API.</li>
          <li>
            We do not intentionally collect sensitive personal information
            through the public API or ChatGPT Actions.
          </li>
          <li>We do not sell personal data.</li>
        </ul>

        <h2>4. Third-party services</h2>
        <ul>
          <li>Render is used for hosting the public application services.</li>
          <li>Supabase PostgreSQL is used for persistent storage.</li>
          <li>
            Kakao Local and Kakao place detail sources may be used to provide
            nearby restaurant data and opening hours.
          </li>
          <li>Auth0 and Google login may be used for Remote MCP OAuth access.</li>
          <li>
            ChatGPT Actions may send your requests to this API when you use a
            published GPT.
          </li>
        </ul>

        <h2>5. Retention</h2>
        <p>
          Operational logs and caches may be retained for debugging,
          observability, and service quality improvement.
          Cached restaurant and hours data are periodically cleaned up by automation jobs.
        </p>

        <h2>6. Contact</h2>
        <p>
          For issues related to this deployment, refer to the public service root at
          <a href="{html.escape(public_http_url)}">{html.escape(public_http_url)}</a>.
        </p>
      </article>
    </main>
  </body>
</html>
"""

    def render_admin_observability_page(state: dict[str, object]) -> str:
        readiness = state["readiness"]
        observability = state["observability"]
        cache = observability["cache"]
        sync = observability["sync"]
        automation = observability["automation"]
        dataset_cards = "".join(
            (
                "<article class='card'>"
                f"<h3>{html.escape(str(item['name']))}</h3>"
                f"<p class='count'>{int(item['row_count'])}</p>"
                "<p class='meta'>last_synced_at: "
                f"{html.escape(str(item['last_synced_at'] or '-'))}</p>"
                "</article>"
            )
            for item in observability["datasets"]
        )
        cache_rows = "".join(
            (
                "<tr>"
                f"<td>{html.escape(str(event['decision']))}</td>"
                f"<td>{html.escape(str(event['origin_slug']))}</td>"
                f"<td>{html.escape(str(event['kakao_query']))}</td>"
                f"<td>{html.escape(str(event['radius_meters']))}</td>"
                f"<td>{html.escape(str(event['error_text'] or '-'))}</td>"
                f"<td>{html.escape(str(event['occurred_at']))}</td>"
                "</tr>"
            )
            for event in cache["recent_events"]
        ) or "<tr><td colspan='6'>No cache events yet.</td></tr>"
        sync_rows = "".join(
            (
                "<tr>"
                f"<td>{html.escape(str(event['target']))}</td>"
                f"<td>{html.escape(str(event['status']))}</td>"
                f"<td>{html.escape(str(event['duration_ms']))}</td>"
                "<td><code>"
                f"{html.escape(json.dumps(event['summary'], ensure_ascii=False))}"
                "</code></td>"
                f"<td>{html.escape(str(event['error_text'] or '-'))}</td>"
                f"<td>{html.escape(str(event['finished_at']))}</td>"
                "</tr>"
            )
            for event in sync["recent_events"]
        ) or "<tr><td colspan='6'>No sync events yet.</td></tr>"
        run_rows = "".join(
            (
                "<tr>"
                f"<td>{run['id']}</td>"
                f"<td>{html.escape(str(run['target']))}</td>"
                f"<td>{html.escape(str(run['status']))}</td>"
                f"<td>{html.escape(str(run['started_at']))}</td>"
                f"<td>{html.escape(str(run['finished_at'] or '-'))}</td>"
                "</tr>"
            )
            for run in observability["recent_sync_runs"]
        ) or "<tr><td colspan='5'>No sync run history yet.</td></tr>"
        readiness_rows = "".join(
            (
                "<tr>"
                f"<td>{html.escape(name)}</td>"
                f"<td>{'yes' if item['ok'] else 'no'}</td>"
                f"<td>{html.escape(str(item.get('row_count', '-')))}</td>"
                f"<td>{html.escape(str(item.get('last_synced_at', '-')))}</td>"
                f"<td>{html.escape(str(item.get('error') or '-'))}</td>"
                "</tr>"
            )
            for name, item in readiness["tables"].items()
        )
        automation_rows = "".join(
            (
                "<tr>"
                f"<td>{html.escape(str(job['name']))}</td>"
                f"<td>{html.escape(str(job['interval_minutes']))}</td>"
                f"<td>{html.escape(str(job['last_run_at'] or '-'))}</td>"
                f"<td>{html.escape(str(job['last_status'] or '-'))}</td>"
                f"<td>{html.escape(str(job['next_due_at'] or '-'))}</td>"
                "</tr>"
            )
            for job in automation["jobs"]
        ) or "<tr><td colspan='5'>No automation jobs configured.</td></tr>"
        return f"""
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Songsim Observability</title>
    <style>
      :root {{
        color-scheme: light;
        --bg: #f5f1e7;
        --surface: #fffdf8;
        --ink: #162126;
        --muted: #5f6b6f;
        --line: #d5ccb6;
        --accent: #174f7a;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        font-family: Georgia, "Noto Serif KR", serif;
        background:
          radial-gradient(circle at top left, rgba(23,79,122,0.08), transparent 30%),
          linear-gradient(180deg, #f9f4ea 0%, var(--bg) 100%);
        color: var(--ink);
      }}
      main {{ max-width: 1080px; margin: 0 auto; padding: 32px 20px 48px; }}
      h1 {{ margin: 0 0 8px; font-size: 2.2rem; }}
      p.lead {{ margin: 0 0 24px; color: var(--muted); }}
      .grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 14px;
      }}
      .card {{
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 16px;
        padding: 16px;
        box-shadow: 0 12px 30px rgba(22,33,38,0.06);
      }}
      .count {{ font-size: 2rem; margin: 8px 0 6px; }}
      .meta {{ color: var(--muted); font-size: 0.92rem; }}
      section {{ margin-top: 28px; }}
      table {{
        width: 100%;
        border-collapse: collapse;
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 16px;
        overflow: hidden;
      }}
      th, td {{
        padding: 12px;
        border-bottom: 1px solid #ebe3d1;
        text-align: left;
        vertical-align: top;
        font-size: 0.92rem;
      }}
      th {{ background: #f0e8d4; }}
      code {{ white-space: pre-wrap; word-break: break-word; }}
      .nav {{ display: flex; gap: 12px; margin-bottom: 16px; }}
      .pill {{
        display: inline-flex;
        align-items: center;
        border-radius: 999px;
        padding: 8px 12px;
        background: #eaf2f7;
        color: var(--accent);
        text-decoration: none;
        font-weight: 700;
      }}
    </style>
  </head>
  <body>
    <main>
      <div class="nav">
        <a class="pill" href="/admin/sync">Admin Sync</a>
        <a class="pill" href="/admin/observability.json">JSON</a>
      </div>
      <h1>Songsim Observability</h1>
      <p class="lead">
        healthz: ok · readyz: {'ok' if readiness['ok'] else 'degraded'} · process_started_at:
        {html.escape(str(observability['process_started_at']))}
      </p>
      <section>
        <h2>Datasets</h2>
        <div class="grid">{dataset_cards}</div>
      </section>
      <section>
        <h2>Readiness</h2>
        <table>
          <thead>
            <tr>
              <th>check</th>
              <th>ok</th>
              <th>row_count</th>
              <th>last_synced_at</th>
              <th>error</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>database</td>
              <td>{'yes' if readiness['database']['ok'] else 'no'}</td>
              <td>-</td>
              <td>-</td>
              <td>{html.escape(str(readiness['database']['error'] or '-'))}</td>
            </tr>
            {readiness_rows}
          </tbody>
        </table>
      </section>
      <section>
        <h2>Automation</h2>
        <p class="meta">
          enabled: {'yes' if automation['enabled'] else 'no'} · leader:
          {'yes' if automation['leader'] else 'no'}
        </p>
        <table>
          <thead>
            <tr>
              <th>job</th>
              <th>interval_minutes</th>
              <th>last_run_at</th>
              <th>last_status</th>
              <th>next_due_at</th>
            </tr>
          </thead>
          <tbody>{automation_rows}</tbody>
        </table>
      </section>
      <section>
        <h2>Cache Counters</h2>
        <div class="grid">
          <article class="card">
            <h3>fresh_hit</h3>
            <p class="count">{cache['fresh_hit']}</p>
          </article>
          <article class="card">
            <h3>stale_hit</h3>
            <p class="count">{cache['stale_hit']}</p>
          </article>
          <article class="card">
            <h3>live_fetch_success</h3>
            <p class="count">{cache['live_fetch_success']}</p>
          </article>
          <article class="card">
            <h3>live_fetch_error</h3>
            <p class="count">{cache['live_fetch_error']}</p>
          </article>
          <article class="card">
            <h3>local_fallback</h3>
            <p class="count">{cache['local_fallback']}</p>
          </article>
          <article class="card">
            <h3>restaurant_hours_fresh_hit</h3>
            <p class="count">{cache['restaurant_hours_fresh_hit']}</p>
          </article>
          <article class="card">
            <h3>restaurant_hours_stale_hit</h3>
            <p class="count">{cache['restaurant_hours_stale_hit']}</p>
          </article>
          <article class="card">
            <h3>restaurant_hours_live_fetch_success</h3>
            <p class="count">{cache['restaurant_hours_live_fetch_success']}</p>
          </article>
          <article class="card">
            <h3>restaurant_hours_live_fetch_error</h3>
            <p class="count">{cache['restaurant_hours_live_fetch_error']}</p>
          </article>
        </div>
      </section>
      <section>
        <h2>Recent Cache Events</h2>
        <table>
          <thead>
            <tr>
              <th>decision</th>
              <th>origin</th>
              <th>query</th>
              <th>radius</th>
              <th>error</th>
              <th>occurred_at</th>
            </tr>
          </thead>
          <tbody>{cache_rows}</tbody>
        </table>
      </section>
      <section>
        <h2>Recent Sync Events</h2>
        <p class="meta">
          last_failure: {html.escape(str(sync['last_failure_message'] or '-'))}
          at {html.escape(str(sync['last_failure_at'] or '-'))}
        </p>
        <table>
          <thead>
            <tr>
              <th>target</th>
              <th>status</th>
              <th>duration_ms</th>
              <th>summary</th>
              <th>error</th>
              <th>finished_at</th>
            </tr>
          </thead>
          <tbody>{sync_rows}</tbody>
        </table>
      </section>
      <section>
        <h2>Recent Sync Runs</h2>
        <table>
          <thead>
            <tr>
              <th>id</th>
              <th>target</th>
              <th>status</th>
              <th>started_at</th>
              <th>finished_at</th>
            </tr>
          </thead>
          <tbody>{run_rows}</tbody>
        </table>
      </section>
    </main>
  </body>
</html>
"""

    @app.get("/healthz")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/", response_class=HTMLResponse)
    def landing(request: Request) -> HTMLResponse:
        return HTMLResponse(render_landing_page(request))

    @app.get("/privacy", response_class=HTMLResponse)
    def privacy(request: Request) -> HTMLResponse:
        return HTMLResponse(render_privacy_page(request))

    @app.get("/readyz")
    def ready() -> dict[str, object]:
        return get_readiness_snapshot()

    @app.get("/gpt-actions-openapi.json")
    def gpt_actions_openapi(request: Request) -> JSONResponse:
        return JSONResponse(build_gpt_actions_openapi(request))

    @app.get("/gpt-actions-openapi-v2.json")
    def gpt_actions_openapi_v2(request: Request) -> JSONResponse:
        return JSONResponse(build_gpt_actions_openapi_v2(request))

    @app.get("/periods", response_model=list[Period])
    def periods() -> list[Period]:
        return get_class_periods()

    @app.get("/gpt/places", response_model=list[GptPlaceResult])
    def gpt_places(
        query: str = Query(default="", description="건물/시설/도서관 검색어"),
        category: str | None = Query(default=None),
        limit: int = Query(default=10, ge=1, le=50),
    ) -> list[GptPlaceResult]:
        with connection() as conn:
            places = search_places(conn, query=query, category=category, limit=limit)
        return [GptPlaceResult.model_validate(_serialize_gpt_place(place)) for place in places]

    @app.get("/gpt/notices", response_model=list[GptNoticeResult])
    def gpt_notices(
        category: str | None = Query(default=None),
        limit: int = Query(default=10, ge=1, le=50),
    ) -> list[GptNoticeResult]:
        with connection() as conn:
            notices = list_latest_notices(conn, category=category, limit=limit)
        return [GptNoticeResult.model_validate(_serialize_gpt_notice(notice)) for notice in notices]

    @app.get("/gpt/restaurants/nearby", response_model=list[GptNearbyRestaurantResult])
    def gpt_restaurants_nearby(
        origin: str = Query(description="출발 건물 slug 또는 이름"),
        at: datetime | None = Query(default=None),
        category: str | None = Query(default=None),
        budget_max: int | None = Query(default=None, ge=0),
        open_now: bool = Query(default=False),
        walk_minutes: int = Query(default=15, ge=1, le=60),
        limit: int = Query(default=10, ge=1, le=50),
    ) -> list[GptNearbyRestaurantResult]:
        with connection() as conn:
            try:
                restaurants = find_nearby_restaurants(
                    conn,
                    origin=origin,
                    at=at,
                    category=category,
                    budget_max=budget_max,
                    open_now=open_now,
                    walk_minutes=walk_minutes,
                    limit=limit,
                )
            except NotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except InvalidRequestError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        return [
            GptNearbyRestaurantResult.model_validate(
                _serialize_gpt_nearby_restaurant(restaurant)
            )
            for restaurant in restaurants
        ]

    @app.get("/gpt/classrooms/empty", response_model=EstimatedEmptyClassroomResponse)
    def gpt_empty_classrooms(
        building: str = Query(description="강의실을 확인할 건물 slug, 대표 이름, 또는 alias"),
        at: datetime | None = Query(default=None),
        year: int | None = Query(default=None),
        semester: int | None = Query(default=None),
        limit: int = Query(default=10, ge=1, le=50),
    ) -> EstimatedEmptyClassroomResponse:
        with connection() as conn:
            try:
                return list_estimated_empty_classrooms(
                    conn,
                    building=building,
                    at=at,
                    year=year,
                    semester=semester,
                    limit=limit,
                )
            except NotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except InvalidRequestError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/places", response_model=list[Place])
    def places(
        query: str = Query(default="", description="건물/시설/도서관 검색어"),
        category: str | None = Query(default=None),
        limit: int = Query(default=10, ge=1, le=50),
    ) -> list[Place]:
        with connection() as conn:
            return search_places(conn, query=query, category=category, limit=limit)

    @app.get("/places/{identifier}", response_model=Place)
    def place_detail(identifier: str) -> Place:
        with connection() as conn:
            try:
                return get_place(conn, identifier)
            except NotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/courses", response_model=list[Course])
    def courses(
        query: str = Query(default=""),
        year: int | None = Query(default=None),
        semester: int | None = Query(default=None),
        limit: int = Query(default=20, ge=1, le=50),
    ) -> list[Course]:
        with connection() as conn:
            return search_courses(conn, query=query, year=year, semester=semester, limit=limit)

    @app.get("/restaurants", response_model=list[Restaurant])
    def restaurants() -> list[Restaurant]:
        with connection() as conn:
            return list_restaurants(conn)

    @app.get("/restaurants/nearby", response_model=list[NearbyRestaurant])
    def restaurants_nearby(
        origin: str = Query(description="출발 건물 slug 또는 이름"),
        at: datetime | None = Query(default=None),
        category: str | None = Query(default=None),
        budget_max: int | None = Query(default=None, ge=0),
        open_now: bool = Query(default=False),
        walk_minutes: int = Query(default=15, ge=1, le=60),
        limit: int = Query(default=10, ge=1, le=50),
    ) -> list[NearbyRestaurant]:
        with connection() as conn:
            try:
                return find_nearby_restaurants(
                    conn,
                    origin=origin,
                    at=at,
                    category=category,
                    budget_max=budget_max,
                    open_now=open_now,
                    walk_minutes=walk_minutes,
                    limit=limit,
                )
            except NotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except InvalidRequestError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/classrooms/empty", response_model=EstimatedEmptyClassroomResponse)
    def classrooms_empty(
        building: str = Query(description="강의실을 확인할 건물 slug, 대표 이름, 또는 alias"),
        at: datetime | None = Query(default=None),
        year: int | None = Query(default=None),
        semester: int | None = Query(default=None),
        limit: int = Query(default=10, ge=1, le=50),
    ) -> EstimatedEmptyClassroomResponse:
        with connection() as conn:
            try:
                return list_estimated_empty_classrooms(
                    conn,
                    building=building,
                    at=at,
                    year=year,
                    semester=semester,
                    limit=limit,
                )
            except NotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except InvalidRequestError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/notices", response_model=list[Notice])
    def notices(
        category: str | None = Query(default=None),
        limit: int = Query(default=10, ge=1, le=50),
    ) -> list[Notice]:
        with connection() as conn:
            return list_latest_notices(conn, category=category, limit=limit)

    @app.get("/transport", response_model=list[TransportGuide])
    def transport(
        mode: str | None = Query(default=None),
        limit: int = Query(default=20, ge=1, le=50),
    ) -> list[TransportGuide]:
        with connection() as conn:
            return list_transport_guides(conn, mode=mode, limit=limit)

    if not public_readonly:
        @app.post("/profiles", response_model=Profile)
        def create_profile_endpoint(payload: ProfileCreateRequest | None = None) -> Profile:
            with connection() as conn:
                return create_profile(
                    conn,
                    display_name=(payload.display_name if payload else ""),
                )

        @app.patch("/profiles/{profile_id}", response_model=Profile)
        def update_profile_endpoint(
            profile_id: str,
            payload: ProfileUpdateRequest,
        ) -> Profile:
            with connection() as conn:
                try:
                    return update_profile(conn, profile_id, payload)
                except NotFoundError as exc:
                    raise HTTPException(status_code=404, detail=str(exc)) from exc
                except InvalidRequestError as exc:
                    raise HTTPException(status_code=400, detail=str(exc)) from exc

        @app.put("/profiles/{profile_id}/timetable", response_model=list[Course])
        def set_profile_timetable_endpoint(
            profile_id: str,
            courses: list[ProfileCourseRef],
        ) -> list[Course]:
            with connection() as conn:
                try:
                    return set_profile_timetable(conn, profile_id, courses)
                except NotFoundError as exc:
                    raise HTTPException(status_code=404, detail=str(exc)) from exc
                except InvalidRequestError as exc:
                    raise HTTPException(status_code=400, detail=str(exc)) from exc

        @app.get("/profiles/{profile_id}/timetable", response_model=list[Course])
        def get_profile_timetable_endpoint(
            profile_id: str,
            year: int | None = Query(default=None),
            semester: int | None = Query(default=None),
        ) -> list[Course]:
            with connection() as conn:
                try:
                    return get_profile_timetable(conn, profile_id, year=year, semester=semester)
                except NotFoundError as exc:
                    raise HTTPException(status_code=404, detail=str(exc)) from exc

        @app.put(
            "/profiles/{profile_id}/notice-preferences",
            response_model=ProfileNoticePreferences,
        )
        def set_profile_notice_preferences_endpoint(
            profile_id: str,
            preferences: ProfileNoticePreferences,
        ) -> ProfileNoticePreferences:
            with connection() as conn:
                try:
                    return set_profile_notice_preferences(conn, profile_id, preferences)
                except NotFoundError as exc:
                    raise HTTPException(status_code=404, detail=str(exc)) from exc
                except InvalidRequestError as exc:
                    raise HTTPException(status_code=400, detail=str(exc)) from exc

        @app.put("/profiles/{profile_id}/interests", response_model=ProfileInterests)
        def set_profile_interests_endpoint(
            profile_id: str,
            interests: ProfileInterests,
        ) -> ProfileInterests:
            with connection() as conn:
                try:
                    return set_profile_interests(conn, profile_id, interests)
                except NotFoundError as exc:
                    raise HTTPException(status_code=404, detail=str(exc)) from exc
                except InvalidRequestError as exc:
                    raise HTTPException(status_code=400, detail=str(exc)) from exc

        @app.get("/profiles/{profile_id}/interests", response_model=ProfileInterests)
        def get_profile_interests_endpoint(profile_id: str) -> ProfileInterests:
            with connection() as conn:
                try:
                    return get_profile_interests(conn, profile_id)
                except NotFoundError as exc:
                    raise HTTPException(status_code=404, detail=str(exc)) from exc

        @app.get("/profiles/{profile_id}/notices", response_model=list[MatchedNotice])
        def get_profile_notices_endpoint(
            profile_id: str,
            limit: int = Query(default=10, ge=1, le=50),
        ) -> list[MatchedNotice]:
            with connection() as conn:
                try:
                    return list_profile_notices(conn, profile_id, limit=limit)
                except NotFoundError as exc:
                    raise HTTPException(status_code=404, detail=str(exc)) from exc
                except InvalidRequestError as exc:
                    raise HTTPException(status_code=400, detail=str(exc)) from exc

        @app.get(
            "/profiles/{profile_id}/courses/recommended",
            response_model=list[MatchedCourse],
        )
        def get_profile_course_recommendations_endpoint(
            profile_id: str,
            year: int | None = Query(default=None),
            semester: int | None = Query(default=None),
            query: str = Query(default=""),
            limit: int = Query(default=10, ge=1, le=50),
        ) -> list[MatchedCourse]:
            with connection() as conn:
                try:
                    return get_profile_course_recommendations(
                        conn,
                        profile_id,
                        year=year,
                        semester=semester,
                        query=query,
                        limit=limit,
                    )
                except NotFoundError as exc:
                    raise HTTPException(status_code=404, detail=str(exc)) from exc
                except InvalidRequestError as exc:
                    raise HTTPException(status_code=400, detail=str(exc)) from exc

        @app.get(
            "/profiles/{profile_id}/meal-recommendations",
            response_model=MealRecommendationResponse,
        )
        def get_profile_meal_recommendations_endpoint(
            profile_id: str,
            origin: str = Query(description="출발 건물 slug 또는 이름"),
            at: datetime | None = Query(default=None),
            year: int | None = Query(default=None),
            semester: int | None = Query(default=None),
            budget_max: int | None = Query(default=None, ge=0),
            category: str | None = Query(default=None),
            open_now: bool = Query(default=False),
            limit: int = Query(default=10, ge=1, le=50),
        ) -> MealRecommendationResponse:
            with connection() as conn:
                try:
                    return get_profile_meal_recommendations(
                        conn,
                        profile_id,
                        origin=origin,
                        at=at,
                        year=year,
                        semester=semester,
                        budget_max=budget_max,
                        category=category,
                        limit=limit,
                        open_now=open_now,
                    )
                except NotFoundError as exc:
                    raise HTTPException(status_code=404, detail=str(exc)) from exc
                except InvalidRequestError as exc:
                    raise HTTPException(status_code=400, detail=str(exc)) from exc

    if settings.admin_enabled and not public_readonly:
        @app.get("/admin/sync", response_class=HTMLResponse)
        def admin_sync_dashboard(request: Request) -> HTMLResponse:
            ensure_admin_request_allowed(request)
            with connection() as conn:
                state = get_sync_dashboard_state(conn)
            return HTMLResponse(render_admin_sync_page(state))

        @app.post("/admin/sync/run")
        async def admin_sync_run(request: Request) -> RedirectResponse:
            ensure_admin_request_allowed(request)
            form_values = {
                key: values[-1] if values else ""
                for key, values in parse_qs(
                    (await request.body()).decode("utf-8"),
                    keep_blank_values=True,
                ).items()
            }

            def parse_optional_int(name: str) -> int | None:
                raw_value = form_values.get(name, "").strip()
                if not raw_value:
                    return None
                try:
                    return int(raw_value)
                except ValueError as exc:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid integer for {name}: {raw_value}",
                    ) from exc

            target = form_values.get("target", "").strip()
            try:
                run_admin_sync(
                    target=target or "snapshot",
                    campus=form_values.get("campus", "").strip() or None,
                    year=parse_optional_int("year"),
                    semester=parse_optional_int("semester"),
                    notice_pages=parse_optional_int("notice_pages"),
                )
            except InvalidRequestError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            return RedirectResponse("/admin/sync", status_code=303)

        @app.get("/admin/observability", response_class=HTMLResponse)
        def admin_observability_dashboard(request: Request) -> HTMLResponse:
            ensure_admin_request_allowed(request)
            readiness = get_readiness_snapshot()
            with connection() as conn:
                observability = get_observability_snapshot(conn).model_dump()
            return HTMLResponse(
                render_admin_observability_page(
                    {"readiness": readiness, "observability": observability}
                )
            )

        @app.get("/admin/observability.json")
        def admin_observability_json(request: Request) -> dict[str, object]:
            ensure_admin_request_allowed(request)
            readiness = get_readiness_snapshot()
            with connection() as conn:
                observability = get_observability_snapshot(conn).model_dump()
            return {
                "health": {"ok": True},
                "readiness": readiness,
                **observability,
            }

    return app


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "songsim_campus.api:create_app",
        factory=True,
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
