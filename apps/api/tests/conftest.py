import pytest

from app.core.config import get_settings


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def temp_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path))
    get_settings.cache_clear()
    return tmp_path


@pytest.fixture
def reset_settings_cache():
    yield
    get_settings.cache_clear()
