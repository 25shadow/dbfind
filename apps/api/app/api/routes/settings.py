from fastapi import APIRouter

from app.schemas.settings import AppSettings, SettingsConnectionTestResponse
from app.services.settings_service import SettingsService

router = APIRouter()


@router.get("", response_model=AppSettings)
async def get_settings() -> AppSettings:
    return SettingsService().get()


@router.put("", response_model=AppSettings)
async def update_settings(payload: AppSettings) -> AppSettings:
    return SettingsService().update(payload)


@router.post("/test-connection", response_model=SettingsConnectionTestResponse)
async def test_settings_connection(payload: AppSettings) -> SettingsConnectionTestResponse:
    return SettingsService().test_connection(payload)


@router.post("/test-vision", response_model=SettingsConnectionTestResponse)
async def test_vision_settings_connection(payload: AppSettings) -> SettingsConnectionTestResponse:
    return SettingsService().test_vision_connection(payload)
