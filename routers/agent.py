import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from models.schemas import ChatRequest
from auth import get_user_id, get_raw_token
from services import agent_service, db
from config import GHOSTFOLIO_URL

router = APIRouter(prefix="/api/v1/agent")


class LoginRequest(BaseModel):
    securityToken: str


@router.post("/auth/login")
async def login(body: LoginRequest):
    """Proxy login to Ghostfolio's anonymous auth endpoint."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(
                f"{GHOSTFOLIO_URL}/api/v1/auth/anonymous",
                json={"accessToken": body.securityToken},
            )
            if res.status_code == 403:
                raise HTTPException(status_code=401, detail="Invalid security token")
            res.raise_for_status()
            data = res.json()
            return {"authToken": data.get("authToken")}
    except httpx.HTTPStatusError:
        raise HTTPException(status_code=401, detail="Authentication failed")
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="Cannot reach Ghostfolio")


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
    return await agent_service.list_conversations(user_id)


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, request: Request):
    user_id = get_user_id(request)
    return await agent_service.get_conversation(conversation_id, user_id)


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, request: Request):
    user_id = get_user_id(request)
    return await agent_service.delete_conversation(conversation_id, user_id)


class FeedbackRequest(BaseModel):
    conversationId: str | None = None
    messageIndex: int
    direction: str
    explanation: str | None = None
    messageContent: str | None = None


@router.post("/feedback")
async def submit_feedback(request: Request, body: FeedbackRequest):
    user_id = get_user_id(request)
    return await db.add_feedback(
        user_id, body.conversationId, body.messageIndex,
        body.direction, body.explanation, body.messageContent,
    )


@router.get("/feedback/summary")
async def get_feedback_summary(request: Request):
    get_user_id(request)  # Auth check
    return await db.get_feedback_summary()
