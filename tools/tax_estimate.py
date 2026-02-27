from services.ghostfolio_client import GhostfolioClient

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "tax_estimate",
        "description": "Estimate unrealized capital gains and losses for tax planning purposes. Shows cost basis vs current value for each holding and total estimated tax liability. Use this when the user asks about taxes, capital gains, tax-loss harvesting, cost basis, or unrealized gains/losses.",
        "parameters": {
            "type": "object",
            "properties": {
                "taxRate": {
                    "type": "number",
                    "description": "Capital gains tax rate as a percentage (default 15% for long-term US federal)",
                    "default": 15,
                }
            },
            "required": [],
        },
    },
}


async def execute(client: GhostfolioClient, args: dict) -> dict:
    tax_rate = args.get("taxRate", 15)
    try:
        details = await client.get_portfolio_details()
        orders_data = await client.get_orders()

        holdings_raw = details.get("holdings", {})
        holdings = list(holdings_raw.values()) if isinstance(holdings_raw, dict) else holdings_raw

        activities = orders_data.get("activities", [])

        # Build cost basis map from activities
        cost_basis_map: dict[str, dict] = {}
        for activity in activities:
            symbol_profile = activity.get("SymbolProfile", {}) or {}
            symbol = symbol_profile.get("symbol")
            if not symbol:
                continue
            if symbol not in cost_basis_map:
                cost_basis_map[symbol] = {"totalCost": 0, "totalQty": 0, "fees": 0}

            if activity.get("type") == "BUY":
                qty = activity.get("quantity", 0)
                price = activity.get("unitPrice", 0)
                cost_basis_map[symbol]["totalCost"] += qty * price
                cost_basis_map[symbol]["totalQty"] += qty
                cost_basis_map[symbol]["fees"] += activity.get("fee", 0) or 0
            elif activity.get("type") == "SELL":
                qty = activity.get("quantity", 0)
                price = activity.get("unitPrice", 0)
                cost_basis_map[symbol]["totalCost"] -= qty * price
                cost_basis_map[symbol]["totalQty"] -= qty

        position_tax = []
        for h in holdings:
            symbol = h.get("symbol")
            basis = cost_basis_map.get(symbol, {"totalCost": 0, "totalQty": 0, "fees": 0})
            current_value = h.get("valueInBaseCurrency", 0) or 0
            cost_basis = basis["totalCost"] + basis["fees"]
            unrealized_gain = current_value - cost_basis
            estimated_tax = unrealized_gain * (tax_rate / 100) if unrealized_gain > 0 else 0

            position_tax.append(
                {
                    "symbol": symbol,
                    "name": h.get("name"),
                    "quantity": h.get("quantity"),
                    "costBasis": f"{cost_basis:.2f}",
                    "currentValue": f"{current_value:.2f}",
                    "unrealizedGain": f"{unrealized_gain:.2f}",
                    "gainPercentage": (f"{(unrealized_gain / cost_basis) * 100:.2f}" if cost_basis > 0 else "N/A"),
                    "estimatedTax": f"{estimated_tax:.2f}",
                }
            )

        total_cost = sum(float(p["costBasis"]) for p in position_tax)
        total_value = sum(float(p["currentValue"]) for p in position_tax)
        total_gain = sum(float(p["unrealizedGain"]) for p in position_tax)
        total_tax = sum(float(p["estimatedTax"]) for p in position_tax)

        return {
            "success": True,
            "taxEstimate": {
                "taxRateUsed": tax_rate,
                "positions": position_tax,
                "totals": {
                    "costBasis": f"{total_cost:.2f}",
                    "currentValue": f"{total_value:.2f}",
                    "totalUnrealizedGain": f"{total_gain:.2f}",
                    "totalEstimatedTax": f"{total_tax:.2f}",
                    "gainPercentage": (f"{(total_gain / total_cost) * 100:.2f}" if total_cost > 0 else "N/A"),
                },
                "disclaimer": "This is a rough estimate for informational purposes only. Actual tax liability depends on holding period, tax brackets, state taxes, and other factors. Consult a tax professional.",
            },
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to estimate taxes: {str(e)}"}
