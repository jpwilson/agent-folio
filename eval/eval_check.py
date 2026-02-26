#!/usr/bin/env python3
"""
Agent Eval - Deterministic Checker

Validates saved snapshots against golden_data.yaml rules.
NO LLM calls. NO network calls. Pure string matching.
Runs in milliseconds. Safe to run on every commit.

Usage:
  python eval/eval_check.py

Exit codes:
  0 = all checks pass
  1 = one or more checks failed
  2 = missing snapshot file (run eval_snapshot.py first)
"""

import json
import os
import sys

import yaml

GOLDEN_PATH = os.path.join(os.path.dirname(__file__), "golden_data.yaml")
SNAPSHOT_PATH = os.path.join(os.path.dirname(__file__), "eval-snapshots.json")


def run_checks(golden: dict, snapshot: dict) -> dict:
    checks = []

    # 1. Tool Selection
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

    # 2. Content Validation
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

    # 3. Negative Validation
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

    # 4. Verification
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

    return {
        "id": golden["id"],
        "query": golden["query"],
        "category": golden["category"],
        "passed": all(c["passed"] for c in checks),
        "checks": checks,
    }


def main():
    if not os.path.exists(SNAPSHOT_PATH):
        print(f"\n  ERROR: No snapshot file found at {SNAPSHOT_PATH}")
        print("  Run the snapshot generator first:")
        print(
            "    AGENT_EVAL_TOKEN=<jwt> python eval/eval_snapshot.py\n"
        )
        sys.exit(2)

    with open(GOLDEN_PATH) as f:
        golden_cases = yaml.safe_load(f)

    with open(SNAPSHOT_PATH) as f:
        snapshot_file = json.load(f)

    snapshot_map = {s["id"]: s for s in snapshot_file.get("snapshots", [])}

    print(f"\n{'=' * 60}")
    print("  Agent-Folio - Deterministic Eval Check")
    print(f"  Golden cases: {len(golden_cases)}")
    print(f"  Snapshots from: {snapshot_file.get('generatedAt')}")
    print(f"{'=' * 60}\n")

    results = []
    total_checks = 0
    passed_checks = 0

    for golden in golden_cases:
        snapshot = snapshot_map.get(golden["id"])
        if not snapshot:
            print(f"  [{golden['id']}] SKIP - no snapshot found")
            continue

        result = run_checks(golden, snapshot)
        results.append(result)

        icon = "\033[32mPASS\033[0m" if result["passed"] else "\033[31mFAIL\033[0m"
        print(f"  [{golden['id']}] {icon} - {golden['query'][:50]}")

        for check in result["checks"]:
            total_checks += 1
            if check["passed"]:
                passed_checks += 1
            check_icon = "\033[32m+\033[0m" if check["passed"] else "\033[31mx\033[0m"
            if not check["passed"]:
                print(f"    {check_icon} [{check['type']}] {check['detail']}")

    # Summary
    passed = sum(1 for r in results if r["passed"])
    failed = sum(1 for r in results if not r["passed"])

    by_category: dict[str, dict] = {}
    for r in results:
        cat = r["category"]
        if cat not in by_category:
            by_category[cat] = {"passed": 0, "total": 0}
        by_category[cat]["total"] += 1
        if r["passed"]:
            by_category[cat]["passed"] += 1

    by_check_type: dict[str, dict] = {}
    for r in results:
        for c in r["checks"]:
            t = c["type"]
            if t not in by_check_type:
                by_check_type[t] = {"passed": 0, "total": 0}
            by_check_type[t]["total"] += 1
            if c["passed"]:
                by_check_type[t]["passed"] += 1

    print(f"\n{'=' * 60}")
    print("  RESULTS")
    print(f"{'=' * 60}")
    pct = f"{(passed / len(results)) * 100:.0f}" if results else "0"
    print(f"  Cases: {passed}/{len(results)} passed ({pct}%)")
    print(f"  Checks: {passed_checks}/{total_checks} passed")
    print("")
    print("  By category:")
    for cat, stats in by_category.items():
        print(f"    {cat}: {stats['passed']}/{stats['total']}")
    print("")
    print("  By check type:")
    for check_type, stats in by_check_type.items():
        icon = "\033[32m+\033[0m" if stats["passed"] == stats["total"] else "\033[31mx\033[0m"
        print(f"    {icon} {check_type}: {stats['passed']}/{stats['total']}")
    print(f"{'=' * 60}\n")

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
