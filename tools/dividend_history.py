from services.providers.base import PortfolioProvider

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "dividend_history",
        "description": "Get dividend income history grouped by month or year. Use this when the user asks about dividends, dividend income, passive income, or dividend yield.",
        "parameters": {
            "type": "object",
            "properties": {
                "range": {
                    "type": "string",
                    "description": "Time period: 'ytd', '1y', '5y', 'max'",
                    "enum": ["ytd", "1y", "5y", "max"],
                    "default": "max",
                },
                "groupBy": {
                    "type": "string",
                    "description": "Group results by 'month' or 'year'",
                    "enum": ["month", "year"],
                    "default": "month",
                },
            },
            "required": [],
        },
    },
}


async def execute(client: PortfolioProvider, args: dict) -> dict:
    try:
        date_range = args.get("range", "max")
        group_by = args.get("groupBy", "month")

        data = await client.get_dividends(date_range, group_by)
        dividends = data.get("dividends", [])

        total_dividends = sum(d.get("investment", 0) for d in dividends)

        return {
            "success": True,
            "range": date_range,
            "groupBy": group_by,
            "dividends": dividends,
            "totalDividendIncome": round(total_dividends, 2),
            "periodCount": len(dividends),
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to fetch dividends: {str(e)}"}
