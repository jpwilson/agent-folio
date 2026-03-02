import json
import os
import time

import httpx
import yaml
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

import config
from auth import get_raw_token, get_user_id
from config import GHOSTFOLIO_URL
from models.schemas import SettingsUpdate
from services import db
from services.ghostfolio_client import GhostfolioClient
from services.sdk_registry import (
    MODEL_OPTIONS,
    SDK_OPTIONS,
    load_settings,
    save_settings,
)

router = APIRouter(prefix="/api/v1/agent/admin")

LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", os.getenv("LANGFUSE_BASEURL", "https://cloud.langfuse.com"))

EVAL_DIR = os.path.join(os.path.dirname(__file__), "..", "eval")
GOLDEN_PATH = os.path.join(EVAL_DIR, "golden_data.yaml")
SNAPSHOT_PATH = os.path.join(EVAL_DIR, "eval-snapshots.json")


@router.get("/settings")
async def get_settings():
    settings = await load_settings()
    return {
        "sdk": settings.get("sdk"),
        "model": settings.get("model"),
        "hasOpenaiKey": bool(config.OPENAI_API_KEY),
        "hasAnthropicKey": bool(config.ANTHROPIC_API_KEY),
        "hasOpenrouterKey": bool(config.OPENROUTER_API_KEY),
        "sdkOptions": SDK_OPTIONS,
        "modelOptions": MODEL_OPTIONS,
    }


@router.put("/settings")
async def update_settings(body: SettingsUpdate):
    settings = await load_settings()

    if body.sdk is not None:
        settings["sdk"] = body.sdk
    if body.model is not None:
        settings["model"] = body.model
    if body.openai_api_key is not None:
        config.OPENAI_API_KEY = body.openai_api_key
    if body.anthropic_api_key is not None:
        config.ANTHROPIC_API_KEY = body.anthropic_api_key
    if body.openrouter_api_key is not None:
        config.OPENROUTER_API_KEY = body.openrouter_api_key

    await save_settings(settings)
    return {"success": True, "settings": settings}


# ---- Eval endpoints ----


@router.get("/eval/golden")
async def get_golden_cases():
    """Return the golden test cases."""
    with open(GOLDEN_PATH) as f:
        cases = yaml.safe_load(f)
    return {"cases": cases, "count": len(cases)}


@router.post("/eval/snapshot")
async def run_snapshot(request: Request):
    """Generate snapshots by hitting the live agent with each test case.

    This makes real LLM calls — costs tokens.
    Requires Authorization header (forwarded to chat endpoint).
    """
    auth_header = request.headers.get("Authorization", "")

    with open(GOLDEN_PATH) as f:
        golden_cases = yaml.safe_load(f)

    # Determine base URL (call ourselves)
    # Behind a reverse proxy (Railway), base_url is http:// but we need https://
    base_url = str(request.base_url).rstrip("/")
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    if forwarded_proto == "https":
        base_url = base_url.replace("http://", "https://")
    chat_url = f"{base_url}/api/v1/agent/chat"

    snapshots = []
    errors = []

    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        for gc in golden_cases:
            start = time.time()
            try:
                res = await client.post(
                    chat_url,
                    json={"messages": [{"role": "user", "content": gc["query"]}]},
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": auth_header,
                    },
                )
                duration_ms = int((time.time() - start) * 1000)

                if res.status_code != 200:
                    errors.append({"id": gc["id"], "error": f"HTTP {res.status_code}"})
                    continue

                data = res.json()
                snapshots.append(
                    {
                        "id": gc["id"],
                        "query": gc["query"],
                        "category": gc["category"],
                        "response": data.get("message", ""),
                        "toolCalls": [tc["tool"] for tc in (data.get("toolCalls") or [])],
                        "verified": data.get("verification", {}).get("verified"),
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "durationMs": duration_ms,
                    }
                )
            except Exception as e:
                errors.append({"id": gc["id"], "error": str(e)})

    # Save snapshot file (local) and to DB (persists across deploys)
    generated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    snapshot_file = {
        "generatedAt": generated_at,
        "apiUrl": chat_url,
        "snapshots": snapshots,
    }
    with open(SNAPSHOT_PATH, "w") as f:
        json.dump(snapshot_file, f, indent=2)

    # Persist snapshots to Postgres so Re-run Checks works after redeploy
    try:
        current_settings = await load_settings()
        model = current_settings.get("model", "unknown")
        await db.save_eval_run(
            model=model,
            cases_passed=len(snapshots),
            cases_total=len(golden_cases),
            checks_passed=0,
            checks_total=0,
            duration_s=None,
            snapshot_at=generated_at,
            results=None,
            snapshots=snapshots,
        )
    except Exception:
        pass

    return {
        "phase": "snapshot",
        "total": len(golden_cases),
        "captured": len(snapshots),
        "errors": errors,
        "snapshots": snapshots,
    }


