from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta

import pytest

from songsim_campus import repo
from songsim_campus import services as services_module
from songsim_campus.db import connection, init_db
from songsim_campus.seed import seed_demo
from songsim_campus.services import (
    SYNC_DATASET_TABLES,
    find_nearby_restaurants,
    get_observability_snapshot,
    get_readiness_snapshot,
    reset_observability_state,
    run_admin_sync,
)
from songsim_campus.settings import clear_settings_cache


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


def _readiness_payload(
    *,
    ok: bool,
    with_error: bool = False,
    suffix: str = "",
) -> dict[str, object]:
    tables = {
        table: {
            "ok": ok,
            "name": f"{table}{suffix}",
            "row_count": 1,
            "last_synced_at": "2026-03-17T17:59:00+09:00",
        }
        for table in SYNC_DATASET_TABLES
    }
    tables["sync_runs"] = {"ok": ok}
    payload: dict[str, object] = {
        "ok": ok,
        "database": {"ok": not with_error, "error": "database timeout" if with_error else None},
        "tables": tables,
    }
    if with_error:
        payload["ok"] = False
        payload["tables"]["places"] = {"ok": False, "error": "statement timeout"}
    return payload


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


def test_observability_prefers_stale_cache_without_live_refetch(app_env, monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    init_db()
    seed_demo(force=True)
    now = datetime.fromisoformat("2026-03-14T12:00:00+09:00")
    monkeypatch.setattr("songsim_campus.services._now", lambda: now)

    class ShouldNotBeCalledKakaoClient:
        def search_sync(self, query: str, *, x=None, y=None, radius: int = 1000):
            raise AssertionError("stale cache should be returned before live refetch")

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
            kakao_client=ShouldNotBeCalledKakaoClient(),
        )
        snapshot = get_observability_snapshot(conn)

    assert results
    assert snapshot.cache.live_fetch_error == 0
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


def test_observability_tracks_restaurant_hours_cache_paths(app_env, monkeypatch, caplog):
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
        return {
            "places": 1,
            "courses": 2,
            "notices": 3,
            "certificate_guides": 2,
            "scholarship_guides": 5,
            "transport_guides": 4,
        }

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


def test_readiness_snapshot_requires_non_empty_required_public_datasets(app_env, monkeypatch):
    init_db()
    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    clear_settings_cache()

    def fake_dataset_state(conn, table: str):
        if table == "certificate_guides":
            return {"name": table, "row_count": 0, "last_synced_at": None}
        return {
            "name": table,
            "row_count": 1,
            "last_synced_at": "2026-03-17T16:00:00+09:00",
        }

    monkeypatch.setattr("songsim_campus.services.repo.get_dataset_sync_state", fake_dataset_state)

    readiness = get_readiness_snapshot()

    clear_settings_cache()

    assert readiness["ok"] is False
    assert readiness["database"]["ok"] is True
    assert readiness["tables"]["certificate_guides"]["ok"] is False
    assert readiness["tables"]["certificate_guides"]["reason"] == "empty_or_unsynced"


def test_readiness_snapshot_allows_empty_optional_public_datasets(app_env, monkeypatch):
    init_db()
    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    clear_settings_cache()

    def fake_dataset_state(conn, table: str):
        if table in {"courses", "campus_dining_menus"}:
            return {"name": table, "row_count": 0, "last_synced_at": None}
        return {
            "name": table,
            "row_count": 1,
            "last_synced_at": "2026-03-17T16:00:00+09:00",
        }

    monkeypatch.setattr("songsim_campus.services.repo.get_dataset_sync_state", fake_dataset_state)

    readiness = get_readiness_snapshot()

    clear_settings_cache()

    assert readiness["ok"] is True
    assert readiness["tables"]["campus_dining_menus"]["ok"] is True
    assert readiness["tables"]["courses"]["ok"] is True


def test_readiness_snapshot_caches_success_within_ttl(app_env, monkeypatch):
    init_db()
    current = {"value": datetime.fromisoformat("2026-03-17T17:00:00+09:00")}
    dataset_calls: list[str] = []
    sync_calls: list[int] = []

    monkeypatch.setattr("songsim_campus.services._now", lambda: current["value"])

    def fake_dataset_state(conn, table: str):
        dataset_calls.append(table)
        return {
            "name": table,
            "row_count": 1,
            "last_synced_at": "2026-03-17T16:59:00+09:00",
        }

    def fake_list_sync_runs(conn, limit: int = 1):
        sync_calls.append(limit)
        return []

    monkeypatch.setattr("songsim_campus.services.repo.get_dataset_sync_state", fake_dataset_state)
    monkeypatch.setattr("songsim_campus.services.repo.list_sync_runs", fake_list_sync_runs)

    first = get_readiness_snapshot()
    current["value"] += timedelta(seconds=10)
    second = get_readiness_snapshot()

    assert first == second
    assert dataset_calls == list(SYNC_DATASET_TABLES)
    assert sync_calls == [1]


