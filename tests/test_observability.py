from __future__ import annotations

import logging
from datetime import datetime

import httpx
import pytest

from songsim_campus import repo
from songsim_campus.db import connection, init_db
from songsim_campus.seed import seed_demo
from songsim_campus.services import (
    find_nearby_restaurants,
    get_observability_snapshot,
    get_readiness_snapshot,
    reset_observability_state,
    run_admin_sync,
)


@pytest.fixture(autouse=True)
def reset_runtime_observability():
    reset_observability_state()
    yield
    reset_observability_state()


def _kakao_cache_row(*, name: str = "가톨릭백반") -> dict[str, object]:
    return {
        "id": -1,
        "slug": "kakao-gatolic-bap",
        "name": name,
        "category": "korean",
        "min_price": None,
        "max_price": None,
        "latitude": 37.48674,
        "longitude": 126.80182,
        "tags": ["한식"],
        "description": "경기 부천시 원미구",
        "source_tag": "kakao_local_cache",
        "last_synced_at": "2026-03-14T10:00:00+09:00",
        "kakao_place_id": "242731511",
        "source_url": "https://place.map.kakao.com/242731511",
    }


def test_observability_counts_fresh_cache_hits(app_env, monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    init_db()
    seed_demo(force=True)
    now = datetime.fromisoformat("2026-03-14T12:00:00+09:00")
    monkeypatch.setattr("songsim_campus.services._now", lambda: now)

    with connection() as conn:
        repo.replace_restaurant_cache_snapshot(
            conn,
            origin_slug="central-library",
            kakao_query="한식",
            radius_meters=15 * 75,
            fetched_at="2026-03-14T10:00:00+09:00",
            rows=[_kakao_cache_row()],
        )

        results = find_nearby_restaurants(
            conn,
            origin="central-library",
            category="korean",
            walk_minutes=15,
            limit=5,
        )
        snapshot = get_observability_snapshot(conn)

    assert results
    assert snapshot.cache.fresh_hit == 1
    assert any(event["decision"] == "fresh_hit" for event in snapshot.cache.recent_events)
    assert "event=restaurant_cache_decision" in caplog.text


def test_observability_uses_stale_cache_when_live_fetch_fails(app_env, monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    init_db()
    seed_demo(force=True)
    now = datetime.fromisoformat("2026-03-14T12:00:00+09:00")
    monkeypatch.setattr("songsim_campus.services._now", lambda: now)

    class BrokenKakaoClient:
        def search_sync(self, query: str, *, x=None, y=None, radius: int = 1000):
            raise httpx.HTTPError("kakao unavailable")

    with connection() as conn:
        repo.replace_restaurant_cache_snapshot(
            conn,
            origin_slug="central-library",
            kakao_query="한식",
            radius_meters=15 * 75,
            fetched_at="2026-03-14T01:00:00+09:00",
            rows=[_kakao_cache_row()],
        )

        results = find_nearby_restaurants(
            conn,
            origin="central-library",
            category="korean",
            walk_minutes=15,
            limit=5,
            kakao_client=BrokenKakaoClient(),
        )
        snapshot = get_observability_snapshot(conn)

    assert results
    assert snapshot.cache.live_fetch_error == 1
    assert snapshot.cache.stale_hit == 1
    assert any(event["decision"] == "stale_hit" for event in snapshot.cache.recent_events)
    assert "event=restaurant_cache_decision" in caplog.text


def test_observability_counts_local_fallback_when_no_cache_or_kakao(app_env, caplog):
    caplog.set_level(logging.INFO)
    init_db()
    seed_demo(force=True)

    with connection() as conn:
        results = find_nearby_restaurants(conn, origin="central-library", walk_minutes=15, limit=5)
        snapshot = get_observability_snapshot(conn)

    assert results
    assert snapshot.cache.local_fallback == 1
    assert snapshot.cache.recent_events[0]["decision"] == "local_fallback"
    assert "event=restaurant_cache_decision" in caplog.text


def test_observability_tracks_restaurant_hours_cache_paths(app_env, caplog):
    caplog.set_level(logging.INFO)
    init_db()
    seed_demo(force=True)

    with connection() as conn:
        repo.replace_restaurant_cache_snapshot(
            conn,
            origin_slug="central-library",
            kakao_query="한식",
            radius_meters=15 * 75,
            fetched_at="2026-03-14T10:00:00+09:00",
            rows=[_kakao_cache_row()],
        )
        repo.upsert_restaurant_hours_cache(
            conn,
            kakao_place_id="242731511",
            source_url="https://place.map.kakao.com/242731511",
            raw_payload={"open_hours": {}},
            opening_hours={"fri": "08:00 ~ 21:00"},
            fetched_at="2026-03-14T10:00:00+09:00",
        )

        find_nearby_restaurants(
            conn,
            origin="central-library",
            category="korean",
            walk_minutes=15,
            at=datetime.fromisoformat("2026-03-20T12:00:00+09:00"),
        )
        snapshot = get_observability_snapshot(conn)

    assert snapshot.cache.restaurant_hours_fresh_hit == 1
    assert snapshot.cache.recent_events[0]["decision"] == "restaurant_hours_fresh_hit"
    assert "event=restaurant_hours_cache_decision" in caplog.text


def test_run_admin_sync_updates_observability_for_success_and_failure(
    app_env,
    monkeypatch,
    caplog,
):
    caplog.set_level(logging.INFO)
    init_db()

    def fake_snapshot(
        conn,
        *,
        campus: str | None = None,
        year: int | None = None,
        semester: int | None = None,
        notice_pages: int | None = None,
    ):
        return {"places": 1, "courses": 2, "notices": 3, "transport_guides": 4}

    def broken_transport(conn, *, fetched_at: str | None = None, source=None):
        raise RuntimeError("transport sync exploded")

    monkeypatch.setattr("songsim_campus.services.sync_official_snapshot", fake_snapshot)
    success_run = run_admin_sync(
        target="snapshot",
        campus="1",
        year=2026,
        semester=1,
        notice_pages=1,
    )

    monkeypatch.setattr(
        "songsim_campus.services.refresh_transport_guides_from_location_page",
        broken_transport,
    )
    failed_run = run_admin_sync(target="transport_guides")

    with connection() as conn:
        snapshot = get_observability_snapshot(conn)

    assert success_run.status == "success"
    assert failed_run.status == "failed"
    assert snapshot.sync.recent_events[0]["status"] == "failed"
    assert snapshot.sync.recent_events[1]["status"] == "success"
    assert snapshot.sync.last_failure_message == "transport sync exploded"
    assert snapshot.sync.last_failure_at is not None
    assert "event=admin_sync_completed" in caplog.text
    assert "event=admin_sync_failed" in caplog.text


def test_readiness_snapshot_reports_failures(app_env, monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    init_db()
    seed_demo(force=True)

    def broken_dataset_state(conn, table: str):
        raise sqlite3.OperationalError(f"{table} unavailable")

    import sqlite3

    monkeypatch.setattr("songsim_campus.services.repo.get_dataset_sync_state", broken_dataset_state)

    readiness = get_readiness_snapshot()

    assert readiness["ok"] is False
    assert readiness["database"]["ok"] is True
    assert readiness["tables"]["places"]["ok"] is False
    assert "unavailable" in readiness["tables"]["places"]["error"]
    assert "event=readiness_check_failed" in caplog.text
