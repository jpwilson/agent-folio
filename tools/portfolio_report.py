from services.ghostfolio_client import GhostfolioClient

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "portfolio_report",
        "description": "Get the portfolio X-Ray report with rules-based analysis including diversification, fee levels, currency risk, emergency fund coverage, and other financial health checks. Use this when the user asks about portfolio health, X-Ray, financial rules, diversification score, or wants a comprehensive checkup.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}


async def execute(client: GhostfolioClient, args: dict) -> dict:
    try:
        data = await client.get_portfolio_report()
        x_ray = data.get("xRay", {})

        categories = []
        for cat in x_ray.get("categories", []):
            rules = []
            for rule in cat.get("rules", []):
                if rule.get("isActive"):
                    rules.append({
                        "name": rule.get("name"),
                        "passed": rule.get("value"),
                        "evaluation": rule.get("evaluation"),
                    })
            categories.append({
                "category": cat.get("name"),
                "rules": rules,
            })

        stats = x_ray.get("statistics", {})

        return {
            "success": True,
            "categories": categories,
            "statistics": {
                "rulesActive": stats.get("rulesActiveCount", 0),
                "rulesFulfilled": stats.get("rulesFulfilledCount", 0),
                "passRate": f"{(stats.get('rulesFulfilledCount', 0) / max(stats.get('rulesActiveCount', 1), 1)) * 100:.0f}%",
            },
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to fetch portfolio report: {str(e)}"}
