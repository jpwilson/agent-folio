from services.providers.invest_insight_provider import InvestInsightProvider

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


def _get_http_client(client):
    """Get the httpx client from InvestInsightProvider (direct or via Combined)."""
    if isinstance(client, InvestInsightProvider):
        return client._client
    for p in getattr(client, "_providers", []):
        if isinstance(p, InvestInsightProvider):
            return p._client
    return None


async def execute(client, args: dict) -> dict:
    try:
        http_client = _get_http_client(client)

        if not http_client:
            try:
                from services.invest_insight_client import InvestInsightClient

                ii_client = InvestInsightClient()
                result = await ii_client.get_demographics(args["zip_code"])
            except Exception:
                return {
                    "success": False,
                    "error": "No Invest Insight connection configured. Add one in Agent Admin > Backends.",
                }
        else:
            resp = await http_client.get(f"/api/v1/demographics/{args['zip_code']}")
            resp.raise_for_status()
            result = resp.json()

        return {"success": True, **result}
    except Exception as e:
        return {"success": False, "error": str(e)}
