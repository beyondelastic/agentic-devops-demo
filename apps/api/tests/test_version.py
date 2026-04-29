import importlib
import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(monkeypatch):
    """Return a TestClient with a freshly imported app so env vars take effect."""
    monkeypatch.setenv("GIT_SHA", "abc123")
    monkeypatch.setenv("BUILT_AT", "2024-01-01T00:00:00Z")
    # Re-import to pick up monkeypatched env vars (settings are module-level in main)
    import api.main as main_mod

    importlib.reload(main_mod)
    return TestClient(main_mod.app)


def test_version_status(client):
    resp = client.get("/version")
    assert resp.status_code == 200


def test_version_shape(client):
    resp = client.get("/version")
    data = resp.json()
    assert "git_sha" in data
    assert "built_at" in data


def test_version_values(client):
    resp = client.get("/version")
    data = resp.json()
    assert data["git_sha"] == "abc123"
    assert data["built_at"] == "2024-01-01T00:00:00Z"


def test_version_fallback_to_unknown(monkeypatch):
    monkeypatch.delenv("GIT_SHA", raising=False)
    monkeypatch.delenv("BUILT_AT", raising=False)
    import api.main as main_mod

    importlib.reload(main_mod)
    c = TestClient(main_mod.app)
    data = c.get("/version").json()
    assert data["git_sha"] == "unknown"
    assert data["built_at"] == "unknown"
