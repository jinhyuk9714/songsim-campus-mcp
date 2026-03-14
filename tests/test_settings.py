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


def test_env_example_documents_2026_first_semester_defaults():
    env_example = Path(__file__).resolve().parents[1] / ".env.example"
    text = env_example.read_text(encoding="utf-8")

    assert "SONGSIM_DATABASE_URL=postgresql://songsim:songsim@127.0.0.1:55432/songsim" in text
    assert "SONGSIM_ADMIN_ENABLED=false" in text
    assert "SONGSIM_RESTAURANT_CACHE_TTL_MINUTES=360" in text
    assert "SONGSIM_RESTAURANT_CACHE_STALE_TTL_MINUTES=1440" in text
    assert "SONGSIM_OFFICIAL_COURSE_YEAR=2026" in text
    assert "SONGSIM_OFFICIAL_COURSE_SEMESTER=1" in text
