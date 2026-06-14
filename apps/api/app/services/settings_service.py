import json
import os
from pathlib import Path

import httpx

from app.core.config import get_settings
from app.schemas.settings import AppSettings, SettingsConnectionTestResponse


class SettingsService:
    def __init__(self) -> None:
        settings = get_settings()
        self.settings_path = Path(settings.workspace_dir) / "settings.json"
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)

    def get(self) -> AppSettings:
        if not self.settings_path.exists():
            return self._from_env()

        data = json.loads(self.settings_path.read_text(encoding="utf-8"))
        data.setdefault("vision_ai_base_url", data.get("ai_base_url", AppSettings.model_fields["ai_base_url"].default))
        data.setdefault("vision_ai_chat_path", data.get("ai_chat_path", AppSettings.model_fields["ai_chat_path"].default))
        return AppSettings(**data)

    def update(self, payload: AppSettings) -> AppSettings:
        self.settings_path.write_text(
            payload.model_dump_json(indent=2),
            encoding="utf-8",
        )
        return payload

    def test_connection(self, payload: AppSettings) -> SettingsConnectionTestResponse:
        url = f"{payload.ai_base_url.rstrip('/')}{payload.ai_chat_path}"
        headers = {"Content-Type": "application/json"}
        if payload.api_key:
            headers["Authorization"] = f"Bearer {payload.api_key}"

        request_body = {
            "model": payload.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": "You are a connection test responder."},
                {"role": "user", "content": "Reply with OK."},
            ],
            "max_tokens": 8,
        }

        try:
            with httpx.Client(timeout=20) as client:
                response = client.post(url, json=request_body, headers=headers)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            detail = self._response_error_text(exc.response)
            return SettingsConnectionTestResponse(
                ok=False,
                message=f"连接失败：HTTP {exc.response.status_code}。{detail}",
                model=payload.model,
            )
        except Exception as exc:
            return SettingsConnectionTestResponse(
                ok=False,
                message=f"连接失败：{exc}",
                model=payload.model,
            )

        content = self._extract_message_content(data)
        return SettingsConnectionTestResponse(
            ok=True,
            message=f"连接成功，模型已响应：{content or 'OK'}",
            model=payload.model,
        )

    def test_vision_connection(self, payload: AppSettings) -> SettingsConnectionTestResponse:
        if not payload.vision_model:
            return SettingsConnectionTestResponse(
                ok=False,
                message="请先填写视觉模型名",
                model="",
            )

        url = f"{payload.vision_ai_base_url.rstrip('/')}{payload.vision_ai_chat_path}"
        headers = {"Content-Type": "application/json"}
        if payload.vision_api_key:
            headers["Authorization"] = f"Bearer {payload.vision_api_key}"

        request_body = {
            "model": payload.vision_model,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a vision capability test responder. Reply with VISION_OK.",
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Read this small image and reply with VISION_OK."},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": (
                                    "data:image/png;base64,"
                                    "iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAIAAAAmkwkpAAAAFElEQVR4nGP8//8/AwwwMSAB3BwAlm4DBfIlvvkAAAAASUVORK5CYII="
                                ),
                                "detail": "low",
                            },
                        },
                    ],
                },
            ],
            "max_tokens": 16,
        }

        try:
            with httpx.Client(timeout=30) as client:
                response = client.post(url, json=request_body, headers=headers)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            detail = self._response_error_text(exc.response)
            return SettingsConnectionTestResponse(
                ok=False,
                message=f"视觉模型连接失败：HTTP {exc.response.status_code}。{detail}",
                model=payload.vision_model,
            )
        except Exception as exc:
            return SettingsConnectionTestResponse(
                ok=False,
                message=f"视觉模型连接失败：{exc}",
                model=payload.vision_model,
            )

        content = self._extract_message_content(data)
        ok = "VISION_OK" in content.upper()
        return SettingsConnectionTestResponse(
            ok=ok,
            message=(
                f"视觉模型已响应：{content or '空响应'}"
                if ok
                else f"接口有响应，但不像支持图片输入：{content or '空响应'}"
            ),
            model=payload.vision_model,
        )

    def _from_env(self) -> AppSettings:
        return AppSettings(
            ai_base_url=os.getenv("AI_BASE_URL", AppSettings.model_fields["ai_base_url"].default),
            ai_chat_path=os.getenv("AI_CHAT_PATH", AppSettings.model_fields["ai_chat_path"].default),
            model=os.getenv("AI_MODEL", AppSettings.model_fields["model"].default),
            api_key=os.getenv("AI_API_KEY", AppSettings.model_fields["api_key"].default),
            vision_ai_base_url=os.getenv(
                "VISION_AI_BASE_URL",
                os.getenv("AI_BASE_URL", AppSettings.model_fields["vision_ai_base_url"].default),
            ),
            vision_ai_chat_path=os.getenv(
                "VISION_AI_CHAT_PATH",
                os.getenv("AI_CHAT_PATH", AppSettings.model_fields["vision_ai_chat_path"].default),
            ),
            vision_model=os.getenv("VISION_MODEL", AppSettings.model_fields["vision_model"].default),
            vision_api_key=os.getenv("VISION_API_KEY", AppSettings.model_fields["vision_api_key"].default),
        )

    def _extract_message_content(self, data: dict) -> str:
        if "choices" in data and data["choices"]:
            choice = data["choices"][0]
            message = choice.get("message") or {}
            return str(message.get("content") or choice.get("text") or "").strip()
        return ""

    def _response_error_text(self, response: httpx.Response) -> str:
        try:
            data = response.json()
        except ValueError:
            return response.text[:300]

        if isinstance(data, dict):
            error = data.get("error")
            if isinstance(error, dict):
                return str(error.get("message") or error)[:300]
            return str(data.get("message") or data)[:300]

        return str(data)[:300]
