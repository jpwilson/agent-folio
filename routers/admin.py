from fastapi import APIRouter
from models.schemas import SettingsUpdate
from services.sdk_registry import (
    load_settings,
    save_settings,
    SDK_OPTIONS,
    MODEL_OPTIONS,
)
from config import OPENAI_API_KEY, ANTHROPIC_API_KEY
import config

router = APIRouter(prefix="/api/v1/agent/admin")


@router.get("/settings")
async def get_settings():
    settings = load_settings()
    return {
        "sdk": settings.get("sdk"),
        "model": settings.get("model"),
        "hasOpenaiKey": bool(OPENAI_API_KEY),
        "hasAnthropicKey": bool(ANTHROPIC_API_KEY),
        "sdkOptions": SDK_OPTIONS,
        "modelOptions": MODEL_OPTIONS,
    }


@router.put("/settings")
async def update_settings(body: SettingsUpdate):
    settings = load_settings()

    if body.sdk is not None:
        settings["sdk"] = body.sdk
    if body.model is not None:
        settings["model"] = body.model
    if body.openai_api_key is not None:
        config.OPENAI_API_KEY = body.openai_api_key
    if body.anthropic_api_key is not None:
        config.ANTHROPIC_API_KEY = body.anthropic_api_key

    save_settings(settings)
    return {"success": True, "settings": settings}
