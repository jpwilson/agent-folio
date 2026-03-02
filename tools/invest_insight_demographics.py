from services.invest_insight_client import InvestInsightClient

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "invest_insight_demographics",
        "description": "Get demographic data for a US zip code including population, median income, median age, and housing units.",
        "parameters": {
            "type": "object",
            "properties": {
                "zip_code": {
                    "type": "string",
                    "description": "US 5-digit zip code",
                }
            },
            "required": ["zip_code"],
        },
    },
}


async def execute(client, args: dict) -> dict:
    try:
        ii_client = InvestInsightClient()
        result = await ii_client.get_demographics(args["zip_code"])
        return {"success": True, **result}
    except Exception as e:
        return {"success": False, "error": str(e)}
