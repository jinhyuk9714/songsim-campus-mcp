from __future__ import annotations

from pathlib import Path

import pytest

from songsim_campus.settings import Settings, clear_settings_cache


def test_settings_parse_database_url(monkeypatch):
    monkeypatch.setenv(
        "SONGSIM_DATABASE_URL",
        "postgresql://songsim:songsim@127.0.0.1:55432/songsim_test",
    )
    clear_settings_cache()

    settings = Settings()

    assert settings.database_url == "postgresql://songsim:songsim@127.0.0.1:55432/songsim_test"


def test_settings_reject_legacy_database_path(monkeypatch):
    monkeypatch.setenv("SONGSIM_DATABASE_PATH", "songsim.db")
    clear_settings_cache()

    with pytest.raises(ValueError, match="SONGSIM_DATABASE_PATH"):
        Settings()


def test_settings_accept_blank_course_sync_values(monkeypatch):
    monkeypatch.setenv("SONGSIM_OFFICIAL_COURSE_YEAR", "")
    monkeypatch.setenv("SONGSIM_OFFICIAL_COURSE_SEMESTER", "")
    clear_settings_cache()

    settings = Settings()

    assert settings.official_course_year is None
    assert settings.official_course_semester is None


def test_settings_parse_explicit_course_sync_values(monkeypatch):
    monkeypatch.setenv("SONGSIM_OFFICIAL_COURSE_YEAR", "2026")
    monkeypatch.setenv("SONGSIM_OFFICIAL_COURSE_SEMESTER", "1")
    clear_settings_cache()

    settings = Settings()

    assert settings.official_course_year == 2026
    assert settings.official_course_semester == 1


def test_settings_parse_restaurant_cache_ttls(monkeypatch):
    monkeypatch.setenv("SONGSIM_RESTAURANT_CACHE_TTL_MINUTES", "360")
    monkeypatch.setenv("SONGSIM_RESTAURANT_CACHE_STALE_TTL_MINUTES", "1440")
    clear_settings_cache()

    settings = Settings()

    assert settings.restaurant_cache_ttl_minutes == 360
    assert settings.restaurant_cache_stale_ttl_minutes == 1440


def test_settings_parse_admin_enabled(monkeypatch):
    monkeypatch.setenv("SONGSIM_ADMIN_ENABLED", "true")
    clear_settings_cache()

    settings = Settings()

    assert settings.admin_enabled is True


def test_settings_parse_public_mode_and_urls(monkeypatch):
    monkeypatch.setenv("SONGSIM_APP_MODE", "public_readonly")
    monkeypatch.setenv("SONGSIM_PUBLIC_HTTP_URL", "https://songsim-api.onrender.com")
    monkeypatch.setenv("SONGSIM_PUBLIC_MCP_URL", "https://songsim-mcp.onrender.com/mcp")
    clear_settings_cache()

    settings = Settings()

    assert settings.app_mode == "public_readonly"
    assert settings.public_http_url == "https://songsim-api.onrender.com"
    assert settings.public_mcp_url == "https://songsim-mcp.onrender.com/mcp"


def test_settings_parse_automation_defaults(monkeypatch):
    monkeypatch.setenv("SONGSIM_AUTOMATION_ENABLED", "true")
    monkeypatch.setenv("SONGSIM_AUTOMATION_TICK_SECONDS", "30")
    monkeypatch.setenv("SONGSIM_AUTOMATION_SNAPSHOT_INTERVAL_MINUTES", "180")
    monkeypatch.setenv("SONGSIM_AUTOMATION_CACHE_CLEANUP_INTERVAL_MINUTES", "600")
    clear_settings_cache()

    settings = Settings()

    assert settings.automation_enabled is True
    assert settings.automation_tick_seconds == 30
    assert settings.automation_snapshot_interval_minutes == 180
    assert settings.automation_cache_cleanup_interval_minutes == 600


def test_env_example_documents_2026_first_semester_defaults():
    env_example = Path(__file__).resolve().parents[1] / ".env.example"
    text = env_example.read_text(encoding="utf-8")

    assert "SONGSIM_DATABASE_URL=postgresql://songsim:songsim@127.0.0.1:55432/songsim" in text
    assert "SONGSIM_ADMIN_ENABLED=false" in text
    assert "SONGSIM_APP_MODE=local_full" in text
    assert "SONGSIM_PUBLIC_HTTP_URL=" in text
    assert "SONGSIM_PUBLIC_MCP_URL=" in text
    assert "SONGSIM_AUTOMATION_ENABLED=false" in text
    assert "SONGSIM_AUTOMATION_TICK_SECONDS=60" in text
    assert "SONGSIM_AUTOMATION_SNAPSHOT_INTERVAL_MINUTES=360" in text
    assert "SONGSIM_AUTOMATION_CACHE_CLEANUP_INTERVAL_MINUTES=720" in text
    assert "SONGSIM_RESTAURANT_CACHE_TTL_MINUTES=360" in text
    assert "SONGSIM_RESTAURANT_CACHE_STALE_TTL_MINUTES=1440" in text
    assert "SONGSIM_OFFICIAL_COURSE_YEAR=2026" in text
    assert "SONGSIM_OFFICIAL_COURSE_SEMESTER=1" in text
