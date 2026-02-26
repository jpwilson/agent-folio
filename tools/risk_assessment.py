from services.ghostfolio_client import GhostfolioClient

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "risk_assessment",
        "description": "Analyze portfolio risk including concentration risk, sector/asset class diversification, and individual position sizing. Use this when the user asks about risk, diversification, concentration, whether they are too exposed to a sector, or portfolio safety.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}


async def execute(client: GhostfolioClient, args: dict) -> dict:
    try:
        details = await client.get_portfolio_details()
        holdings_raw = details.get("holdings", {})

        if isinstance(holdings_raw, dict):
            holdings = list(holdings_raw.values())
        else:
            holdings = holdings_raw

        total_value = sum(h.get("valueInBaseCurrency", 0) or 0 for h in holdings)

        if total_value == 0:
            return {
                "success": True,
                "risk": {"message": "No portfolio value found to assess risk."},
            }

        positions = sorted(
            [
                {
                    "symbol": h.get("symbol"),
                    "name": h.get("name"),
                    "value": h.get("valueInBaseCurrency", 0) or 0,
                    "percentage": ((h.get("valueInBaseCurrency", 0) or 0) / total_value)
                    * 100,
                }
                for h in holdings
            ],
            key=lambda p: p["percentage"],
            reverse=True,
        )

        top3 = sum(p["percentage"] for p in positions[:3])

        # Asset class breakdown
        asset_class_map: dict[str, float] = {}
        for h in holdings:
            cls = h.get("assetClass") or "UNKNOWN"
            asset_class_map[cls] = asset_class_map.get(cls, 0) + (
                h.get("valueInBaseCurrency", 0) or 0
            )
        asset_class_breakdown = [
            {
                "assetClass": cls,
                "value": val,
                "percentage": (val / total_value) * 100,
            }
            for cls, val in asset_class_map.items()
        ]

        # Sector breakdown
        sector_map: dict[str, float] = {}
        for h in holdings:
            for s in h.get("sectors", []) or []:
                name = s.get("name", "Unknown")
                weight = s.get("weight", 0)
                sector_map[name] = sector_map.get(name, 0) + (
                    (h.get("valueInBaseCurrency", 0) or 0) * weight
                )
        sector_breakdown = sorted(
            [
                {"sector": sec, "value": val, "percentage": (val / total_value) * 100}
                for sec, val in sector_map.items()
            ],
            key=lambda s: s["percentage"],
            reverse=True,
        )[:10]

        # Risk flags
        risks = []
        if len(positions) < 5:
            risks.append(f"Low diversification: only {len(positions)} positions")
        if positions and positions[0]["percentage"] > 30:
            risks.append(
                f"High concentration: {positions[0]['symbol']} is {positions[0]['percentage']:.1f}% of portfolio"
            )
        if top3 > 60:
            risks.append(f"Top 3 positions are {top3:.1f}% of portfolio")
        if len(asset_class_breakdown) == 1:
            risks.append("Single asset class - no asset class diversification")

        return {
            "success": True,
            "risk": {
                "totalValue": total_value,
                "positionCount": len(positions),
                "top3ConcentrationPct": f"{top3:.1f}",
                "positions": [
                    {
                        "symbol": p["symbol"],
                        "name": p["name"],
                        "percentage": f"{p['percentage']:.2f}",
                    }
                    for p in positions
                ],
                "assetClassBreakdown": asset_class_breakdown,
                "sectorBreakdown": sector_breakdown,
                "riskFlags": risks,
                "diversificationScore": (
                    "Good"
                    if len(risks) == 0
                    else "Moderate" if len(risks) <= 2 else "Poor"
                ),
            },
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to assess risk: {str(e)}"}