@router.post("/eval/check")
async def run_check():
    """Run deterministic checks against saved snapshots.

    No LLM calls. Pure string matching. Instant.
    """
    with open(GOLDEN_PATH) as f:
        golden_cases = yaml.safe_load(f)

    # Try local file first, fall back to DB snapshots
    if os.path.exists(SNAPSHOT_PATH):
        with open(SNAPSHOT_PATH) as f:
            snapshot_file = json.load(f)
    else:
        db_snapshots = await db.get_latest_snapshots()
        if not db_snapshots:
            return {"error": "No snapshots found. Run snapshot generation first."}
        snapshot_file = {"generatedAt": "from database", "snapshots": db_snapshots}

    snapshot_map = {s["id"]: s for s in snapshot_file.get("snapshots", [])}

    results = []
    total_checks = 0
    passed_checks = 0

    for golden in golden_cases:
        snapshot = snapshot_map.get(golden["id"])
        if not snapshot:
            results.append(
                {
                    "id": golden["id"],
                    "query": golden["query"],
                    "category": golden["category"],
                    "passed": False,
                    "checks": [{"type": "missing", "passed": False, "detail": "No snapshot found"}],
                }
            )
            continue

        checks = []

        # Tool selection
        if golden.get("expected_tools"):
            for expected_tool in golden["expected_tools"]:
                found = expected_tool in snapshot.get("toolCalls", [])
                checks.append(
                    {
                        "type": "tool_selection",
                        "passed": found,
                        "detail": (
                            f"Tool '{expected_tool}' was correctly called"
                            if found
                            else f"Expected tool '{expected_tool}' not called. Got: [{', '.join(snapshot.get('toolCalls', []))}]"
                        ),
                    }
                )

        # Content validation
        if golden.get("must_contain"):
            response_lower = snapshot.get("response", "").lower()
            for required in golden["must_contain"]:
                found = required.lower() in response_lower
                checks.append(
                    {
                        "type": "content_validation",
                        "passed": found,
                        "detail": (
                            f"Response contains '{required}'"
                            if found
                            else f"Response missing required content '{required}'"
                        ),
                    }
                )

        # Negative validation
        if golden.get("must_not_contain"):
            response_lower = snapshot.get("response", "").lower()
            for forbidden in golden["must_not_contain"]:
                found = forbidden.lower() in response_lower
                checks.append(
                    {
                        "type": "negative_validation",
                        "passed": not found,
                        "detail": (
                            f"Response correctly excludes '{forbidden}'"
                            if not found
                            else f"Response contains forbidden content '{forbidden}'"
                        ),
                    }
                )

        # Verification
        if golden.get("expect_verified") is not None:
            match = snapshot.get("verified") == golden["expect_verified"]
            checks.append(
                {
                    "type": "verification",
                    "passed": match,
                    "detail": (
                        f"Verification status matches ({golden['expect_verified']})"
                        if match
                        else f"Expected verified={golden['expect_verified']}, got {snapshot.get('verified')}"
                    ),
                }
            )

        for c in checks:
            total_checks += 1
            if c["passed"]:
                passed_checks += 1

        results.append(
            {
                "id": golden["id"],
                "query": golden["query"],
                "category": golden["category"],
                "passed": all(c["passed"] for c in checks),
                "checks": checks,
            }
        )

    passed_cases = sum(1 for r in results if r["passed"])

    # Persist eval run to Postgres
    try:
        current_settings = await load_settings()
        model = current_settings.get("model", "unknown")
        await db.save_eval_run(
            model=model,
            cases_passed=passed_cases,
            cases_total=len(results),
            checks_passed=passed_checks,
            checks_total=total_checks,
            duration_s=None,
            snapshot_at=snapshot_file.get("generatedAt"),
            results=results,
        )
    except Exception:
        pass  # Don't fail the eval if persistence fails

    return {
        "phase": "check",
        "generatedAt": snapshot_file.get("generatedAt"),
        "cases": {"passed": passed_cases, "total": len(results)},
        "checks": {"passed": passed_checks, "total": total_checks},
        "results": results,
    }


@router.get("/eval/history")
async def get_eval_history():
    """Return past eval runs from Postgres."""
    runs = await db.list_eval_runs(limit=20)
    return {"runs": runs}


