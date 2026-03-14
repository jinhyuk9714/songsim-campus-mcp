from __future__ import annotations

import logging
from datetime import datetime

from songsim_campus import repo
from songsim_campus.db import connection, get_connection, init_db
from songsim_campus.services import get_observability_snapshot, run_automation_tick
from songsim_campus.settings import clear_settings_cache


def _create_sync_run(
    *,
    target: str,
    status: str,
    trigger: str,
    started_at: str,
    finished_at: str | None,
    summary: dict[str, int] | None = None,
) -> int:
    with connection() as conn:
        run_id = repo.create_sync_run(
            conn,
            target=target,
            status=status,
            trigger=trigger,
            params={},
            summary=summary or {},
            error_text=None,
            started_at=started_at,
            finished_at=finished_at,
        )
    return run_id


def _kakao_cache_row(
    *,
    place_id: str = "242731511",
    name: str = "가톨릭백반",
    source_tag: str = "kakao_local_cache",
) -> dict[str, object]:
    return {
        "id": -1,
        "slug": f"kakao-{place_id}",
        "name": name,
        "category": "korean",
        "min_price": None,
        "max_price": None,
        "latitude": 37.48674,
        "longitude": 126.80182,
        "tags": ["한식"],
        "description": "경기 부천시 원미구",
        "source_tag": source_tag,
        "last_synced_at": "2026-03-14T10:00:00+09:00",
        "kakao_place_id": place_id,
        "source_url": f"https://place.map.kakao.com/{place_id}",
    }


def test_automation_observability_uses_last_success_for_due_calculation(
    app_env,
    monkeypatch,
):
    monkeypatch.setenv("SONGSIM_AUTOMATION_ENABLED", "true")
    monkeypatch.setenv("SONGSIM_AUTOMATION_SNAPSHOT_INTERVAL_MINUTES", "360")
    clear_settings_cache()
    init_db()

    _create_sync_run(
        target="snapshot",
        status="success",
        trigger="automation",
        started_at="2026-03-14T05:00:00+09:00",
        finished_at="2026-03-14T05:05:00+09:00",
        summary={"places": 1},
    )
    _create_sync_run(
        target="snapshot",
        status="failed",
        trigger="automation",
        started_at="2026-03-14T08:00:00+09:00",
        finished_at="2026-03-14T08:01:00+09:00",
    )

    now = datetime.fromisoformat("2026-03-14T09:00:00+09:00")
    monkeypatch.setattr("songsim_campus.services._now", lambda: now)

    with connection() as conn:
        snapshot = get_observability_snapshot(conn)

    job = next(item for item in snapshot.automation.jobs if item.name == "snapshot")
    assert snapshot.automation.enabled is True
    assert job.last_status == "failed"
    assert job.last_run_at == "2026-03-14T08:01:00+09:00"
    assert job.next_due_at == "2026-03-14T11:05:00+09:00"


def test_run_automation_tick_records_snapshot_run_as_automation(app_env, monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("SONGSIM_AUTOMATION_ENABLED", "true")
    clear_settings_cache()
    init_db()

    def fake_snapshot(
        conn,
        *,
        campus: str | None = None,
        year: int | None = None,
        semester: int | None = None,
        notice_pages: int | None = None,
    ):
        return {"places": 5, "courses": 10, "notices": 4, "transport_guides": 2}

    monkeypatch.setattr("songsim_campus.services.sync_official_snapshot", fake_snapshot)

    runs = run_automation_tick(job_names={"snapshot"})

    assert len(runs) == 1
    assert runs[0].target == "snapshot"
    assert runs[0].trigger == "automation"
    assert runs[0].status == "success"
    assert runs[0].summary == {
        "places": 5,
        "courses": 10,
        "notices": 4,
        "transport_guides": 2,
    }
    with connection() as conn:
        stored = repo.list_sync_runs(conn, limit=5)
    assert stored[0]["trigger"] == "automation"
    assert "event=automation_job_completed" in caplog.text


def test_run_automation_tick_cleans_up_stale_cache_rows(app_env, monkeypatch):
    monkeypatch.setenv("SONGSIM_AUTOMATION_ENABLED", "true")
    clear_settings_cache()
    init_db()

    with connection() as conn:
        repo.replace_restaurant_cache_snapshot(
            conn,
            origin_slug="central-library",
            kakao_query="한식",
            radius_meters=900,
            fetched_at="2026-03-10T10:00:00+09:00",
            rows=[_kakao_cache_row(place_id="111")],
        )
        repo.replace_restaurant_cache_snapshot(
            conn,
            origin_slug="student-center",
            kakao_query="한식",
            radius_meters=900,
            fetched_at="2026-03-14T11:30:00+09:00",
            rows=[_kakao_cache_row(place_id="222")],
        )
        repo.upsert_restaurant_hours_cache(
            conn,
            kakao_place_id="111",
            source_url="https://place.map.kakao.com/111",
            raw_payload={},
            opening_hours={"weekday": "11:00 ~ 18:00"},
            fetched_at="2026-03-01T10:00:00+09:00",
        )
        repo.upsert_restaurant_hours_cache(
            conn,
            kakao_place_id="222",
            source_url="https://place.map.kakao.com/222",
            raw_payload={},
            opening_hours={"weekday": "11:00 ~ 18:00"},
            fetched_at="2026-03-14T11:30:00+09:00",
        )

    now = datetime.fromisoformat("2026-03-14T12:00:00+09:00")
    monkeypatch.setattr("songsim_campus.services._now", lambda: now)

    runs = run_automation_tick(job_names={"cache_cleanup"})

    assert len(runs) == 1
    assert runs[0].target == "cache_cleanup"
    assert runs[0].trigger == "automation"
    assert runs[0].summary == {
        "restaurant_cache_snapshots_deleted": 1,
        "restaurant_cache_items_deleted": 1,
        "restaurant_hours_cache_deleted": 1,
    }

    with connection() as conn:
        assert repo.count_rows(conn, "restaurant_cache_snapshots") == 1
        assert repo.count_rows(conn, "restaurant_cache_items") == 1
        assert repo.count_rows(conn, "restaurant_hours_cache") == 1


def test_run_automation_tick_records_failed_run(app_env, monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("SONGSIM_AUTOMATION_ENABLED", "true")
    clear_settings_cache()
    init_db()

    def broken_snapshot(
        conn,
        *,
        campus: str | None = None,
        year: int | None = None,
        semester: int | None = None,
        notice_pages: int | None = None,
    ):
        raise RuntimeError("snapshot exploded")

    monkeypatch.setattr("songsim_campus.services.sync_official_snapshot", broken_snapshot)

    runs = run_automation_tick(job_names={"snapshot"})

    assert len(runs) == 1
    assert runs[0].status == "failed"
    assert runs[0].trigger == "automation"
    assert "snapshot exploded" in (runs[0].error_text or "")
    with connection() as conn:
        stored = repo.list_sync_runs(conn, limit=5)
    assert stored[0]["status"] == "failed"
    assert stored[0]["trigger"] == "automation"
    assert "event=automation_job_failed" in caplog.text


def test_postgres_advisory_lock_allows_only_one_holder(app_env):
    init_db()
    conn_one = get_connection()
    conn_two = get_connection()
    try:
        assert repo.try_advisory_lock(conn_one, 424242) is True
        assert repo.try_advisory_lock(conn_two, 424242) is False
        assert repo.release_advisory_lock(conn_one, 424242) is True
        assert repo.try_advisory_lock(conn_two, 424242) is True
    finally:
        conn_one.close()
        conn_two.close()
