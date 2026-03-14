from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from songsim_campus.api import create_app
from songsim_campus.settings import clear_settings_cache


@pytest.fixture()
def app_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("SONGSIM_DATABASE_PATH", str(db_path))
    monkeypatch.setenv("SONGSIM_SEED_DEMO_ON_START", "true")
    monkeypatch.setenv("SONGSIM_SYNC_OFFICIAL_ON_START", "false")
    clear_settings_cache()
    yield db_path
    clear_settings_cache()
    os.environ.pop("SONGSIM_DATABASE_PATH", None)
    os.environ.pop("SONGSIM_SEED_DEMO_ON_START", None)
    os.environ.pop("SONGSIM_SYNC_OFFICIAL_ON_START", None)


@pytest.fixture()
def client(app_env: Path):
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
