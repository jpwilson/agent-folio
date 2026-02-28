from services.providers.base import PortfolioProvider

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "portfolio_summary",
        "description": "Get the current portfolio holdings with allocation percentages, asset classes, and performance. Use this when the user asks about their portfolio, holdings, allocation, diversification, or how their investments are doing.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}


async def execute(client: PortfolioProvider, args: dict) -> dict:
    try:
        details = await client.get_portfolio_details()
        holdings_raw = details.get("holdings", {})

        # holdings can be a dict (keyed by symbol) or a list
        holdings_list = list(holdings_raw.values()) if isinstance(holdings_raw, dict) else holdings_raw

        holdings = []
        for h in holdings_list:
            allocation = h.get("allocationInPercentage", 0)
            holdings.append(
                {
                    "name": h.get("name"),
                    "symbol": h.get("symbol"),
                    "currency": h.get("currency"),
                    "assetClass": h.get("assetClass"),
                    "assetSubClass": h.get("assetSubClass"),
                    "allocationInPercentage": f"{allocation * 100:.2f}",
                    "marketPrice": h.get("marketPrice"),
                    "quantity": h.get("quantity"),
                    "valueInBaseCurrency": h.get("valueInBaseCurrency"),
                }
            )

        return {
            "success": True,
            "holdings": holdings,
            "summary": details.get("summary", {}),
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to fetch portfolio: {str(e)}"}
