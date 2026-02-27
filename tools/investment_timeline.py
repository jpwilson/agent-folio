from services.ghostfolio_client import GhostfolioClient

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "investment_timeline",
        "description": "Get the investment history timeline showing how much was invested each month or year, plus savings streaks. Use this when the user asks about their investment history over time, savings rate, investment streak, how much they invested per month, or their investment pattern.",
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
                    "description": "Group by 'month' or 'year'",
                    "enum": ["month", "year"],
                    "default": "month",
                },
            },
            "required": [],
        },
    },
}


async def execute(client: GhostfolioClient, args: dict) -> dict:
    try:
        date_range = args.get("range", "max")
        group_by = args.get("groupBy", "month")

        data = await client.get_portfolio_investments(date_range, group_by)
        investments = data.get("investments", [])
        streaks = data.get("streaks", {})

        total_invested = sum(i.get("investment", 0) for i in investments)

        return {
            "success": True,
            "range": date_range,
            "groupBy": group_by,
            "investments": investments,
            "totalInvested": round(total_invested, 2),
            "periodCount": len(investments),
            "streaks": {
                "currentStreak": streaks.get("currentStreak", 0),
                "longestStreak": streaks.get("longestStreak", 0),
            },
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to fetch investment timeline: {str(e)}"}
