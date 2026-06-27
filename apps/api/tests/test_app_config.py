from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def test_app_allows_additional_cors_origins_from_env(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://127.0.0.1:5174, http://localhost:5174")
    get_settings.cache_clear()

    response = TestClient(create_app()).options(
        "/api/files",
        headers={
            "Origin": "http://127.0.0.1:5174",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5174"

    get_settings.cache_clear()


def test_settings_exposes_structure_confidence_threshold(monkeypatch):
    monkeypatch.setenv("STRUCTURE_CONFIDENCE_THRESHOLD", "0.8")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.structure_confidence_threshold == 0.8

    get_settings.cache_clear()
