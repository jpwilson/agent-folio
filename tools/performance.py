from services.ghostfolio_client import GhostfolioClient

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "portfolio_performance",
        "description": "Get portfolio performance over a time period including returns, annualized performance, and net worth. Use this when the user asks about performance, returns, how their portfolio did over a period (YTD, this year, last year, 1 year, 5 years, all time), or their net worth trend.",
        "parameters": {
            "type": "object",
            "properties": {
                "range": {
                    "type": "string",
                    "description": "Time period: '1d' (today), 'wtd' (week), 'mtd' (month), 'ytd' (year to date), '1y' (1 year), '5y' (5 years), 'max' (all time)",
                    "enum": ["1d", "wtd", "mtd", "ytd", "1y", "5y", "max"],
                    "default": "ytd",
                },
            },
            "required": [],
        },
    },
}


async def execute(client: GhostfolioClient, args: dict) -> dict:
    try:
        date_range = args.get("range", "ytd")
        data = await client.get_portfolio_performance(date_range)

        perf = data.get("performance", {})
        chart = data.get("chart", [])

        # Summarize chart — first and last points
        chart_summary = {}
        if chart:
            chart_summary = {
                "startDate": chart[0].get("date") if chart else None,
                "endDate": chart[-1].get("date") if chart else None,
                "startValue": chart[0].get("totalInvestment") if chart else None,
                "endValue": chart[-1].get("value") if chart else None,
                "dataPoints": len(chart),
            }

        return {
            "success": True,
            "range": date_range,
            "performance": {
                "currentNetWorth": perf.get("currentNetWorth"),
                "totalInvestment": perf.get("totalInvestment"),
                "netPerformance": perf.get("netPerformance"),
                "netPerformancePercentage": perf.get("netPerformancePercentage"),
                "netPerformanceWithCurrencyEffect": perf.get("netPerformanceWithCurrencyEffect"),
                "netPerformancePercentageWithCurrencyEffect": perf.get("netPerformancePercentageWithCurrencyEffect"),
                "annualizedPerformancePercent": perf.get("annualizedPerformancePercent"),
                "currentValueInBaseCurrency": perf.get("currentValueInBaseCurrency"),
                "totalInvestmentValueWithCurrencyEffect": perf.get("totalInvestmentValueWithCurrencyEffect"),
            },
            "chartSummary": chart_summary,
            "firstOrderDate": data.get("firstOrderDate"),
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to fetch performance: {str(e)}"}
