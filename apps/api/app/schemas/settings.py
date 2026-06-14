from pydantic import BaseModel, Field


class AppSettings(BaseModel):
    ai_base_url: str = Field(default="https://api.openai.com")
    ai_chat_path: str = Field(default="/v1/chat/completions")
    model: str = Field(default="gpt-4o-mini")
    api_key: str = Field(default="")
    vision_ai_base_url: str = Field(default="https://api.openai.com")
    vision_ai_chat_path: str = Field(default="/v1/chat/completions")
    vision_model: str = Field(default="")
    vision_api_key: str = Field(default="")


class SettingsConnectionTestResponse(BaseModel):
    ok: bool
    message: str
    model: str
