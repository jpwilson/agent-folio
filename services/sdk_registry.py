from config import DEFAULT_MODEL, DEFAULT_SDK
from sdks.anthropic_sdk import AnthropicSDK
from sdks.base import BaseSDK
from sdks.langchain_sdk import LangChainSDK
from sdks.litellm_sdk import LiteLLMSDK
from sdks.openai_sdk import OpenAISDK
from services import db

_SDK_MAP = {
    "openai": OpenAISDK,
    "anthropic": AnthropicSDK,
    "litellm": LiteLLMSDK,
    "langchain": LangChainSDK,
}

SDK_OPTIONS = [
    {
        "id": "litellm",
        "name": "LiteLLM (Universal)",
        "description": "Supports 100+ providers — just change the model string",
    },
    {"id": "openai", "name": "OpenAI Python SDK", "description": "Native OpenAI SDK with function calling"},
    {"id": "anthropic", "name": "Anthropic Python SDK", "description": "Native Anthropic SDK with tool_use"},
    {"id": "langchain", "name": "LangChain", "description": "LangChain agent with tool calling support"},
]

MODEL_OPTIONS = [
    # Ordered cheapest to most expensive
    {
        "id": "gpt-4o-mini",
        "name": "GPT-4o Mini",
        "provider": "openai",
        "description": "Fastest and cheapest OpenAI model. Great for simple queries. ~$0.15/$0.60 per 1M tokens.",
    },
    {
        "id": "gpt-4.1-mini",
        "name": "GPT-4.1 Mini",
        "provider": "openai",
        "description": "Latest small OpenAI model with improved instruction following. ~$0.40/$1.60 per 1M tokens.",
    },
    {
        "id": "claude-3-5-sonnet-20241022",
        "name": "Claude 3.5 Sonnet",
        "provider": "anthropic",
        "description": "Strong reasoning at mid-range cost. Good balance of quality and speed. ~$3/$15 per 1M tokens.",
    },
    {
        "id": "gpt-4o",
        "name": "GPT-4o",
        "provider": "openai",
        "description": "OpenAI's flagship model. High quality, multimodal. ~$2.50/$10 per 1M tokens.",
    },
    {
        "id": "gpt-4.1",
        "name": "GPT-4.1",
        "provider": "openai",
        "description": "Latest full-size OpenAI model. Best for complex analysis. ~$2/$8 per 1M tokens.",
    },
    {
        "id": "claude-sonnet-4-6",
        "name": "Claude Sonnet 4.6",
        "provider": "anthropic",
        "description": "Anthropic's latest model. Excellent reasoning and tool use. ~$3/$15 per 1M tokens.",
    },
]


async def load_settings() -> dict:
    """Load settings from Postgres."""
    return await db.load_settings()


async def save_settings(settings: dict):
    """Persist settings to Postgres."""
    await db.save_settings(settings)


def get_sdk(sdk_name: str | None = None) -> BaseSDK:
    """Get an SDK adapter instance by name."""
    name = sdk_name or DEFAULT_SDK
    cls = _SDK_MAP.get(name)
    if not cls:
        raise ValueError(f"Unknown SDK: {name}. Available: {list(_SDK_MAP.keys())}")
    return cls()


async def get_current_model() -> str:
    """Get the currently configured model."""
    settings = await db.load_settings()
    return settings.get("model", DEFAULT_MODEL)
