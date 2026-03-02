from services.providers.base import PortfolioProvider

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "transaction_history",
        "description": "Get the user's recent transaction history (buys, sells, dividends, fees). Use this when the user asks about their past trades, activity, transaction patterns, or what they have bought or sold recently.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of transactions to return",
                    "default": 20,
                }
            },
            "required": [],
        },
    },
}


async def execute(client: PortfolioProvider, args: dict) -> dict:
    limit = args.get("limit", 20)
    try:
        data = await client.get_orders()
        activities = data.get("activities", [])

        # Sort by date descending and limit
        activities.sort(key=lambda a: a.get("date", ""), reverse=True)
        recent = activities[:limit]

        transactions = []
        for a in recent:
            symbol_profile = a.get("SymbolProfile", {}) or {}
            entry = {
                    "date": a.get("date"),
                    "type": a.get("type"),
                    "symbol": symbol_profile.get("symbol") or a.get("symbol"),
                    "name": symbol_profile.get("name"),
                    "quantity": a.get("quantity"),
                    "unitPrice": a.get("unitPrice"),
                    "currency": symbol_profile.get("currency") or a.get("currency"),
                    "fee": a.get("fee"),
                }
            if a.get("_source"):
                entry["source"] = a["_source"]
            transactions.append(entry)

        return {
            "success": True,
            "transactions": transactions,
            "totalCount": len(activities),
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to fetch transactions: {str(e)}"}
