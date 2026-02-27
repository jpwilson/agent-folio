from pydantic import BaseModel


class ChatRequest(BaseModel):
    messages: list[dict]
    conversationId: str | None = None


class ChatResponse(BaseModel):
    conversationId: str
    message: str
    toolCalls: list[dict]
    verification: dict


class SettingsUpdate(BaseModel):
    sdk: str | None = None
    model: str | None = None
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
