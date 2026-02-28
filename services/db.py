"""Postgres database layer using asyncpg.

All persistent state (conversations, messages, feedback, settings)
lives here. Tables are auto-created on startup.
"""

import json
import os
import uuid
from datetime import UTC, datetime

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
    followups JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_agent_msg_conv ON agent_messages(conversation_id);
-- Migration: add followups column if missing
ALTER TABLE agent_messages ADD COLUMN IF NOT EXISTS followups JSONB;

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

CREATE TABLE IF NOT EXISTS agent_user_profiles (
    user_id UUID PRIMARY KEY,
    username TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_eval_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model TEXT,
    cases_passed INT NOT NULL,
    cases_total INT NOT NULL,
    checks_passed INT NOT NULL,
    checks_total INT NOT NULL,
    duration_s REAL,
    snapshot_at TEXT,
    results JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_agent_eval_created ON agent_eval_runs(created_at DESC);
-- Migration: add snapshots column if missing
ALTER TABLE agent_eval_runs ADD COLUMN IF NOT EXISTS snapshots JSONB;

CREATE TABLE IF NOT EXISTS agent_portfolio_imports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    file_name TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','importing','completed','rolled_back','failed')),
    orders_created INT NOT NULL DEFAULT 0,
    order_ids JSONB,
    preview JSONB,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_agent_imports_user ON agent_portfolio_imports(user_id);
CREATE INDEX IF NOT EXISTS idx_agent_imports_hash ON agent_portfolio_imports(file_hash);

CREATE TABLE IF NOT EXISTS agent_backend_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    provider TEXT NOT NULL CHECK (provider IN ('ghostfolio', 'rotki')),
    label TEXT NOT NULL DEFAULT '',
    base_url TEXT NOT NULL,
    credentials JSONB NOT NULL DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_agent_backends_user ON agent_backend_connections(user_id);
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
        rows = await conn.fetch(
            """
            SELECT c.id, c.title, c.created_at, c.updated_at,
                   (SELECT COUNT(*) FROM agent_messages m WHERE m.conversation_id = c.id) as msg_count
            FROM agent_conversations c
            WHERE c.user_id = $1
            ORDER BY c.updated_at DESC
        """,
            uuid.UUID(user_id),
        )
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
        conv = await conn.fetchrow(
            """
            SELECT id, title FROM agent_conversations
            WHERE id = $1 AND user_id = $2
        """,
            uuid.UUID(conversation_id),
            uuid.UUID(user_id),
        )
        if not conv:
            return {"error": "Conversation not found"}
        messages = await conn.fetch(
            """
            SELECT id, role, content, tool_calls, followups, created_at
            FROM agent_messages WHERE conversation_id = $1
            ORDER BY created_at ASC
        """,
            uuid.UUID(conversation_id),
        )
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
                    "followups": json.loads(m["followups"]) if m["followups"] else None,
                    "createdAt": m["created_at"].isoformat(),
                }
                for m in messages
            ],
        }
    }


async def create_conversation(conv_id: str, user_id: str, title: str) -> None:
    pool = _get_pool()
    now = datetime.now(UTC)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO agent_conversations (id, user_id, title, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5)
        """,
            uuid.UUID(conv_id),
            uuid.UUID(user_id),
            title,
            now,
            now,
        )


async def add_message(
    conversation_id: str,
    msg_id: str,
    role: str,
    content: str,
    tool_calls: list | None = None,
    followups: list | None = None,
) -> None:
    pool = _get_pool()
    tc = json.dumps(tool_calls) if tool_calls else None
    fu = json.dumps(followups) if followups else None
    now = datetime.now(UTC)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO agent_messages (id, conversation_id, role, content, tool_calls, followups, created_at)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7)
        """,
            uuid.UUID(msg_id),
            uuid.UUID(conversation_id),
            role,
            content,
            tc,
            fu,
            now,
        )
        await conn.execute(
            """
            UPDATE agent_conversations SET updated_at = $1 WHERE id = $2
        """,
            now,
            uuid.UUID(conversation_id),
        )


async def delete_conversation(conversation_id: str, user_id: str) -> dict:
    pool = _get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            DELETE FROM agent_conversations WHERE id = $1 AND user_id = $2
        """,
            uuid.UUID(conversation_id),
            uuid.UUID(user_id),
        )
    return {"success": True}


# ---- Feedback ----


async def add_feedback(
    user_id: str,
    conversation_id: str | None,
    message_index: int,
    direction: str,
    explanation: str | None,
    message_content: str | None,
) -> dict:
    pool = _get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO agent_feedback (user_id, conversation_id, message_index, direction, explanation, message_content)
            VALUES ($1, $2, $3, $4, $5, $6)
        """,
            uuid.UUID(user_id),
            uuid.UUID(conversation_id) if conversation_id else None,
            message_index,
            direction,
            explanation,
            message_content,
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


