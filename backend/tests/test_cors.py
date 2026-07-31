import pytest
from fastapi.testclient import TestClient

import config
from main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _configure_cors(monkeypatch):
    monkeypatch.setattr(
        config,
        "ALLOWED_ORIGINS",
        ["http://localhost:5173", "https://frontend.example.com"],
    )


@pytest.mark.parametrize(
    "path,method",
    [
        ("/api/profile", "GET"),
        ("/api/generate-menu", "POST"),
    ],
)
def test_cors_preflight_allows_authorization_header(client, path, method):
    response = client.options(
        path,
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    allowed_headers = (response.headers.get("access-control-allow-headers") or "").lower()
    assert "authorization" in allowed_headers
