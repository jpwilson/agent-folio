from pydantic import BaseModel
from typing import Optional


class ChatRequest(BaseModel):
    messages: list[dict]
    conversationId: Optional[str] = None


class ChatResponse(BaseModel):
    conversationId: str
    message: str
    toolCalls: list[dict]
    verification: dict


class SettingsUpdate(BaseModel):
    sdk: Optional[str] = None
    model: Optional[str] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
