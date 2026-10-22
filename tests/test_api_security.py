"""Verify that protected NEXORA endpoints reject anonymous requests."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.auth import validate_access_token


PROTECTED_ENDPOINTS = [
    ("POST", "/api/v1/analytics/ask"),
    ("GET", "/api/v1/model/test"),
    ("POST", "/api/v1/documents/ask"),
    ("GET", "/api/v1/auth/me"),
    ("POST", "/api/v1/copilot/ask"),
]


@pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
def test_protected_endpoint_rejects_anonymous_user(method, path):
    # Ensure this test never bypasses authentication via dependency overrides.
    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides.clear()

    try:
        # Invalid payloads are intentional: authentication should run first.
        with TestClient(app) as client:
            response = client.request(method, path, json={} if method == "POST" else None)

        assert response.status_code == 401, (
            f"{method} {path} returned {response.status_code}, expected 401"
        )
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)


def test_health_endpoint_remains_public():
    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides.clear()

    try:
        with TestClient(app) as client:
            response = client.get("/health")

        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)
