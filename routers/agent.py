import logging

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from auth import get_raw_token, get_user_id
from config import GHOSTFOLIO_URL, GRADER_TOKEN
from models.schemas import ChatRequest
from services import agent_service, db

logger = logging.getLogger(__name__)

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
            auth_token = data.get("authToken")

            # Auto-register Ghostfolio backend connection on login
            try:
                import json
                from base64 import b64decode

                payload = json.loads(b64decode(auth_token.split(".")[1] + "=="))
                uid = payload.get("id") or payload.get("sub") or ""
                if uid:
                    existing = await db.get_active_backends(uid)
                    has_gf = any(c["provider"] == "ghostfolio" for c in existing)
                    if not has_gf:
                        await db.add_backend_connection(
                            user_id=uid,
                            provider="ghostfolio",
                            base_url=GHOSTFOLIO_URL,
                            credentials={"security_token": body.securityToken},
                            label="Ghostfolio",
                        )
            except Exception:
                pass  # Auto-register is best-effort

            return {"authToken": auth_token}
    except httpx.HTTPStatusError:
        raise HTTPException(status_code=401, detail="Authentication failed") from None
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="Cannot reach Ghostfolio") from None


@router.get("/auth/grader-available")
async def grader_available():
    """Check if a grader demo account is configured."""
    return {"available": bool(GRADER_TOKEN)}


@router.post("/auth/grader-login")
async def grader_login():
    """Quick sign-in using the pre-configured grader demo account."""
    if not GRADER_TOKEN:
        raise HTTPException(status_code=404, detail="No grader account configured")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(
                f"{GHOSTFOLIO_URL}/api/v1/auth/anonymous",
                json={"accessToken": GRADER_TOKEN},
            )
            if res.status_code == 403:
                raise HTTPException(status_code=401, detail="Grader token is invalid")
            res.raise_for_status()
            data = res.json()
            return {"authToken": data.get("authToken")}
    except httpx.HTTPStatusError:
        raise HTTPException(status_code=401, detail="Grader authentication failed") from None
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="Cannot reach Ghostfolio") from None


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


@router.post("/chat/stream")
async def chat_stream(request: Request, body: ChatRequest):
    user_id = get_user_id(request)
    token = get_raw_token(request)
    return StreamingResponse(
        agent_service.chat_stream(
            messages=body.messages,
            user_id=user_id,
            token=token,
            conversation_id=body.conversationId,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
        user_id,
        body.conversationId,
        body.messageIndex,
        body.direction,
        body.explanation,
        body.messageContent,
    )


@router.get("/feedback/summary")
async def get_feedback_summary(request: Request):
    get_user_id(request)  # Auth check
    return await db.get_feedback_summary()


@router.get("/feedback/detail")
async def get_feedback_detail(request: Request):
    get_user_id(request)  # Auth check
    return await db.get_feedback_detail()


class UsernameRequest(BaseModel):
    username: str


@router.get("/profile")
async def get_profile(request: Request):
    user_id = get_user_id(request)
    username = await db.get_username(user_id)
    return {"userId": user_id, "username": username}


@router.put("/profile/username")
async def set_username(request: Request, body: UsernameRequest):
    user_id = get_user_id(request)
    await db.set_username(user_id, body.username)
    return {"success": True, "username": body.username.strip()[:50]}


# ---- Backend connections ----


class BackendConnectionRequest(BaseModel):
    provider: str
    label: str = ""
    baseUrl: str
    credentials: dict = {}


class BackendUpdateRequest(BaseModel):
    isActive: bool | None = None
    label: str | None = None
    baseUrl: str | None = None
    credentials: dict | None = None


@router.get("/backends")
async def list_backends(request: Request):
    """List user's backend connections (credentials redacted)."""
    user_id = get_user_id(request)
    connections = await db.list_backend_connections(user_id)
    return {"backends": connections}


@router.post("/backends")
async def add_backend(request: Request, body: BackendConnectionRequest):
    """Add a new backend connection."""
    user_id = get_user_id(request)
    if body.provider not in ("ghostfolio", "rotki"):
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {body.provider}")
    conn_id = await db.add_backend_connection(
        user_id=user_id,
        provider=body.provider,
        base_url=body.baseUrl,
        credentials=body.credentials,
        label=body.label,
    )
    return {"success": True, "id": conn_id}


@router.put("/backends/{connection_id}")
async def update_backend(connection_id: str, request: Request, body: BackendUpdateRequest):
    """Update a backend connection (toggle active, change label/URL)."""
    user_id = get_user_id(request)
    updated = await db.update_backend_connection(
        connection_id=connection_id,
        user_id=user_id,
        is_active=body.isActive,
        label=body.label,
        base_url=body.baseUrl,
        credentials=body.credentials,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Connection not found")
    return {"success": True}


@router.delete("/backends/{connection_id}")
async def delete_backend(connection_id: str, request: Request):
    """Remove a backend connection."""
    user_id = get_user_id(request)
    deleted = await db.delete_backend_connection(connection_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Connection not found")
    return {"success": True}


@router.post("/backends/{connection_id}/test")
async def test_backend(connection_id: str, request: Request):
    """Test connectivity to a backend."""
    user_id = get_user_id(request)
    backends = await db.get_active_backends(user_id)
    # Also check inactive backends
    all_backends = await db.list_backend_connections(user_id)
    # Find the connection (list_backend_connections redacts creds, so we use get_active_backends)
    # We need to get the full connection from db
    from services.db import _get_pool
    import uuid as uuid_mod

    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT provider, base_url, credentials FROM agent_backend_connections WHERE id = $1 AND user_id = $2",
            uuid_mod.UUID(connection_id),
            uuid_mod.UUID(user_id),
        )
    if not row:
        raise HTTPException(status_code=404, detail="Connection not found")

    import json
    connection = {
        "provider": row["provider"],
        "base_url": row["base_url"],
        "credentials": json.loads(row["credentials"]) if row["credentials"] else {},
    }

    try:
        from services.providers.factory import build_provider

        provider = await build_provider(connection)
        # Try a lightweight call to verify connectivity
        await provider.get_accounts()
        return {"success": True, "message": f"Connected to {row['provider']} successfully"}
    except Exception as e:
        return {"success": False, "message": f"Connection failed: {str(e)}"}
