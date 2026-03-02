from services.invest_insight_client import InvestInsightClient

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "invest_insight_search",
        "description": "Run a market saturation analysis for a business type in a specific location. Returns saturation score (0-100), opportunity rating, demographics, and business counts.",
        "parameters": {
            "type": "object",
            "properties": {
                "business_type": {
                    "type": "string",
                    "description": "Business type key (e.g. 'coffee_shop', 'restaurant', 'gym', 'laundromat')",
                },
                "location": {
                    "type": "string",
                    "description": "Location to analyze (city name, address, or zip code)",
                },
                "radius_km": {
                    "type": "number",
                    "description": "Search radius in kilometers (default 5)",
                    "default": 5.0,
                },
            },
            "required": ["business_type", "location"],
        },
    },
}


async def execute(client, args: dict) -> dict:
    try:
        ii_client = InvestInsightClient()
        result = await ii_client.run_analysis(
            business_type=args["business_type"],
            location=args["location"],
            radius_km=args.get("radius_km", 5.0),
        )
        return {
            "success": True,
            "business_type": result.get("business_type"),
            "location": result.get("location_name"),
            "saturation_score": result.get("saturation_score"),
            "opportunity_rating": result.get("opportunity_rating"),
            "population": result.get("population"),
            "median_income": result.get("median_income"),
            "osm_business_count": result.get("osm_business_count"),
            "zip_count": result.get("zip_count"),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