def test_readiness_snapshot_recomputes_after_ttl(app_env, monkeypatch):
    init_db()
    current = {"value": datetime.fromisoformat("2026-03-17T17:10:00+09:00")}
    dataset_calls: list[str] = []

    monkeypatch.setattr("songsim_campus.services._now", lambda: current["value"])

    def fake_dataset_state(conn, table: str):
        dataset_calls.append(table)
        return {
            "name": table,
            "row_count": 1,
            "last_synced_at": "2026-03-17T17:09:00+09:00",
        }

    monkeypatch.setattr("songsim_campus.services.repo.get_dataset_sync_state", fake_dataset_state)
    monkeypatch.setattr("songsim_campus.services.repo.list_sync_runs", lambda conn, limit=1: [])

    get_readiness_snapshot()
    current["value"] += timedelta(seconds=31)
    get_readiness_snapshot()

    deadline = time.time() + 1
    expected_calls = len(SYNC_DATASET_TABLES) * 2
    while time.time() < deadline and len(dataset_calls) < expected_calls:
        time.sleep(0.01)

    assert len(dataset_calls) == expected_calls


def test_readiness_snapshot_keeps_cache_separate_by_app_mode(app_env, monkeypatch):
    init_db()
    current = {"value": datetime.fromisoformat("2026-03-17T17:20:00+09:00")}
    dataset_calls: list[str] = []

    monkeypatch.setattr("songsim_campus.services._now", lambda: current["value"])

    def fake_dataset_state(conn, table: str):
        dataset_calls.append(table)
        return {
            "name": table,
            "row_count": 1,
            "last_synced_at": "2026-03-17T17:19:00+09:00",
        }

    monkeypatch.setattr("songsim_campus.services.repo.get_dataset_sync_state", fake_dataset_state)
    monkeypatch.setattr("songsim_campus.services.repo.list_sync_runs", lambda conn, limit=1: [])

    get_readiness_snapshot()
    current["value"] += timedelta(seconds=10)
    get_readiness_snapshot()

    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    clear_settings_cache()
    get_readiness_snapshot()
    clear_settings_cache()

    assert len(dataset_calls) == len(SYNC_DATASET_TABLES) * 2


def test_readiness_snapshot_rolls_back_after_dataset_failure(app_env, monkeypatch):
    init_db()
    seed_demo(force=True)
    original_get_dataset_sync_state = repo.get_dataset_sync_state

    def flaky_dataset_state(conn, table: str):
        if table == "places":
            conn.execute("SELECT * FROM missing_readiness_table")
        return original_get_dataset_sync_state(conn, table)

    monkeypatch.setattr("songsim_campus.services.repo.get_dataset_sync_state", flaky_dataset_state)

    readiness = get_readiness_snapshot()

    assert readiness["ok"] is False
    assert readiness["tables"]["places"]["ok"] is False
    assert readiness["tables"]["courses"]["ok"] is True
    assert readiness["tables"]["notices"]["ok"] is True
    assert readiness["tables"]["sync_runs"]["ok"] is True


def test_readiness_snapshot_caches_failure_within_ttl(app_env, monkeypatch):
    init_db()
    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    clear_settings_cache()
    current = {"value": datetime.fromisoformat("2026-03-17T17:30:00+09:00")}
    dataset_calls: list[str] = []

    monkeypatch.setattr("songsim_campus.services._now", lambda: current["value"])

    def fake_dataset_state(conn, table: str):
        dataset_calls.append(table)
        if table == "certificate_guides":
            return {"name": table, "row_count": 0, "last_synced_at": None}
        return {
            "name": table,
            "row_count": 1,
            "last_synced_at": "2026-03-17T17:29:00+09:00",
        }

    monkeypatch.setattr("songsim_campus.services.repo.get_dataset_sync_state", fake_dataset_state)
    monkeypatch.setattr("songsim_campus.services.repo.list_sync_runs", lambda conn, limit=1: [])

    first = get_readiness_snapshot()
    current["value"] += timedelta(seconds=5)
    second = get_readiness_snapshot()
    clear_settings_cache()

    assert first["ok"] is False
    assert second["ok"] is False
    assert dataset_calls == list(SYNC_DATASET_TABLES)


def test_readiness_snapshot_returns_stale_while_refresh_runs(app_env, monkeypatch):
    init_db()
    current = {"value": datetime.fromisoformat("2026-03-17T18:00:00+09:00")}
    stale_snapshot = _readiness_payload(ok=True, suffix="-stale")
    fresh_snapshot = _readiness_payload(ok=True, suffix="-fresh")
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()
    call_count = {"value": 0}

    monkeypatch.setattr("songsim_campus.services._now", lambda: current["value"])

    def compute_stale(settings):
        return stale_snapshot

    monkeypatch.setattr("songsim_campus.services._compute_readiness_snapshot", compute_stale)
    assert get_readiness_snapshot() == stale_snapshot

    current["value"] += timedelta(seconds=31)

    def slow_refresh(settings):
        call_count["value"] += 1
        started.set()
        release.wait(timeout=2)
        finished.set()
        return fresh_snapshot

    monkeypatch.setattr("songsim_campus.services._compute_readiness_snapshot", slow_refresh)

    started_at = time.perf_counter()
    result = get_readiness_snapshot()
    elapsed_ms = (time.perf_counter() - started_at) * 1000

    assert result == stale_snapshot
    assert elapsed_ms < 200
    assert started.wait(timeout=1)

    release.set()
    assert finished.wait(timeout=1)
    deadline = time.time() + 1
    while time.time() < deadline:
        if get_readiness_snapshot() == fresh_snapshot:
            break
        time.sleep(0.01)

    assert call_count["value"] == 1
    assert get_readiness_snapshot() == fresh_snapshot


