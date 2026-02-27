from services.ghostfolio_client import GhostfolioClient

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "stock_history",
        "description": "Get historical price data for a stock, ETF, or cryptocurrency. Use this when the user asks about price trends, historical performance, or wants to see how a stock's price has changed over time (e.g. 'show me Apple's price over the last year').",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": 'The stock symbol or company name to look up (e.g. "AAPL", "Apple", "VTI")',
                },
                "period": {
                    "type": "string",
                    "enum": ["1m", "3m", "6m", "1y", "3y", "5y", "max"],
                    "description": "Time period for historical data. Defaults to 1y.",
                },
            },
            "required": ["query"],
        },
    },
}

PERIOD_DAYS = {
    "1m": 30,
    "3m": 90,
    "6m": 180,
    "1y": 365,
    "3y": 1095,
    "5y": 1825,
    "max": 10000,
}


async def execute(client: GhostfolioClient, args: dict) -> dict:
    query = args.get("query", "")
    period = args.get("period", "1y")
    days = PERIOD_DAYS.get(period, 365)

    try:
        # First look up the symbol
        result = await client.lookup_symbol(query)
        items = result.get("items", [])

        if not items:
            return {"success": False, "error": f'No results found for "{query}"'}

        best = items[0]
        ds = best.get("dataSource")
        sym = best.get("symbol")

        if not ds or not sym:
            return {"success": False, "error": "Could not determine data source for symbol"}

        # Fetch historical data
        details = await client.get_symbol_history(ds, sym, days)

        historical = details.get("historicalData", [])
        name = details.get("name") or best.get("name")
        currency = details.get("currency") or best.get("currency")
        current_price = details.get("marketPrice")

        if not historical:
            return {
                "success": True,
                "symbol": sym,
                "name": name,
                "currency": currency,
                "currentPrice": current_price,
                "historicalData": [],
                "note": "No historical data available for this period.",
            }

        # Sample data points to keep response manageable
        # For short periods show more granularity, for long periods sample monthly
        if len(historical) > 60:
            # Sample roughly 60 data points spread evenly
            step = max(1, len(historical) // 60)
            sampled = historical[::step]
            # Always include the most recent data point
            if historical[-1] not in sampled:
                sampled.append(historical[-1])
        else:
            sampled = historical

        data_points = [
            {
                "date": point.get("date", "")[:10],
                "price": point.get("marketPrice") or point.get("value"),
            }
            for point in sampled
            if (point.get("marketPrice") or point.get("value")) is not None
        ]

        # Calculate summary stats
        prices = [p["price"] for p in data_points if p["price"] is not None]
        first_price = prices[0] if prices else None
        last_price = prices[-1] if prices else None

        summary = {}
        if first_price and last_price:
            change = last_price - first_price
            change_pct = (change / first_price) * 100
            summary = {
                "startPrice": round(first_price, 2),
                "endPrice": round(last_price, 2),
                "change": round(change, 2),
                "changePercent": round(change_pct, 2),
                "high": round(max(prices), 2),
                "low": round(min(prices), 2),
            }

        return {
            "success": True,
            "symbol": sym,
            "name": name,
            "currency": currency,
            "currentPrice": current_price,
            "period": period,
            "dataPoints": len(data_points),
            "summary": summary,
            "historicalData": data_points,
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to fetch historical data: {str(e)}"}
