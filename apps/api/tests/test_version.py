import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_version_status_200() -> None:
    response = client.get("/version")
    assert response.status_code == 200


def test_version_response_shape() -> None:
    response = client.get("/version")
    data = response.json()
    assert "git_sha" in data
    assert "built_at" in data


def test_version_fallback_to_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GIT_SHA", raising=False)
    monkeypatch.delenv("BUILT_AT", raising=False)
    response = client.get("/version")
    data = response.json()
    assert data["git_sha"] == "unknown"
    assert data["built_at"] == "unknown"


def test_version_reflects_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_SHA", "abc1234")
    monkeypatch.setenv("BUILT_AT", "2025-01-01T00:00:00Z")
    response = client.get("/version")
    data = response.json()
    assert data["git_sha"] == "abc1234"
    assert data["built_at"] == "2025-01-01T00:00:00Z"
