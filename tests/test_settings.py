from __future__ import annotations

from pathlib import Path

from songsim_campus.settings import Settings, clear_settings_cache


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


def test_env_example_documents_2026_first_semester_defaults():
    env_example = Path(__file__).resolve().parents[1] / ".env.example"
    text = env_example.read_text(encoding="utf-8")

    assert "SONGSIM_OFFICIAL_COURSE_YEAR=2026" in text
    assert "SONGSIM_OFFICIAL_COURSE_SEMESTER=1" in text
