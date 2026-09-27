"""Offline mode blocks egress-capable endpoints and leaves the rest alone."""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.offline import is_blocked

EGRESS = [
    ("POST", "/api/hermes/update"),
    ("POST", "/api/gateway/restart"),
    ("POST", "/api/plugins/install"),
    ("POST", "/api/plugins/demo/update"),
    ("POST", "/api/chat/sessions/abc/send"),
    ("POST", "/api/chat/sessions/abc/message"),
    ("POST", "/api/cron"),
    ("POST", "/api/cron/job1/run"),
]


@pytest.mark.parametrize("method,path", EGRESS)
def test_egress_endpoints_are_blocked(method, path):
    assert is_blocked(method, path)


@pytest.mark.parametrize("method,path", [
    ("GET", "/api/health"),
    ("POST", "/api/cron/job1/pause"),
    ("POST", "/api/plugins/demo/enable"),
    ("POST", "/api/replay/runs/s1/publish"),
    ("GET", "/api/plugins/install"),
])
def test_local_endpoints_are_not_blocked(method, path):
    assert not is_blocked(method, path)


def test_middleware_returns_403_only_when_offline(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    client = TestClient(app)
    monkeypatch.setenv("HERMES_HUD_OFFLINE", "1")
    r = client.post("/api/hermes/update")
    assert r.status_code == 403
    assert "Offline mode" in r.json()["detail"]
    monkeypatch.delenv("HERMES_HUD_OFFLINE")
    r = client.post("/api/hermes/update")
    assert r.status_code != 403 or "Offline mode" not in r.text