async def get_feedback_detail() -> dict:
    """Rich feedback analytics: daily counts, per-conversation breakdown, classified reasons."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM agent_feedback")
        up = await conn.fetchval("SELECT COUNT(*) FROM agent_feedback WHERE direction = 'up'")
        down = total - up

        # Daily breakdown (last 30 days)
        daily = await conn.fetch("""
            SELECT DATE(created_at) AS day, direction, COUNT(*) AS cnt
            FROM agent_feedback
            WHERE created_at > NOW() - INTERVAL '30 days'
            GROUP BY DATE(created_at), direction
            ORDER BY day
        """)

        # Per-conversation summary
        per_conv = await conn.fetch("""
            SELECT f.conversation_id,
                   COALESCE(c.title, 'Unknown') AS title,
                   SUM(CASE WHEN f.direction = 'up' THEN 1 ELSE 0 END) AS ups,
                   SUM(CASE WHEN f.direction = 'down' THEN 1 ELSE 0 END) AS downs,
                   COUNT(*) AS total
            FROM agent_feedback f
            LEFT JOIN agent_conversations c ON f.conversation_id = c.id
            WHERE f.conversation_id IS NOT NULL
            GROUP BY f.conversation_id, c.title
            ORDER BY total DESC
            LIMIT 20
        """)

        # All entries (last 50 — includes explanations)
        all_entries = await conn.fetch("""
            SELECT f.user_id, f.conversation_id, f.message_index, f.direction,
                   f.explanation, f.message_content, f.created_at,
                   COALESCE(c.title, 'Unknown') AS conv_title
            FROM agent_feedback f
            LEFT JOIN agent_conversations c ON f.conversation_id = c.id
            ORDER BY f.created_at DESC LIMIT 50
        """)

    # Build daily chart data
    day_map: dict[str, dict] = {}
    for r in daily:
        d = r["day"].isoformat()
        if d not in day_map:
            day_map[d] = {"up": 0, "down": 0}
        day_map[d][r["direction"]] = r["cnt"]

    return {
        "total": total,
        "thumbsUp": up,
        "thumbsDown": down,
        "satisfactionRate": f"{(up / max(total, 1)) * 100:.0f}%",
        "dailyChart": [{"date": d, "up": v["up"], "down": v["down"]} for d, v in sorted(day_map.items())],
        "perConversation": [
            {
                "conversationId": str(r["conversation_id"]) if r["conversation_id"] else None,
                "title": r["title"],
                "ups": r["ups"],
                "downs": r["downs"],
                "total": r["total"],
            }
            for r in per_conv
        ],
        "entries": [
            {
                "timestamp": r["created_at"].isoformat(),
                "userId": str(r["user_id"]),
                "conversationId": str(r["conversation_id"]) if r["conversation_id"] else None,
                "convTitle": r["conv_title"],
                "messageIndex": r["message_index"],
                "direction": r["direction"],
                "explanation": r["explanation"],
                "messageContent": r["message_content"],
            }
            for r in all_entries
        ],
    }


# ---- User Profiles ----


async def get_username(user_id: str) -> str | None:
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT username FROM agent_user_profiles WHERE user_id = $1",
            uuid.UUID(user_id),
        )
    return row["username"] if row else None


async def set_username(user_id: str, username: str) -> None:
    pool = _get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO agent_user_profiles (user_id, username) VALUES ($1, $2)
            ON CONFLICT (user_id) DO UPDATE SET username = $2
        """,
            uuid.UUID(user_id),
            username.strip()[:50],
        )


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
        await conn.execute(
            """
            INSERT INTO agent_settings (id, sdk, model) VALUES (1, $1, $2)
            ON CONFLICT (id) DO UPDATE SET sdk = $1, model = $2
        """,
            settings.get("sdk", "litellm"),
            settings.get("model", "gpt-4o-mini"),
        )


# ---- Eval Runs ----


