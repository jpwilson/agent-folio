from services.providers.invest_insight_provider import InvestInsightProvider

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "invest_insight_properties",
        "description": "Manage user's property/investment holdings from Invest Insight. Actions: list, add, update, delete.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "add", "update", "delete"],
                    "description": "The action to perform",
                },
                "property_id": {
                    "type": "string",
                    "description": "Property ID (required for update/delete)",
                },
                "data": {
                    "type": "object",
                    "description": "Property data for add/update. Fields: name, address, business_type, purchase_price, current_value, status",
                },
            },
            "required": ["action"],
        },
    },
}


def _find_invest_insight_provider(client):
    """Extract the InvestInsightProvider from the client (may be Combined or direct)."""
    if isinstance(client, InvestInsightProvider):
        return client
    # CombinedProvider stores providers in _providers
    for p in getattr(client, "_providers", []):
        if isinstance(p, InvestInsightProvider):
            return p
    return None


def _get_standalone_client():
    """Fall back to the standalone InvestInsightClient using env vars."""
    try:
        from services.invest_insight_client import InvestInsightClient

        return InvestInsightClient()
    except Exception:
        return None


async def execute(client, args: dict) -> dict:
    try:
        action = args["action"]

        # Try to get the provider from the backend connection first
        ii_provider = _find_invest_insight_provider(client)

        if action == "list":
            # Use the provider (backend connection) if available
            if ii_provider:
                details = await ii_provider.get_portfolio_details()
                holdings = details.get("holdings", [])
                properties = []
                for h in holdings:
                    extra = h.get("_investInsight", {})
                    properties.append(
                        {
                            "id": extra.get("id"),
                            "name": h.get("name"),
                            "address": extra.get("address"),
                            "business_type": extra.get("businessType"),
                            "purchase_price": extra.get("purchasePrice"),
                            "current_value": h.get("marketPrice"),
                            "status": extra.get("status"),
                        }
                    )
                return {
                    "success": True,
                    "properties": properties,
                    "total": len(properties),
                    "summary": details.get("summary", {}),
                }

            # Fall back to standalone client
            standalone = _get_standalone_client()
            if standalone:
                return {"success": True, **(await standalone.list_properties())}
            return {
                "success": False,
                "error": "No Invest Insight connection configured. Add one in Agent Admin > Backends.",
            }

        # Write operations — need the provider's HTTP client
        if ii_provider:
            if action == "add":
                resp = await ii_provider._client.post("/api/v1/properties", json=args.get("data", {}))
                resp.raise_for_status()
                return {"success": True, "property": resp.json()}
            elif action == "update":
                pid = args.get("property_id")
                if not pid:
                    return {"success": False, "error": "property_id required for update"}
                resp = await ii_provider._client.put(f"/api/v1/properties/{pid}", json=args.get("data", {}))
                resp.raise_for_status()
                return {"success": True, "property": resp.json()}
            elif action == "delete":
                pid = args.get("property_id")
                if not pid:
                    return {"success": False, "error": "property_id required for delete"}
                await ii_provider._client.delete(f"/api/v1/properties/{pid}")
                return {"success": True, "deleted": pid}

        # Fall back to standalone client for write ops
        standalone = _get_standalone_client()
        if not standalone:
            return {
                "success": False,
                "error": "No Invest Insight connection configured. Add one in Agent Admin > Backends.",
            }

        if action == "add":
            result = await standalone.add_property(args.get("data", {}))
            return {"success": True, "property": result}
        elif action == "update":
            pid = args.get("property_id")
            if not pid:
                return {"success": False, "error": "property_id required for update"}
            result = await standalone.update_property(pid, args.get("data", {}))
            return {"success": True, "property": result}
        elif action == "delete":
            pid = args.get("property_id")
            if not pid:
                return {"success": False, "error": "property_id required for delete"}
            return await standalone.delete_property(pid)
        else:
            return {"success": False, "error": f"Unknown action: {action}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