# ---- Conversation cleanup ----


@router.get("/conversations/stats")
async def conversation_stats():
    """Diagnostic: show conversation counts and duplicates."""
    from services.db import _get_pool

    pool = _get_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM agent_conversations")
        dupes = await conn.fetch("""
            SELECT title, COUNT(*) as cnt
            FROM agent_conversations
            GROUP BY title
            HAVING COUNT(*) > 1
            ORDER BY cnt DESC LIMIT 20
        """)
        msg_count = await conn.fetchval("SELECT COUNT(*) FROM agent_messages")
    return {
        "totalConversations": total,
        "totalMessages": msg_count,
        "duplicateTitles": [{"title": d["title"][:80], "count": d["cnt"]} for d in dupes],
    }


@router.post("/conversations/deduplicate")
async def deduplicate_conversations():
    """Remove duplicate conversations, keeping only the most recent one per title."""
    from services.db import _get_pool

    pool = _get_pool()
    async with pool.acquire() as conn:
        before = await conn.fetchval("SELECT COUNT(*) FROM agent_conversations")
        # Delete all but the most recent conversation for each duplicate title
        await conn.execute("""
            DELETE FROM agent_conversations
            WHERE id IN (
                SELECT id FROM (
                    SELECT id,
                           ROW_NUMBER() OVER (PARTITION BY title ORDER BY updated_at DESC) as rn
                    FROM agent_conversations
                ) sub WHERE sub.rn > 1
            )
        """)
        after = await conn.fetchval("SELECT COUNT(*) FROM agent_conversations")
    return {
        "before": before,
        "after": after,
        "removed": before - after,
    }


# ---- Analytics / Cost Analysis endpoint ----


@router.get("/analytics")
async def get_analytics():
    """Fetch usage data from Langfuse and compute cost analysis.

    Returns development/testing costs (actual) and production cost projections.
    """
    if not LANGFUSE_PUBLIC_KEY or not LANGFUSE_SECRET_KEY:
        return {"error": "Langfuse keys not configured"}

    langfuse_api = f"{LANGFUSE_HOST}/api/public"
    auth = (LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY)

    # Fetch all generations from Langfuse (paginate if needed)
    all_generations = []
    page = 1
    while True:
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.get(
                f"{langfuse_api}/observations",
                params={"limit": 100, "page": page, "type": "GENERATION"},
                auth=auth,
            )
        if res.status_code != 200:
            return {"error": f"Langfuse API returned {res.status_code}"}
        data = res.json()
        generations = data.get("data", [])
        all_generations.extend(generations)
        meta = data.get("meta", {})
        if page >= meta.get("totalPages", 1):
            break
        page += 1

    # Aggregate by model and source
    by_model = {}
    total_input_tokens = 0
    total_output_tokens = 0
    total_cost = 0.0
    total_calls = len(all_generations)

    for g in all_generations:
        model = g.get("model") or "unknown"
        source = g.get("name") or "unknown"
        inp = g.get("promptTokens") or 0
        out = g.get("completionTokens") or 0
        cost = g.get("calculatedTotalCost") or 0

        total_input_tokens += inp
        total_output_tokens += out
        total_cost += cost

        if model not in by_model:
            by_model[model] = {"calls": 0, "inputTokens": 0, "outputTokens": 0, "cost": 0.0, "source": source}
        by_model[model]["calls"] += 1
        by_model[model]["inputTokens"] += inp
        by_model[model]["outputTokens"] += out
        by_model[model]["cost"] += cost

    # Compute per-query averages for projection
    avg_input_per_call = total_input_tokens / total_calls if total_calls > 0 else 800
    avg_output_per_call = total_output_tokens / total_calls if total_calls > 0 else 200
    avg_cost_per_call = total_cost / total_calls if total_calls > 0 else 0.0002
    avg_tools_per_call = 1.2  # typical: ~1.2 tool calls per query

    # Production cost projections
    # Assumptions: queries per user per day
    queries_per_user_per_day = 3
    days_per_month = 30

    projections = {}
    for user_count in [100, 1000, 10000, 100000]:
        monthly_queries = user_count * queries_per_user_per_day * days_per_month
        monthly_cost = monthly_queries * avg_cost_per_call
        monthly_tokens = monthly_queries * (avg_input_per_call + avg_output_per_call)
        projections[str(user_count)] = {
            "users": user_count,
            "monthlyQueries": monthly_queries,
            "monthlyTokens": int(monthly_tokens),
            "monthlyCost": round(monthly_cost, 2),
        }

    # Langfuse (observability tool) cost estimate
    # Langfuse cloud: free tier up to 50k observations/month
    langfuse_cost = 0.0  # free tier for dev/testing

    return {
        "devCosts": {
            "totalCalls": total_calls,
            "totalInputTokens": total_input_tokens,
            "totalOutputTokens": total_output_tokens,
            "totalTokens": total_input_tokens + total_output_tokens,
            "totalCost": round(total_cost, 6),
            "byModel": {
                model: {
                    "calls": info["calls"],
                    "inputTokens": info["inputTokens"],
                    "outputTokens": info["outputTokens"],
                    "cost": round(info["cost"], 6),
                    "source": info["source"],
                }
                for model, info in by_model.items()
            },
            "observabilityCost": langfuse_cost,
        },
        "projections": projections,
        "assumptions": {
            "queriesPerUserPerDay": queries_per_user_per_day,
            "avgInputTokensPerQuery": int(avg_input_per_call),
            "avgOutputTokensPerQuery": int(avg_output_per_call),
            "avgCostPerQuery": round(avg_cost_per_call, 6),
            "avgToolCallsPerQuery": avg_tools_per_call,
            "model": list(by_model.keys())[0] if by_model else "gpt-4o-mini",
        },
    }


