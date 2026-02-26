from fastapi import APIRouter, Request
from models.schemas import ChatRequest
from auth import get_user_id, get_raw_token
from services import agent_service

router = APIRouter(prefix="/api/v1/agent")


@router.post("/chat")
async def chat(request: Request, body: ChatRequest):
    user_id = get_user_id(request)
    token = get_raw_token(request)
    result = await agent_service.chat(
        messages=body.messages,
        user_id=user_id,
        token=token,
        conversation_id=body.conversationId,
    )
    return result


@router.get("/conversations")
async def list_conversations(request: Request):
    user_id = get_user_id(request)
    return agent_service.list_conversations(user_id)


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, request: Request):
    user_id = get_user_id(request)
    return agent_service.get_conversation(conversation_id, user_id)


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, request: Request):
    user_id = get_user_id(request)
    return agent_service.delete_conversation(conversation_id, user_id)
