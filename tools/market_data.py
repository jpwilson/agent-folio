import contextlib

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

        # Try to get price details for the best match
        best = items[0]
        ds = best.get("dataSource")
        sym = best.get("symbol")
        details = None
        if ds and sym:
            with contextlib.suppress(Exception):
                details = await client.get_symbol_details(ds, sym)

        price_info = {}
        if details:
            price_info = {
                "marketPrice": details.get("marketPrice"),
                "currency": details.get("currency"),
                "name": details.get("name") or best.get("name"),
                "exchange": details.get("exchange"),
                "sector": details.get("sectors", [{}])[0].get("name") if details.get("sectors") else None,
                "country": details.get("countries", [{}])[0].get("name") if details.get("countries") else None,
            }

        return {
            "success": True,
            "quote": {
                "symbol": best.get("symbol"),
                "name": price_info.get("name") or best.get("name"),
                "dataSource": ds,
                "marketPrice": price_info.get("marketPrice"),
                "currency": price_info.get("currency") or best.get("currency"),
                "exchange": price_info.get("exchange"),
                "sector": price_info.get("sector"),
                "country": price_info.get("country"),
                "assetClass": best.get("assetClass"),
                "assetSubClass": best.get("assetSubClass"),
            },
            "otherResults": [
                {
                    "symbol": item.get("symbol"),
                    "name": item.get("name"),
                    "dataSource": item.get("dataSource"),
                }
                for item in items[1:5]
            ],
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to look up symbol: {str(e)}"}
