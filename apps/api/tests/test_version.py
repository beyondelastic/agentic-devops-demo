"""Tests for the /version endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.settings import Settings, get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_version_returns_200():
    with TestClient(app) as client:
        response = client.get("/version")
    assert response.status_code == 200


def test_version_response_shape():
    with TestClient(app) as client:
        response = client.get("/version")
    body = response.json()
    assert "git_sha" in body
    assert "built_at" in body


def test_version_uses_env_vars(monkeypatch):
    monkeypatch.setenv("GIT_SHA", "abc1234")
    monkeypatch.setenv("BUILT_AT", "2024-01-01T00:00:00Z")
    app.dependency_overrides[get_settings] = lambda: Settings()
    try:
        with TestClient(app) as client:
            response = client.get("/version")
        body = response.json()
        assert body["git_sha"] == "abc1234"
        assert body["built_at"] == "2024-01-01T00:00:00Z"
    finally:
        app.dependency_overrides.clear()


def test_version_falls_back_to_unknown(monkeypatch):
    monkeypatch.delenv("GIT_SHA", raising=False)
    monkeypatch.delenv("BUILT_AT", raising=False)
    app.dependency_overrides[get_settings] = lambda: Settings()
    try:
        with TestClient(app) as client:
            response = client.get("/version")
        body = response.json()
        assert body["git_sha"] == "unknown"
        assert body["built_at"] == "unknown"
    finally:
        app.dependency_overrides.clear()
