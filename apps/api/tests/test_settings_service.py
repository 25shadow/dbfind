import json

from app.core.config import get_settings
from app.services.settings_service import SettingsService


def test_settings_service_reads_legacy_settings_without_vision_fields(temp_workspace):
    settings_path = temp_workspace / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "ai_base_url": "https://example.test",
                "ai_chat_path": "/v1/chat/completions",
                "model": "chat-model",
                "api_key": "chat-key",
            }
        ),
        encoding="utf-8",
    )
    get_settings.cache_clear()

    settings = SettingsService().get()

    assert settings.vision_ai_base_url == "https://example.test"
    assert settings.vision_ai_chat_path == "/v1/chat/completions"
    assert settings.vision_model == ""
    assert settings.vision_api_key == ""
