"""Tests for the /version endpoint."""

from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from api.main import app

    return TestClient(app)


def test_version_status_200(client: TestClient) -> None:
    response = client.get("/version")
    assert response.status_code == 200


def test_version_response_shape(client: TestClient) -> None:
    response = client.get("/version")
    data = response.json()
    assert "git_sha" in data
    assert "built_at" in data


def test_version_fallback_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GIT_SHA", raising=False)
    monkeypatch.delenv("BUILT_AT", raising=False)

    import api.main as main_module

    importlib.reload(main_module)
    test_client = TestClient(main_module.app)
    data = test_client.get("/version").json()
    assert data["git_sha"] == "unknown"
    assert data["built_at"] == "unknown"


def test_version_reads_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_SHA", "abc123")
    monkeypatch.setenv("BUILT_AT", "2025-01-01T00:00:00Z")

    import api.main as main_module

    importlib.reload(main_module)
    test_client = TestClient(main_module.app)
    data = test_client.get("/version").json()
    assert data["git_sha"] == "abc123"
    assert data["built_at"] == "2025-01-01T00:00:00Z"