def test_readiness_snapshot_starts_only_one_background_refresh(app_env, monkeypatch):
    init_db()
    current = {"value": datetime.fromisoformat("2026-03-17T18:10:00+09:00")}
    stale_snapshot = _readiness_payload(ok=True, suffix="-stale")
    fresh_snapshot = _readiness_payload(ok=True, suffix="-fresh")
    release = threading.Event()
    started = threading.Event()
    finished = threading.Event()
    call_count = {"value": 0}

    monkeypatch.setattr("songsim_campus.services._now", lambda: current["value"])
    monkeypatch.setattr(
        "songsim_campus.services._compute_readiness_snapshot",
        lambda settings: stale_snapshot,
    )
    assert get_readiness_snapshot() == stale_snapshot

    current["value"] += timedelta(seconds=31)

    def slow_refresh(settings):
        call_count["value"] += 1
        started.set()
        release.wait(timeout=2)
        finished.set()
        return fresh_snapshot

    monkeypatch.setattr("songsim_campus.services._compute_readiness_snapshot", slow_refresh)

    results: list[dict[str, object]] = []

    def fetch_snapshot():
        results.append(get_readiness_snapshot())

    threads = [threading.Thread(target=fetch_snapshot) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=1)

    assert started.wait(timeout=1)
    assert results == [stale_snapshot] * 4
    assert call_count["value"] == 1
    assert services_module._READINESS_REFRESH_IN_PROGRESS

    release.set()
    assert finished.wait(timeout=1)
    deadline = time.time() + 1
    while time.time() < deadline:
        if not services_module._READINESS_REFRESH_IN_PROGRESS:
            break
        time.sleep(0.01)

    assert not services_module._READINESS_REFRESH_IN_PROGRESS


def test_readiness_snapshot_keeps_stale_snapshot_after_refresh_failure(app_env, monkeypatch):
    init_db()
    current = {"value": datetime.fromisoformat("2026-03-17T18:20:00+09:00")}
    stale_snapshot = _readiness_payload(ok=True, suffix="-stale")
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()
    call_count = {"value": 0}

    monkeypatch.setattr("songsim_campus.services._now", lambda: current["value"])
    monkeypatch.setattr(
        "songsim_campus.services._compute_readiness_snapshot",
        lambda settings: stale_snapshot,
    )
    assert get_readiness_snapshot() == stale_snapshot

    current["value"] += timedelta(seconds=31)

    def failed_refresh(settings):
        call_count["value"] += 1
        started.set()
        release.wait(timeout=2)
        finished.set()
        return _readiness_payload(ok=False, with_error=True, suffix="-failed")

    monkeypatch.setattr("songsim_campus.services._compute_readiness_snapshot", failed_refresh)

    assert get_readiness_snapshot() == stale_snapshot
    assert started.wait(timeout=1)

    release.set()
    assert finished.wait(timeout=1)
    deadline = time.time() + 1
    while time.time() < deadline:
        if not services_module._READINESS_REFRESH_IN_PROGRESS:
            break
        time.sleep(0.01)

    assert not services_module._READINESS_REFRESH_IN_PROGRESS
    assert get_readiness_snapshot() == stale_snapshot
    assert call_count["value"] == 2


def test_readiness_snapshot_does_not_use_stale_snapshot_past_max_stale_window(
    app_env,
    monkeypatch,
):
    init_db()
    current = {"value": datetime.fromisoformat("2026-03-17T18:40:00+09:00")}
    stale_snapshot = _readiness_payload(ok=True, suffix="-stale")
    failure_snapshot = _readiness_payload(ok=False, with_error=True, suffix="-failed")

    monkeypatch.setattr("songsim_campus.services._now", lambda: current["value"])
    monkeypatch.setattr(
        "songsim_campus.services._compute_readiness_snapshot",
        lambda settings: stale_snapshot,
    )
    assert get_readiness_snapshot() == stale_snapshot

    current["value"] += timedelta(
        seconds=services_module.READINESS_CACHE_MAX_STALE_SECONDS + 1
    )
    monkeypatch.setattr(
        "songsim_campus.services._compute_readiness_snapshot",
        lambda settings: failure_snapshot,
    )

    assert get_readiness_snapshot() == failure_snapshot
