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
import time

import yaml

EVAL_DIR = os.path.dirname(__file__)
GOLDEN_PATH = os.path.join(EVAL_DIR, "golden_data.yaml")
SNAPSHOT_PATH = os.path.join(EVAL_DIR, "eval-snapshots.json")

# Use DATA_DIR env var for persistent history, fall back to eval/history for local dev
_data_dir = os.environ.get("DATA_DIR", "")
HISTORY_DIR = os.path.join(_data_dir, "eval_history") if _data_dir else os.path.join(EVAL_DIR, "history")


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


def save_history(run_result: dict):
    """Save eval run to history for regression detection."""
    os.makedirs(HISTORY_DIR, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
    path = os.path.join(HISTORY_DIR, f"eval_{timestamp}.json")
    with open(path, "w") as f:
        json.dump(run_result, f, indent=2)
    return path


def check_regression(current: dict) -> list[str]:
    """Compare current run against the most recent historical run.

    Returns a list of regression warnings (empty = no regressions).
    """
    if not os.path.exists(HISTORY_DIR):
        return []

    history_files = sorted(
        [f for f in os.listdir(HISTORY_DIR) if f.startswith("eval_") and f.endswith(".json")]
    )
    if not history_files:
        return []

    # Load most recent
    with open(os.path.join(HISTORY_DIR, history_files[-1])) as f:
        previous = json.load(f)

    warnings = []

    # Compare pass rates
    prev_rate = previous.get("passRate", 0)
    curr_rate = current.get("passRate", 0)
    if curr_rate < prev_rate:
        warnings.append(
            f"Overall pass rate dropped: {prev_rate:.0f}% -> {curr_rate:.0f}%"
        )

    # Compare per-case results
    prev_cases = {r["id"]: r["passed"] for r in previous.get("results", [])}
    for result in current.get("results", []):
        case_id = result["id"]
        if case_id in prev_cases and prev_cases[case_id] and not result["passed"]:
            warnings.append(
                f"Regression: {case_id} was passing, now failing"
            )

    # Compare by category
    prev_cats = previous.get("byCategory", {})
    curr_cats = current.get("byCategory", {})
    for cat, stats in curr_cats.items():
        if cat in prev_cats:
            prev_pct = prev_cats[cat]["passed"] / max(prev_cats[cat]["total"], 1) * 100
            curr_pct = stats["passed"] / max(stats["total"], 1) * 100
            if curr_pct < prev_pct:
                warnings.append(
                    f"Category '{cat}' regressed: {prev_pct:.0f}% -> {curr_pct:.0f}%"
                )

    return warnings


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

    pass_rate = (passed / len(results)) * 100 if results else 0

    print(f"\n{'=' * 60}")
    print("  RESULTS")
    print(f"{'=' * 60}")
    print(f"  Cases: {passed}/{len(results)} passed ({pass_rate:.0f}%)")
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

    # Build run result for history
    run_result = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "snapshotGeneratedAt": snapshot_file.get("generatedAt"),
        "totalCases": len(results),
        "passed": passed,
        "failed": failed,
        "passRate": pass_rate,
        "totalChecks": total_checks,
        "passedChecks": passed_checks,
        "byCategory": by_category,
        "byCheckType": by_check_type,
        "results": [{"id": r["id"], "passed": r["passed"]} for r in results],
    }

    # Regression detection
    regressions = check_regression(run_result)
    if regressions:
        print(f"\n  \033[33mREGRESSIONS DETECTED:\033[0m")
        for warn in regressions:
            print(f"    \033[33m! {warn}\033[0m")

    # Save to history
    history_path = save_history(run_result)
    print(f"\n  History saved: {os.path.basename(history_path)}")
    print(f"{'=' * 60}\n")

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
