"""Postgres database layer using asyncpg.

All persistent state (conversations, messages, feedback, settings)
lives here. Tables are auto-created on startup.
"""

import json
import os
import uuid
from datetime import datetime, timezone

import asyncpg

_pool: asyncpg.Pool | None = None

INIT_SQL = """
CREATE TABLE IF NOT EXISTS agent_conversations (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    title TEXT NOT NULL DEFAULT 'Untitled',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_agent_conv_user ON agent_conversations(user_id);

CREATE TABLE IF NOT EXISTS agent_messages (
    id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES agent_conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    tool_calls JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_agent_msg_conv ON agent_messages(conversation_id);

CREATE TABLE IF NOT EXISTS agent_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    conversation_id UUID,
    message_index INT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('up', 'down')),
    explanation TEXT,
    message_content TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_settings (
    id INT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    sdk TEXT NOT NULL DEFAULT 'litellm',
    model TEXT NOT NULL DEFAULT 'gpt-4o-mini'
);
INSERT INTO agent_settings (id, sdk, model) VALUES (1, 'litellm', 'gpt-4o-mini')
ON CONFLICT (id) DO NOTHING;
"""


async def init_db():
    """Create connection pool and run table creation."""
    global _pool
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is required")
    _pool = await asyncpg.create_pool(database_url, min_size=2, max_size=10)
    async with _pool.acquire() as conn:
        await conn.execute(INIT_SQL)


async def close_db():
    """Close the connection pool."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def _get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database not initialized")
    return _pool


# ---- Conversations ----

async def list_conversations(user_id: str) -> dict:
    pool = _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT c.id, c.title, c.created_at, c.updated_at,
                   (SELECT COUNT(*) FROM agent_messages m WHERE m.conversation_id = c.id) as msg_count
            FROM agent_conversations c
            WHERE c.user_id = $1
            ORDER BY c.updated_at DESC
        """, uuid.UUID(user_id))
    return {
        "conversations": [
            {
                "id": str(r["id"]),
                "title": r["title"],
                "createdAt": r["created_at"].isoformat(),
                "updatedAt": r["updated_at"].isoformat(),
                "_count": {"messages": r["msg_count"]},
            }
            for r in rows
        ]
    }


async def get_conversation(conversation_id: str, user_id: str) -> dict:
    pool = _get_pool()
    async with pool.acquire() as conn:
        conv = await conn.fetchrow("""
            SELECT id, title FROM agent_conversations
            WHERE id = $1 AND user_id = $2
        """, uuid.UUID(conversation_id), uuid.UUID(user_id))
        if not conv:
            return {"error": "Conversation not found"}
        messages = await conn.fetch("""
            SELECT id, role, content, tool_calls, created_at
            FROM agent_messages WHERE conversation_id = $1
            ORDER BY created_at ASC
        """, uuid.UUID(conversation_id))
    return {
        "conversation": {
            "id": str(conv["id"]),
            "title": conv["title"],
            "messages": [
                {
                    "id": str(m["id"]),
                    "role": m["role"],
                    "content": m["content"],
                    "toolCalls": json.loads(m["tool_calls"]) if m["tool_calls"] else None,
                    "createdAt": m["created_at"].isoformat(),
                }
                for m in messages
            ],
        }
    }


async def create_conversation(conv_id: str, user_id: str, title: str) -> None:
    pool = _get_pool()
    now = datetime.now(timezone.utc)
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO agent_conversations (id, user_id, title, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5)
        """, uuid.UUID(conv_id), uuid.UUID(user_id), title, now, now)


async def add_message(
    conversation_id: str, msg_id: str, role: str, content: str,
    tool_calls: list | None = None,
) -> None:
    pool = _get_pool()
    tc = json.dumps(tool_calls) if tool_calls else None
    now = datetime.now(timezone.utc)
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO agent_messages (id, conversation_id, role, content, tool_calls, created_at)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6)
        """, uuid.UUID(msg_id), uuid.UUID(conversation_id), role, content, tc, now)
        await conn.execute("""
            UPDATE agent_conversations SET updated_at = $1 WHERE id = $2
        """, now, uuid.UUID(conversation_id))


async def delete_conversation(conversation_id: str, user_id: str) -> dict:
    pool = _get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            DELETE FROM agent_conversations WHERE id = $1 AND user_id = $2
        """, uuid.UUID(conversation_id), uuid.UUID(user_id))
    return {"success": True}


# ---- Feedback ----

async def add_feedback(
    user_id: str, conversation_id: str | None, message_index: int,
    direction: str, explanation: str | None, message_content: str | None,
) -> dict:
    pool = _get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO agent_feedback (user_id, conversation_id, message_index, direction, explanation, message_content)
            VALUES ($1, $2, $3, $4, $5, $6)
        """,
            uuid.UUID(user_id),
            uuid.UUID(conversation_id) if conversation_id else None,
            message_index, direction, explanation, message_content,
        )
    return {"success": True}


async def get_feedback_summary() -> dict:
    pool = _get_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM agent_feedback")
        up = await conn.fetchval("SELECT COUNT(*) FROM agent_feedback WHERE direction = 'up'")
        down = total - up
        recent = await conn.fetch("""
            SELECT user_id, conversation_id, message_index, direction,
                   explanation, message_content, created_at
            FROM agent_feedback ORDER BY created_at DESC LIMIT 20
        """)
    return {
        "total": total,
        "thumbsUp": up,
        "thumbsDown": down,
        "satisfactionRate": f"{(up / max(total, 1)) * 100:.0f}%",
        "recentEntries": [
            {
                "timestamp": r["created_at"].isoformat(),
                "userId": str(r["user_id"]),
                "conversationId": str(r["conversation_id"]) if r["conversation_id"] else None,
                "messageIndex": r["message_index"],
                "direction": r["direction"],
                "explanation": r["explanation"],
                "messageContent": r["message_content"],
            }
            for r in recent
        ],
    }


# ---- Settings ----

async def load_settings() -> dict:
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT sdk, model FROM agent_settings WHERE id = 1")
    if row:
        return {"sdk": row["sdk"], "model": row["model"]}
    return {"sdk": "litellm", "model": "gpt-4o-mini"}


async def save_settings(settings: dict) -> None:
    pool = _get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO agent_settings (id, sdk, model) VALUES (1, $1, $2)
            ON CONFLICT (id) DO UPDATE SET sdk = $1, model = $2
        """, settings.get("sdk", "litellm"), settings.get("model", "gpt-4o-mini"))
