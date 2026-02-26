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

    Runs 4 deterministic checks against tool results and response text.
    Returns {verified: bool, checks: [{check, passed, detail}]}.
    """
    checks = []

    # Find portfolio and tax results
    portfolio_result = next(
        (r for r in tool_results if r["tool"] == "portfolio_summary"), None
    )
    tax_result = next(
        (r for r in tool_results if r["tool"] == "tax_estimate"), None
    )

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

    return {
        "verified": len(checks) == 0 or all(c["passed"] for c in checks),
        "checks": checks,
    }
