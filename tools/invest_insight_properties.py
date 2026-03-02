from services.invest_insight_client import InvestInsightClient

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "invest_insight_properties",
        "description": "Manage user's property/investment holdings. Actions: list, add, update, delete.",
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


async def execute(client, args: dict) -> dict:
    try:
        ii_client = InvestInsightClient()
        action = args["action"]
        if action == "list":
            return {"success": True, **(await ii_client.list_properties())}
        elif action == "add":
            result = await ii_client.add_property(args.get("data", {}))
            return {"success": True, "property": result}
        elif action == "update":
            pid = args.get("property_id")
            if not pid:
                return {"success": False, "error": "property_id required for update"}
            result = await ii_client.update_property(pid, args.get("data", {}))
            return {"success": True, "property": result}
        elif action == "delete":
            pid = args.get("property_id")
            if not pid:
                return {"success": False, "error": "property_id required for delete"}
            return await ii_client.delete_property(pid)
        else:
            return {"success": False, "error": f"Unknown action: {action}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
