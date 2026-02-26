from services.ghostfolio_client import GhostfolioClient

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "market_data",
        "description": "Look up current market data for a stock, ETF, or cryptocurrency by searching for its name or symbol. Use this when the user asks about current prices, what a stock is trading at, or wants to look up a specific asset.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": 'The stock symbol or company name to search for (e.g. "AAPL", "Apple", "VTI")',
                }
            },
            "required": ["query"],
        },
    },
}


async def execute(client: GhostfolioClient, args: dict) -> dict:
    query = args.get("query", "")
    try:
        result = await client.lookup_symbol(query)
        items = result.get("items", [])

        if not items:
            return {"success": False, "error": f'No results found for "{query}"'}

        return {
            "success": True,
            "results": [
                {
                    "symbol": item.get("symbol"),
                    "name": item.get("name"),
                    "currency": item.get("currency"),
                    "dataSource": item.get("dataSource"),
                    "assetClass": item.get("assetClass"),
                    "assetSubClass": item.get("assetSubClass"),
                }
                for item in items[:5]
            ],
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to look up symbol: {str(e)}"}