async def save_eval_run(
    model: str,
    cases_passed: int,
    cases_total: int,
    checks_passed: int,
    checks_total: int,
    duration_s: float | None,
    snapshot_at: str | None,
    results: list | None,
    snapshots: list | None = None,
) -> str:
    pool = _get_pool()
    run_id = str(uuid.uuid4())
    results_json = json.dumps(results) if results else None
    snapshots_json = json.dumps(snapshots) if snapshots else None
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO agent_eval_runs
                (id, model, cases_passed, cases_total, checks_passed, checks_total,
                 duration_s, snapshot_at, results, snapshots)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10::jsonb)
        """,
            uuid.UUID(run_id),
            model,
            cases_passed,
            cases_total,
            checks_passed,
            checks_total,
            duration_s,
            snapshot_at,
            results_json,
            snapshots_json,
        )
    return run_id


async def get_eval_run(run_id: str) -> dict | None:
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, model, cases_passed, cases_total, checks_passed, checks_total,
                   duration_s, snapshot_at, results, created_at
            FROM agent_eval_runs WHERE id = $1
        """,
            uuid.UUID(run_id),
        )
    if not row:
        return None
    return {
        "id": str(row["id"]),
        "model": row["model"],
        "casesPassed": row["cases_passed"],
        "casesTotal": row["cases_total"],
        "checksPassed": row["checks_passed"],
        "checksTotal": row["checks_total"],
        "durationS": row["duration_s"],
        "snapshotAt": row["snapshot_at"],
        "results": json.loads(row["results"]) if row["results"] else None,
        "createdAt": row["created_at"].isoformat(),
    }


async def get_latest_snapshots() -> list | None:
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT snapshots FROM agent_eval_runs
            WHERE snapshots IS NOT NULL
            ORDER BY created_at DESC LIMIT 1
        """
        )
    if row and row["snapshots"]:
        return json.loads(row["snapshots"])
    return None


async def list_eval_runs(limit: int = 20) -> list:
    pool = _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, model, cases_passed, cases_total, checks_passed, checks_total,
                   duration_s, snapshot_at, created_at
            FROM agent_eval_runs
            ORDER BY created_at DESC
            LIMIT $1
        """,
            limit,
        )
    return [
        {
            "id": str(r["id"]),
            "model": r["model"],
            "casesPassed": r["cases_passed"],
            "casesTotal": r["cases_total"],
            "checksPassed": r["checks_passed"],
            "checksTotal": r["checks_total"],
            "durationS": r["duration_s"],
            "snapshotAt": r["snapshot_at"],
            "createdAt": r["created_at"].isoformat(),
        }
        for r in rows
    ]


# ---- Portfolio Imports ----


async def save_import(user_id: str, file_name: str, file_hash: str, preview: list | None) -> str:
    pool = _get_pool()
    import_id = str(uuid.uuid4())
    preview_json = json.dumps(preview) if preview else None
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO agent_portfolio_imports (id, user_id, file_name, file_hash, preview)
            VALUES ($1, $2, $3, $4, $5::jsonb)
        """,
            uuid.UUID(import_id),
            uuid.UUID(user_id),
            file_name,
            file_hash,
            preview_json,
        )
    return import_id


async def update_import_status(
    import_id: str,
    status: str,
    orders_created: int | None = None,
    order_ids: list | None = None,
    error_message: str | None = None,
) -> None:
    pool = _get_pool()
    oids = json.dumps(order_ids) if order_ids else None
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE agent_portfolio_imports
            SET status = $2,
                orders_created = COALESCE($3, orders_created),
                order_ids = COALESCE($4::jsonb, order_ids),
                error_message = $5
            WHERE id = $1
        """,
            uuid.UUID(import_id),
            status,
            orders_created,
            oids,
            error_message,
        )


async def get_import_by_hash(user_id: str, file_hash: str) -> dict | None:
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, file_name, status, created_at
            FROM agent_portfolio_imports
            WHERE user_id = $1 AND file_hash = $2 AND status != 'rolled_back'
        """,
            uuid.UUID(user_id),
            file_hash,
        )
    if not row:
        return None
    return {
        "id": str(row["id"]),
        "fileName": row["file_name"],
        "status": row["status"],
        "createdAt": row["created_at"].isoformat(),
    }


async def list_imports(user_id: str) -> list:
    pool = _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, file_name, file_hash, status, orders_created, error_message, created_at
            FROM agent_portfolio_imports
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT 50
        """,
            uuid.UUID(user_id),
        )
    return [
        {
            "id": str(r["id"]),
            "fileName": r["file_name"],
            "fileHash": r["file_hash"],
            "status": r["status"],
            "ordersCreated": r["orders_created"],
            "errorMessage": r["error_message"],
            "createdAt": r["created_at"].isoformat(),
        }
        for r in rows
    ]


