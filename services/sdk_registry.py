import json
import os
from sdks.base import BaseSDK
from sdks.openai_sdk import OpenAISDK
from sdks.anthropic_sdk import AnthropicSDK
from sdks.litellm_sdk import LiteLLMSDK
from sdks.langchain_sdk import LangChainSDK
from config import DEFAULT_SDK, DEFAULT_MODEL, DATA_DIR

SETTINGS_FILE = os.path.join(DATA_DIR, "agent_settings.json")

_SDK_MAP = {
    "openai": OpenAISDK,
    "anthropic": AnthropicSDK,
    "litellm": LiteLLMSDK,
    "langchain": LangChainSDK,
}

SDK_OPTIONS = [
    {"id": "litellm", "name": "LiteLLM (Universal)", "description": "Supports 100+ providers — just change the model string"},
    {"id": "openai", "name": "OpenAI Python SDK", "description": "Native OpenAI SDK with function calling"},
    {"id": "anthropic", "name": "Anthropic Python SDK", "description": "Native Anthropic SDK with tool_use"},
    {"id": "langchain", "name": "LangChain", "description": "LangChain agent with tool calling support"},
]

MODEL_OPTIONS = [
    {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "provider": "openai"},
    {"id": "gpt-4o", "name": "GPT-4o", "provider": "openai"},
    {"id": "gpt-4.1-mini", "name": "GPT-4.1 Mini", "provider": "openai"},
    {"id": "gpt-4.1", "name": "GPT-4.1", "provider": "openai"},
    {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet", "provider": "anthropic"},
    {"id": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6", "provider": "anthropic"},
]


def load_settings() -> dict:
    """Load settings from JSON file, falling back to defaults."""
    defaults = {"sdk": DEFAULT_SDK, "model": DEFAULT_MODEL}
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE) as f:
                saved = json.load(f)
            return {**defaults, **saved}
        except Exception:
            pass
    return defaults


def save_settings(settings: dict):
    """Persist settings to JSON file."""
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)


def get_sdk(sdk_name: str | None = None) -> BaseSDK:
    """Get an SDK adapter instance by name."""
    settings = load_settings()
    name = sdk_name or settings.get("sdk", DEFAULT_SDK)
    cls = _SDK_MAP.get(name)
    if not cls:
        raise ValueError(f"Unknown SDK: {name}. Available: {list(_SDK_MAP.keys())}")
    return cls()


def get_current_model() -> str:
    """Get the currently configured model."""
    settings = load_settings()
    return settings.get("model", DEFAULT_MODEL)
