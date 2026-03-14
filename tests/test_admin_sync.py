from __future__ import annotations

from songsim_campus import repo
from songsim_campus.db import connection, init_db
from songsim_campus.seed import seed_demo
from songsim_campus.services import (
    get_sync_dashboard_state,
    list_sync_runs,
    run_admin_sync,
)


def test_run_admin_sync_records_success_history_for_snapshot(app_env, monkeypatch):
    init_db()

    def fake_snapshot(
        conn,
        *,
        campus: str | None = None,
        year: int | None = None,
        semester: int | None = None,
        notice_pages: int | None = None,
    ):
        assert campus == "2"
        assert year == 2026
        assert semester == 1
        assert notice_pages == 2
        return {"places": 3, "courses": 5, "notices": 7, "transport_guides": 1}

    monkeypatch.setattr("songsim_campus.services.sync_official_snapshot", fake_snapshot)

    run = run_admin_sync(campus="2", year=2026, semester=1, notice_pages=2)

    assert run.target == "snapshot"
    assert run.status == "success"
    assert run.summary == {"places": 3, "courses": 5, "notices": 7, "transport_guides": 1}
    assert run.error_text is None
    assert run.finished_at is not None

    with connection() as conn:
        runs = list_sync_runs(conn, limit=10)
        dashboard = get_sync_dashboard_state(conn)

    assert runs[0].id == run.id
    assert runs[0].params == {"campus": "2", "year": 2026, "semester": 1, "notice_pages": 2}
    assert dashboard["recent_runs"][0].id == run.id


def test_run_admin_sync_dispatches_target_specific_parameters(app_env, monkeypatch):
    init_db()
    seen: dict[str, object] = {}

    def fake_places(conn, *, campus: str = "1", fetched_at: str | None = None):
        seen["places"] = {"campus": campus, "fetched_at": fetched_at}
        return []

    def fake_courses(
        conn,
        *,
        year: int | None = None,
        semester: int | None = None,
        fetched_at: str | None = None,
        source=None,
    ):
        seen["courses"] = {"year": year, "semester": semester, "fetched_at": fetched_at}
        return []

    def fake_notices(conn, *, pages: int = 1, fetched_at: str | None = None, source=None):
        seen["notices"] = {"pages": pages, "fetched_at": fetched_at}
        return []

    monkeypatch.setattr("songsim_campus.services.refresh_places_from_campus_map", fake_places)
    monkeypatch.setattr("songsim_campus.services.refresh_courses_from_subject_search", fake_courses)
    monkeypatch.setattr("songsim_campus.services.refresh_notices_from_notice_board", fake_notices)

    places_run = run_admin_sync(target="places", campus="9")
    courses_run = run_admin_sync(target="courses", year=2026, semester=1)
    notices_run = run_admin_sync(target="notices", notice_pages=3)

    assert places_run.summary == {"places": 0}
    assert courses_run.summary == {"courses": 0}
    assert notices_run.summary == {"notices": 0}
    assert seen["places"] == {"campus": "9", "fetched_at": None}
    assert seen["courses"] == {"year": 2026, "semester": 1, "fetched_at": None}
    assert seen["notices"] == {"pages": 3, "fetched_at": None}


def test_run_admin_sync_rolls_back_failed_target_and_records_failure(app_env, monkeypatch):
    init_db()

    def broken_transport(conn, *, fetched_at: str | None = None, source=None):
        repo.replace_transport_guides(
            conn,
            [
                {
                    "mode": "bus",
                    "title": "실패 전 임시 데이터",
                    "summary": "",
                    "steps": [],
                    "source_url": None,
                    "source_tag": "test",
                    "last_synced_at": "2026-03-14T10:00:00+09:00",
                }
            ],
        )
        raise RuntimeError("transport sync exploded")

    monkeypatch.setattr(
        "songsim_campus.services.refresh_transport_guides_from_location_page",
        broken_transport,
    )

    run = run_admin_sync(target="transport_guides")

    assert run.status == "failed"
    assert run.summary == {}
    assert "transport sync exploded" in (run.error_text or "")

    with connection() as conn:
        assert repo.count_rows(conn, "transport_guides") == 0
        stored = list_sync_runs(conn, limit=10)

    assert stored[0].status == "failed"
    assert "transport sync exploded" in (stored[0].error_text or "")


def test_get_sync_dashboard_state_reports_row_counts_and_last_synced(app_env):
    init_db()
    seed_demo(force=True)

    with connection() as conn:
        state = get_sync_dashboard_state(conn)

    datasets = {item["name"]: item for item in state["datasets"]}
    assert datasets["places"]["row_count"] == 5
    assert datasets["courses"]["row_count"] > 0
    assert datasets["notices"]["row_count"] > 0
    assert datasets["transport_guides"]["row_count"] == 0
    assert datasets["places"]["last_synced_at"] == "2026-03-13T09:00:00+09:00"
    assert datasets["transport_guides"]["last_synced_at"] is None
    assert state["recent_runs"] == []
