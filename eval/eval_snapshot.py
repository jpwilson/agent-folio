#!/usr/bin/env python3
"""
Agent Eval - Snapshot Generator

Runs test cases against the LIVE agent API and saves responses as snapshots.
These snapshots are then validated deterministically by eval_check.py.

Usage:
  AGENT_EVAL_TOKEN=<jwt> python eval/eval_snapshot.py

Run this when:
  - You change the system prompt
  - You add/modify tools
  - You change agent logic
  - You want to refresh the baseline
"""

import json
import os
import sys
import time

import httpx
import yaml

API_URL = os.getenv("AGENT_EVAL_URL", "http://localhost:8000/api/v1/agent/chat")
TOKEN = os.getenv("AGENT_EVAL_TOKEN", "")
GOLDEN_PATH = os.path.join(os.path.dirname(__file__), "golden_data.yaml")
SNAPSHOT_PATH = os.path.join(os.path.dirname(__file__), "eval-snapshots.json")


def generate_snapshot(golden_case: dict) -> dict | None:
    start = time.time()
    try:
        res = httpx.post(
            API_URL,
            json={"messages": [{"role": "user", "content": golden_case["query"]}]},
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {TOKEN}",
            },
            timeout=60.0,
        )
        if res.status_code != 200:
            print(f"  FAILED [{golden_case['id']}]: HTTP {res.status_code} - {res.text}")
            return None

        data = res.json()
        duration_ms = int((time.time() - start) * 1000)

        return {
            "id": golden_case["id"],
            "query": golden_case["query"],
            "category": golden_case["category"],
            "response": data.get("message", ""),
            "toolCalls": [tc["tool"] for tc in (data.get("toolCalls") or [])],
            "verified": data.get("verification", {}).get("verified"),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "durationMs": duration_ms,
        }
    except Exception as e:
        print(f"  ERROR [{golden_case['id']}]: {e}")
        return None


def main():
    if not TOKEN:
        print("Set AGENT_EVAL_TOKEN environment variable with a valid JWT token")
        sys.exit(1)

    with open(GOLDEN_PATH) as f:
        golden_cases = yaml.safe_load(f)

    print(f"\n{'=' * 60}")
    print("  Agent-Folio - Snapshot Generator")
    print(f"  Golden cases: {len(golden_cases)}")
    print(f"  API: {API_URL}")
    print(f"{'=' * 60}\n")

    snapshots = []

    for gc in golden_cases:
        print(f"  [{gc['id']}] {gc['query'][:50]}...", end="", flush=True)
        snap = generate_snapshot(gc)
        if snap:
            snapshots.append(snap)
            tools = ", ".join(snap["toolCalls"]) or "none"
            print(f" OK ({snap['durationMs']}ms) [tools: {tools}]")
        else:
            print(" SKIPPED")

    snapshot_file = {
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "apiUrl": API_URL,
        "snapshots": snapshots,
    }

    with open(SNAPSHOT_PATH, "w") as f:
        json.dump(snapshot_file, f, indent=2)

    print(f"\n  Snapshots saved to {SNAPSHOT_PATH}")
    print(f"  {len(snapshots)}/{len(golden_cases)} cases captured\n")


if __name__ == "__main__":
    main()
