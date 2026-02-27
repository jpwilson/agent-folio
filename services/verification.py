import re

COMMON_WORDS = {
    "I", "A", "AN", "THE", "AND", "OR", "NOT", "IS", "IT", "IN", "ON", "TO",
    "FOR", "OF", "AT", "BY", "AS", "IF", "SO", "DO", "BE", "HAS", "HAD",
    "WAS", "ARE", "BUT", "ALL", "CAN", "HER", "HIS", "ITS", "MAY", "NEW",
    "NOW", "OLD", "SEE", "WAY", "WHO", "DID", "GET", "LET", "SAY", "SHE",
    "TOO", "USE", "USD", "ETF", "USA", "FAQ", "API", "CSV", "N", "S", "P",
    "YOUR", "WITH", "THAT", "THIS", "FROM", "HAVE", "BEEN", "WILL", "EACH",
    "THAN", "THEM", "SOME", "MOST", "VERY", "JUST", "OVER",
}


def verify_response(tool_results: list[dict], response_text: str) -> dict:
    """Domain-specific verification layer.

    Runs deterministic checks against tool results and response text.
    Returns {verified: bool, checks: [{check, passed, detail}], confidence: {...}}.
    """
    checks = []

    # Find tool results by type
    portfolio_result = next(
        (r for r in tool_results if r["tool"] == "portfolio_summary"), None
    )
    tax_result = next(
        (r for r in tool_results if r["tool"] == "tax_estimate"), None
    )
    performance_result = next(
        (r for r in tool_results if r["tool"] == "portfolio_performance"), None
    )
    dividend_result = next(
        (r for r in tool_results if r["tool"] == "dividend_history"), None
    )
    report_result = next(
        (r for r in tool_results if r["tool"] == "portfolio_report"), None
    )
    timeline_result = next(
        (r for r in tool_results if r["tool"] == "investment_timeline"), None
    )
    account_result = next(
        (r for r in tool_results if r["tool"] == "account_overview"), None
    )

    # ---- Original 4 Checks ----

    # Check 1: Allocation percentages sum to ~100%
    if portfolio_result and portfolio_result["result"].get("success"):
        holdings = portfolio_result["result"].get("holdings", [])
        total_alloc = sum(
            float(h.get("allocationInPercentage", 0)) for h in holdings
        )
        valid = 95 < total_alloc < 105
        checks.append(
            {
                "check": "allocation_sum",
                "passed": valid,
                "detail": f"Portfolio allocations sum to {total_alloc:.1f}% (expected ~100%)",
            }
        )

    # Check 2: All holdings have positive market prices
    if portfolio_result and portfolio_result["result"].get("success"):
        holdings = portfolio_result["result"].get("holdings", [])
        invalid = [
            h for h in holdings if not h.get("marketPrice") or h["marketPrice"] <= 0
        ]
        checks.append(
            {
                "check": "valid_market_prices",
                "passed": len(invalid) == 0,
                "detail": (
                    "All holdings have valid market prices"
                    if len(invalid) == 0
                    else f"{len(invalid)} holdings have invalid prices: {', '.join(h.get('symbol','?') for h in invalid)}"
                ),
            }
        )

    # Check 3: Tax estimate data consistency
    if tax_result and tax_result["result"].get("success"):
        totals = tax_result["result"].get("taxEstimate", {}).get("totals", {})
        total_cost = float(totals.get("costBasis", 0))
        total_value = float(totals.get("currentValue", 0))
        checks.append(
            {
                "check": "tax_data_consistency",
                "passed": total_cost > 0 and total_value > 0,
                "detail": f"Cost basis: ${total_cost:.2f}, Current value: ${total_value:.2f}",
            }
        )

    # Check 4: No hallucinated symbols
    if portfolio_result and portfolio_result["result"].get("success"):
        holdings = portfolio_result["result"].get("holdings", [])
        known_symbols = {h.get("symbol") for h in holdings}
        mentioned = re.findall(r"\b[A-Z]{2,5}\b", response_text)
        suspect = [s for s in mentioned if s not in COMMON_WORDS and s not in known_symbols]
        checks.append(
            {
                "check": "no_hallucinated_symbols",
                "passed": len(suspect) == 0,
                "detail": (
                    "All mentioned symbols are in the portfolio or are known terms"
                    if len(suspect) == 0
                    else f"Potentially unknown symbols mentioned: {', '.join(set(suspect))}"
                ),
            }
        )

    # ---- New Check 5: Output Validation ----
    # Validates that the response contains expected data types/formats
    # based on which tools were called

    # 5a: Performance data has numeric values
    if performance_result and performance_result["result"].get("success"):
        perf = performance_result["result"]
        perf_inner = perf.get("performance", {})
        has_data = (
            perf_inner.get("netPerformance") is not None
            or perf_inner.get("currentNetWorth") is not None
            or perf.get("chartSummary", {}).get("dataPoints", 0) > 0
        )
        checks.append(
            {
                "check": "performance_data_valid",
                "passed": has_data,
                "detail": (
                    "Performance data contains valid metrics"
                    if has_data
                    else "Performance data missing metrics"
                ),
            }
        )

    # 5b: Dividend data is non-negative
    if dividend_result and dividend_result["result"].get("success"):
        total = dividend_result["result"].get("totalDividendIncome", 0)
        valid = total >= 0
        checks.append(
            {
                "check": "dividend_data_valid",
                "passed": valid,
                "detail": (
                    f"Dividend income total: ${total:.2f} (non-negative)"
                    if valid
                    else f"Dividend income is negative: ${total:.2f}"
                ),
            }
        )

    # 5c: X-Ray report has categories
    if report_result and report_result["result"].get("success"):
        categories = report_result["result"].get("categories", [])
        has_categories = len(categories) > 0
        checks.append(
            {
                "check": "report_structure_valid",
                "passed": has_categories,
                "detail": (
                    f"X-Ray report has {len(categories)} categories"
                    if has_categories
                    else "X-Ray report is empty (no categories)"
                ),
            }
        )

    # 5d: Account overview has accounts
    if account_result and account_result["result"].get("success"):
        count = account_result["result"].get("totalCount", 0)
        has_accounts = count > 0
        checks.append(
            {
                "check": "account_data_valid",
                "passed": has_accounts,
                "detail": (
                    f"Found {count} account(s)"
                    if has_accounts
                    else "No accounts found"
                ),
            }
        )

    # 5e: Investment timeline has data points
    if timeline_result and timeline_result["result"].get("success"):
        period_count = timeline_result["result"].get("periodCount", 0)
        has_data = period_count > 0
        checks.append(
            {
                "check": "timeline_data_valid",
                "passed": has_data,
                "detail": (
                    f"Investment timeline has {period_count} periods"
                    if has_data
                    else "Investment timeline is empty"
                ),
            }
        )

    # ---- New Check 6: Confidence Scoring ----
    confidence = _compute_confidence(tool_results, response_text, checks)

    verified = len(checks) == 0 or all(c["passed"] for c in checks)

    return {
        "verified": verified,
        "checks": checks,
        "confidence": confidence,
    }