# ---- Traces / Analytics endpoint ----


@router.get("/traces")
async def get_traces():
    """Fetch tracing analytics from Langfuse: daily metrics, recent traces, latency data."""
    if not LANGFUSE_PUBLIC_KEY or not LANGFUSE_SECRET_KEY:
        return {"error": "Langfuse keys not configured"}

    langfuse_api = f"{LANGFUSE_HOST}/api/public"
    auth = (LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY)

    async with httpx.AsyncClient(timeout=15.0) as client:
        # Fetch daily metrics, recent traces, and generations (for latency) in parallel
        daily_res, traces_res, gen_res = await _fetch_parallel(client, langfuse_api, auth)

    # Parse daily metrics
    daily_data = []
    if daily_res and daily_res.status_code == 200:
        daily_data = daily_res.json().get("data", [])

    # Parse recent traces
    recent_traces = []
    if traces_res and traces_res.status_code == 200:
        for t in traces_res.json().get("data", [])[:20]:
            recent_traces.append(
                {
                    "id": t.get("id", "")[:12],
                    "name": t.get("name", ""),
                    "timestamp": t.get("timestamp", ""),
                    "latency": t.get("latency"),
                    "cost": t.get("totalCost"),
                    "observations": len(t.get("observations", [])),
                }
            )

    # Parse generations for latency distribution and error rates
    latencies = []
    error_count = 0
    success_count = 0
    total_ttft = []
    if gen_res and gen_res.status_code == 200:
        for g in gen_res.json().get("data", []):
            lat = g.get("latency")
            if lat is not None:
                latencies.append(round(lat, 2))
            ttft = g.get("timeToFirstToken")
            if ttft is not None:
                total_ttft.append(round(ttft, 2))
            level = g.get("level", "DEFAULT")
            if level == "ERROR":
                error_count += 1
            else:
                success_count += 1

    # Latency distribution buckets
    buckets = {"<1s": 0, "1-3s": 0, "3-5s": 0, "5-10s": 0, "10-20s": 0, ">20s": 0}
    for lat in latencies:
        if lat < 1:
            buckets["<1s"] += 1
        elif lat < 3:
            buckets["1-3s"] += 1
        elif lat < 5:
            buckets["3-5s"] += 1
        elif lat < 10:
            buckets["5-10s"] += 1
        elif lat < 20:
            buckets["10-20s"] += 1
        else:
            buckets[">20s"] += 1

    # Latency stats
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    p50 = sorted(latencies)[len(latencies) // 2] if latencies else 0
    p95_idx = int(len(latencies) * 0.95)
    p95 = sorted(latencies)[p95_idx] if latencies and p95_idx < len(latencies) else 0
    avg_ttft = sum(total_ttft) / len(total_ttft) if total_ttft else 0

    # Daily chart data
    daily_chart = []
    for d in sorted(daily_data, key=lambda x: x.get("date", "")):
        daily_chart.append(
            {
                "date": d.get("date", ""),
                "traces": d.get("countTraces", 0),
                "observations": d.get("countObservations", 0),
                "cost": d.get("totalCost", 0),
                "models": d.get("usage", []),
            }
        )

    return {
        "dailyChart": daily_chart,
        "recentTraces": recent_traces,
        "latencyDistribution": buckets,
        "latencyStats": {
            "avg": round(avg_latency, 2),
            "p50": round(p50, 2),
            "p95": round(p95, 2),
            "avgTtft": round(avg_ttft, 2),
            "count": len(latencies),
        },
        "successRate": {
            "success": success_count,
            "errors": error_count,
            "total": success_count + error_count,
            "rate": round(success_count / (success_count + error_count) * 100, 1)
            if (success_count + error_count) > 0
            else 0,
        },
    }


async def _fetch_parallel(client, langfuse_api, auth):
    """Fetch daily metrics, traces, and generations in parallel."""
    import asyncio

    async def _get(url, params):
        try:
            return await client.get(url, params=params, auth=auth)
        except Exception:
            return None

    results = await asyncio.gather(
        _get(f"{langfuse_api}/metrics/daily", {"limit": 50}),
        _get(f"{langfuse_api}/traces", {"limit": 20}),
        _get(f"{langfuse_api}/observations", {"limit": 100, "type": "GENERATION"}),
    )
    return results


# ---- Eval run detail ----


@router.get("/eval/history/{run_id}")
async def get_eval_run_detail(run_id: str):
    """Return full results for a single eval run."""
    run = await db.get_eval_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Eval run not found")
    return run


# ---- Portfolio import ----


class ImportRequest(BaseModel):
    orders: list[dict]
    fileName: str
    fileHash: str
    accountId: str


class RollbackRequest(BaseModel):
    pass


@router.post("/portfolio/check-duplicate")
async def check_duplicate(request: Request):
    user_id = get_user_id(request)
    body = await request.json()
    file_hash = body.get("fileHash", "")
    existing = await db.get_import_by_hash(user_id, file_hash)
    return {"duplicate": existing is not None, "existing": existing}


@router.post("/portfolio/import")
async def import_portfolio(request: Request, body: ImportRequest):
    """Import orders into Ghostfolio and track the batch."""
    user_id = get_user_id(request)
    token = get_raw_token(request)

    # Check for duplicates
    existing = await db.get_import_by_hash(user_id, body.fileHash)
    if existing:
        raise HTTPException(status_code=409, detail="This file has already been imported")

    # Save import record
    preview = body.orders[:10]  # Store first 10 for preview
    import_id = await db.save_import(user_id, body.fileName, body.fileHash, preview)
    await db.update_import_status(import_id, "importing")

    # Create orders via Ghostfolio API
    client = GhostfolioClient(GHOSTFOLIO_URL, token)
    created_ids = []
    errors = []

    for order in body.orders:
        try:
            order_data = {
                "accountId": body.accountId,
                "currency": order.get("currency", "USD"),
                "date": order["date"],
                "fee": order.get("fee", 0),
                "quantity": order["quantity"],
                "symbol": order["symbol"],
                "type": order["type"],
                "unitPrice": order["unitPrice"],
            }
            if order.get("dataSource"):
                order_data["dataSource"] = order["dataSource"]
            result = await client.create_order(order_data)
            created_ids.append(result.get("id", ""))
        except Exception as e:
            errors.append({"symbol": order.get("symbol", "?"), "error": str(e)})

    # Update import status
    status = "completed" if not errors else ("failed" if not created_ids else "completed")
    await db.update_import_status(
        import_id,
        status,
        orders_created=len(created_ids),
        order_ids=created_ids,
        error_message=json.dumps(errors) if errors else None,
    )

    return {
        "importId": import_id,
        "created": len(created_ids),
        "failed": len(errors),
        "errors": errors,
        "status": status,
    }


@router.post("/portfolio/rollback/{import_id}")
async def rollback_import(import_id: str, request: Request):
    """Delete all orders from an import batch."""
    user_id = get_user_id(request)
    token = get_raw_token(request)

    imp = await db.get_import(import_id, user_id)
    if not imp:
        raise HTTPException(status_code=404, detail="Import not found")
    if imp["status"] == "rolled_back":
        raise HTTPException(status_code=400, detail="Already rolled back")

    order_ids = imp.get("orderIds") or []
    client = GhostfolioClient(GHOSTFOLIO_URL, token)
    deleted = 0
    errors = []

    for oid in order_ids:
        try:
            await client.delete_order(oid)
            deleted += 1
        except Exception as e:
            errors.append({"orderId": oid, "error": str(e)})

    await db.update_import_status(import_id, "rolled_back")

    return {"deleted": deleted, "errors": errors, "status": "rolled_back"}


@router.get("/portfolio/history")
async def get_import_history(request: Request):
    user_id = get_user_id(request)
    imports = await db.list_imports(user_id)
    return {"imports": imports}