async def get_import(import_id: str, user_id: str) -> dict | None:
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, file_name, file_hash, status, orders_created, order_ids, preview,
                   error_message, created_at
            FROM agent_portfolio_imports
            WHERE id = $1 AND user_id = $2
        """,
            uuid.UUID(import_id),
            uuid.UUID(user_id),
        )
    if not row:
        return None
    return {
        "id": str(row["id"]),
        "fileName": row["file_name"],
        "fileHash": row["file_hash"],
        "status": row["status"],
        "ordersCreated": row["orders_created"],
        "orderIds": json.loads(row["order_ids"]) if row["order_ids"] else None,
        "preview": json.loads(row["preview"]) if row["preview"] else None,
        "errorMessage": row["error_message"],
        "createdAt": row["created_at"].isoformat(),
    }


# ---- Backend Connections ----


async def list_backend_connections(user_id: str) -> list:
    pool = _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, provider, label, base_url, credentials, is_active, created_at
            FROM agent_backend_connections
            WHERE user_id = $1
            ORDER BY created_at ASC
        """,
            uuid.UUID(user_id),
        )
    return [
        {
            "id": str(r["id"]),
            "provider": r["provider"],
            "label": r["label"],
            "baseUrl": r["base_url"],
            "credentials": _redact_credentials(json.loads(r["credentials"]) if r["credentials"] else {}),
            "isActive": r["is_active"],
            "createdAt": r["created_at"].isoformat(),
        }
        for r in rows
    ]


def _redact_credentials(creds: dict) -> dict:
    """Return credentials with sensitive values masked."""
    redacted = {}
    for k, v in creds.items():
        if isinstance(v, str) and len(v) > 4:
            redacted[k] = v[:2] + "*" * (len(v) - 4) + v[-2:]
        else:
            redacted[k] = "***"
    return redacted


async def add_backend_connection(
    user_id: str,
    provider: str,
    base_url: str,
    credentials: dict,
    label: str = "",
) -> str:
    pool = _get_pool()
    conn_id = str(uuid.uuid4())
    creds_json = json.dumps(credentials)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO agent_backend_connections (id, user_id, provider, label, base_url, credentials)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb)
        """,
            uuid.UUID(conn_id),
            uuid.UUID(user_id),
            provider,
            label.strip()[:100],
            base_url.strip().rstrip("/"),
            creds_json,
        )
    return conn_id


async def update_backend_connection(
    connection_id: str,
    user_id: str,
    is_active: bool | None = None,
    label: str | None = None,
    base_url: str | None = None,
    credentials: dict | None = None,
) -> bool:
    pool = _get_pool()
    updates = []
    params = [uuid.UUID(connection_id), uuid.UUID(user_id)]
    idx = 3

    if is_active is not None:
        updates.append(f"is_active = ${idx}")
        params.append(is_active)
        idx += 1
    if label is not None:
        updates.append(f"label = ${idx}")
        params.append(label.strip()[:100])
        idx += 1
    if base_url is not None:
        updates.append(f"base_url = ${idx}")
        params.append(base_url.strip().rstrip("/"))
        idx += 1
    if credentials is not None:
        updates.append(f"credentials = ${idx}::jsonb")
        params.append(json.dumps(credentials))
        idx += 1

    if not updates:
        return False

    sql = f"UPDATE agent_backend_connections SET {', '.join(updates)} WHERE id = $1 AND user_id = $2"
    async with pool.acquire() as conn:
        result = await conn.execute(sql, *params)
    return result == "UPDATE 1"


async def delete_backend_connection(connection_id: str, user_id: str) -> bool:
    pool = _get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM agent_backend_connections WHERE id = $1 AND user_id = $2",
            uuid.UUID(connection_id),
            uuid.UUID(user_id),
        )
    return result == "DELETE 1"


async def get_active_backends(user_id: str) -> list:
    """Return active backend connections with full (unredacted) credentials."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, provider, label, base_url, credentials, is_active, created_at
            FROM agent_backend_connections
            WHERE user_id = $1 AND is_active = TRUE
            ORDER BY created_at ASC
        """,
            uuid.UUID(user_id),
        )
    return [
        {
            "id": str(r["id"]),
            "provider": r["provider"],
            "label": r["label"],
            "base_url": r["base_url"],
            "credentials": json.loads(r["credentials"]) if r["credentials"] else {},
        }
        for r in rows
    ]