def _compute_confidence(
    tool_results: list[dict], response_text: str, checks: list[dict]
) -> dict:
    """Compute a confidence score (0-100) for the response.

    Factors:
    - Tool success rate: did the tools return data without errors?
    - Check pass rate: how many verification checks passed?
    - Response quality: does the response have substance?
    - Data freshness: are there tool results backing the response?
    """
    scores = {}

    # Factor 1: Tool success rate (0-100)
    if tool_results:
        successful = sum(1 for r in tool_results if r["result"].get("success"))
        scores["toolSuccess"] = int((successful / len(tool_results)) * 100)
    else:
        scores["toolSuccess"] = 50  # No tools called — neutral

    # Factor 2: Check pass rate (0-100)
    if checks:
        passed = sum(1 for c in checks if c["passed"])
        scores["checkPassRate"] = int((passed / len(checks)) * 100)
    else:
        scores["checkPassRate"] = 100  # No checks applicable — assume OK

    # Factor 3: Response quality (0-100)
    resp_len = len(response_text.strip())
    if resp_len < 20:
        scores["responseQuality"] = 20
    elif resp_len < 100:
        scores["responseQuality"] = 60
    else:
        scores["responseQuality"] = 90

    # Check for hedging/uncertainty indicators
    uncertainty = ["i'm not sure", "i cannot", "i don't have", "unavailable", "no data"]
    for phrase in uncertainty:
        if phrase in response_text.lower():
            scores["responseQuality"] = max(scores["responseQuality"] - 20, 10)
            break

    # Factor 4: Data-backed (0-100)
    # Higher if the response is backed by actual tool data
    if tool_results and any(r["result"].get("success") for r in tool_results):
        scores["dataBacked"] = 100
    elif tool_results:
        scores["dataBacked"] = 30  # Tools called but all failed
    else:
        scores["dataBacked"] = 40  # No tools called

    # Weighted average
    weights = {
        "toolSuccess": 0.30,
        "checkPassRate": 0.30,
        "responseQuality": 0.20,
        "dataBacked": 0.20,
    }
    overall = sum(scores[k] * weights[k] for k in weights)

    return {
        "overall": int(overall),
        "factors": scores,
    }
