from services.providers.base import PortfolioProvider

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "account_overview",
        "description": "Get all investment accounts with balances, platform info, and totals. Use this when the user asks about their accounts, cash balance, which brokerages they use, or total account values.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}


async def execute(client: PortfolioProvider, args: dict) -> dict:
    try:
        data = await client.get_accounts()
        accounts = data.get("accounts", [])

        formatted = []
        for a in accounts:
            entry = {
                    "name": a.get("name"),
                    "currency": a.get("currency"),
                    "balance": a.get("balance"),
                    "valueInBaseCurrency": a.get("valueInBaseCurrency"),
                    "platform": a.get("Platform", {}).get("name") if a.get("Platform") else a.get("platformId"),
                    "isExcluded": a.get("isExcluded", False),
                }
            if a.get("_source"):
                entry["source"] = a["_source"]
            formatted.append(entry)

        return {
            "success": True,
            "accounts": formatted,
            "totalCount": len(formatted),
            "totalBalanceInBaseCurrency": data.get("totalBalanceInBaseCurrency"),
            "totalValueInBaseCurrency": data.get("totalValueInBaseCurrency"),
            "activitiesCount": data.get("activitiesCount"),
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to fetch accounts: {str(e)}"}
