"""Unit tests for tools/ — validate TOOL_DEFINITION dicts across all 10 tool modules."""

import importlib
from unittest.mock import AsyncMock

import pytest

# All 10 tool modules by their import path
TOOL_MODULE_PATHS = [
    "tools.portfolio_summary",
    "tools.market_data",
    "tools.transaction_history",
    "tools.risk_assessment",
    "tools.tax_estimate",
    "tools.performance",
    "tools.dividend_history",
    "tools.portfolio_report",
    "tools.investment_timeline",
    "tools.account_overview",
]


def _load_all_tool_modules():
    """Import and return all tool modules."""
    modules = []
    for path in TOOL_MODULE_PATHS:
        modules.append(importlib.import_module(path))
    return modules


ALL_TOOL_MODULES = _load_all_tool_modules()


# ============================================================
# All tools have valid TOOL_DEFINITION dicts
# ============================================================


class TestToolDefinitionsExist:
    """Every tool module should export a TOOL_DEFINITION dict."""

    @pytest.mark.parametrize("module", ALL_TOOL_MODULES, ids=TOOL_MODULE_PATHS)
    def test_has_tool_definition(self, module):
        assert hasattr(module, "TOOL_DEFINITION"), f"{module.__name__} is missing TOOL_DEFINITION"
        assert isinstance(module.TOOL_DEFINITION, dict)

    @pytest.mark.parametrize("module", ALL_TOOL_MODULES, ids=TOOL_MODULE_PATHS)
    def test_has_execute_function(self, module):
        assert hasattr(module, "execute"), f"{module.__name__} is missing execute() function"
        assert callable(module.execute)


# ============================================================
# Each DEFINITION has name, description, parameters
# ============================================================


class TestToolDefinitionStructure:
    """Each TOOL_DEFINITION should have the correct top-level and nested keys."""

    @pytest.mark.parametrize("module", ALL_TOOL_MODULES, ids=TOOL_MODULE_PATHS)
    def test_has_type_function(self, module):
        defn = module.TOOL_DEFINITION
        assert defn.get("type") == "function", f"{module.__name__}: TOOL_DEFINITION.type should be 'function'"

    @pytest.mark.parametrize("module", ALL_TOOL_MODULES, ids=TOOL_MODULE_PATHS)
    def test_has_function_key(self, module):
        defn = module.TOOL_DEFINITION
        assert "function" in defn, f"{module.__name__}: TOOL_DEFINITION must have 'function' key"

    @pytest.mark.parametrize("module", ALL_TOOL_MODULES, ids=TOOL_MODULE_PATHS)
    def test_function_has_name(self, module):
        func = module.TOOL_DEFINITION["function"]
        assert "name" in func, f"{module.__name__}: function must have 'name'"
        assert isinstance(func["name"], str)
        assert len(func["name"]) > 0

    @pytest.mark.parametrize("module", ALL_TOOL_MODULES, ids=TOOL_MODULE_PATHS)
    def test_function_has_description(self, module):
        func = module.TOOL_DEFINITION["function"]
        assert "description" in func, f"{module.__name__}: function must have 'description'"
        assert isinstance(func["description"], str)
        assert len(func["description"]) > 10, "Description should be meaningful"

    @pytest.mark.parametrize("module", ALL_TOOL_MODULES, ids=TOOL_MODULE_PATHS)
    def test_function_has_parameters(self, module):
        func = module.TOOL_DEFINITION["function"]
        assert "parameters" in func, f"{module.__name__}: function must have 'parameters'"
        assert isinstance(func["parameters"], dict)


# ============================================================
# Parameter schemas are valid JSON schema
# ============================================================


class TestToolParameterSchemas:
    """Parameter schemas should follow JSON Schema conventions."""

    @pytest.mark.parametrize("module", ALL_TOOL_MODULES, ids=TOOL_MODULE_PATHS)
    def test_parameters_has_type_object(self, module):
        params = module.TOOL_DEFINITION["function"]["parameters"]
        assert params.get("type") == "object", f"{module.__name__}: parameters.type should be 'object'"

    @pytest.mark.parametrize("module", ALL_TOOL_MODULES, ids=TOOL_MODULE_PATHS)
    def test_parameters_has_properties(self, module):
        params = module.TOOL_DEFINITION["function"]["parameters"]
        assert "properties" in params, f"{module.__name__}: parameters must have 'properties'"
        assert isinstance(params["properties"], dict)

    @pytest.mark.parametrize("module", ALL_TOOL_MODULES, ids=TOOL_MODULE_PATHS)
    def test_required_is_list(self, module):
        params = module.TOOL_DEFINITION["function"]["parameters"]
        if "required" in params:
            assert isinstance(params["required"], list), f"{module.__name__}: 'required' should be a list"

    @pytest.mark.parametrize("module", ALL_TOOL_MODULES, ids=TOOL_MODULE_PATHS)
    def test_property_values_are_dicts(self, module):
        props = module.TOOL_DEFINITION["function"]["parameters"]["properties"]
        for prop_name, prop_schema in props.items():
            assert isinstance(prop_schema, dict), f"{module.__name__}: property '{prop_name}' value should be a dict"

    @pytest.mark.parametrize("module", ALL_TOOL_MODULES, ids=TOOL_MODULE_PATHS)
    def test_properties_have_type(self, module):
        props = module.TOOL_DEFINITION["function"]["parameters"]["properties"]
        for prop_name, prop_schema in props.items():
            assert "type" in prop_schema, f"{module.__name__}: property '{prop_name}' should have a 'type' key"

    @pytest.mark.parametrize("module", ALL_TOOL_MODULES, ids=TOOL_MODULE_PATHS)
    def test_properties_have_description(self, module):
        props = module.TOOL_DEFINITION["function"]["parameters"]["properties"]
        for prop_name, prop_schema in props.items():
            assert "description" in prop_schema, (
                f"{module.__name__}: property '{prop_name}' should have a 'description' key"
            )


# ============================================================
# Tool names match the ALL_TOOLS registry
# ============================================================


class TestToolNamesMatchRegistry:
    """The name inside TOOL_DEFINITION should match the ALL_TOOLS key."""

    def test_all_tools_registered(self):
        from tools import ALL_TOOLS

        assert len(ALL_TOOLS) == 11, f"Expected 11 tools, got {len(ALL_TOOLS)}"

    def test_tool_definitions_list(self):
        from tools import TOOL_DEFINITIONS

        assert len(TOOL_DEFINITIONS) == 11, f"Expected 11 definitions, got {len(TOOL_DEFINITIONS)}"

    def test_names_are_unique(self):
        from tools import TOOL_DEFINITIONS

        names = [d["function"]["name"] for d in TOOL_DEFINITIONS]
        assert len(names) == len(set(names)), f"Duplicate tool names: {names}"

    def test_all_names_present_in_registry(self):
        from tools import ALL_TOOLS, TOOL_DEFINITIONS

        definition_names = {d["function"]["name"] for d in TOOL_DEFINITIONS}
        registry_keys = set(ALL_TOOLS.keys())
        # Every definition name should be a registry key
        assert definition_names == registry_keys, (
            f"Mismatch between TOOL_DEFINITIONS names {definition_names} and ALL_TOOLS keys {registry_keys}"
        )


# ============================================================
# Execute function tests (with mocked GhostfolioClient)
# ============================================================


class TestPortfolioSummaryExecute:
    @pytest.mark.asyncio
    async def test_success_dict_holdings(self):
        from tools.portfolio_summary import execute

        mock = AsyncMock()
        mock.get_portfolio_details.return_value = {
            "holdings": {
                "AAPL": {
                    "name": "Apple",
                    "symbol": "AAPL",
                    "currency": "USD",
                    "assetClass": "EQUITY",
                    "assetSubClass": "STOCK",
                    "allocationInPercentage": 0.35,
                    "marketPrice": 175.0,
                    "quantity": 10,
                    "valueInBaseCurrency": 1750.0,
                }
            },
            "summary": {"netWorth": 5000},
        }
        result = await execute(mock, {})
        assert result["success"] is True
        assert len(result["holdings"]) == 1
        assert result["holdings"][0]["allocationInPercentage"] == "35.00"

    @pytest.mark.asyncio
    async def test_success_list_holdings(self):
        from tools.portfolio_summary import execute

        mock = AsyncMock()
        mock.get_portfolio_details.return_value = {
            "holdings": [
                {
                    "name": "MSFT",
                    "symbol": "MSFT",
                    "currency": "USD",
                    "assetClass": "EQUITY",
                    "assetSubClass": "STOCK",
                    "allocationInPercentage": 0.5,
                    "marketPrice": 400.0,
                    "quantity": 5,
                    "valueInBaseCurrency": 2000.0,
                }
            ],
            "summary": {},
        }
        result = await execute(mock, {})
        assert result["success"] is True
        assert result["holdings"][0]["symbol"] == "MSFT"

    @pytest.mark.asyncio
    async def test_failure(self):
        from tools.portfolio_summary import execute

        mock = AsyncMock()
        mock.get_portfolio_details.side_effect = Exception("API error")
        result = await execute(mock, {})
        assert result["success"] is False
        assert "API error" in result["error"]


class TestTransactionHistoryExecute:
    @pytest.mark.asyncio
    async def test_success(self):
        from tools.transaction_history import execute

        mock = AsyncMock()
        mock.get_orders.return_value = {
            "activities": [
                {
                    "date": "2024-01-15",
                    "type": "BUY",
                    "SymbolProfile": {"symbol": "AAPL", "name": "Apple Inc", "currency": "USD"},
                    "quantity": 10,
                    "unitPrice": 150.0,
                    "fee": 0,
                }
            ]
        }
        result = await execute(mock, {})
        assert result["success"] is True
        assert len(result["transactions"]) == 1
        assert result["transactions"][0]["symbol"] == "AAPL"
        assert result["totalCount"] == 1

    @pytest.mark.asyncio
    async def test_with_limit(self):
        from tools.transaction_history import execute

        mock = AsyncMock()
        activities = [
            {
                "date": f"2024-01-{i:02d}",
                "type": "BUY",
                "SymbolProfile": {"symbol": f"S{i}", "name": f"Stock {i}", "currency": "USD"},
                "quantity": 1,
                "unitPrice": 100.0,
                "fee": 0,
            }
            for i in range(1, 11)
        ]
        mock.get_orders.return_value = {"activities": activities}
        result = await execute(mock, {"limit": 3})
        assert result["success"] is True
        assert len(result["transactions"]) == 3
        assert result["totalCount"] == 10

    @pytest.mark.asyncio
    async def test_failure(self):
        from tools.transaction_history import execute

        mock = AsyncMock()
        mock.get_orders.side_effect = Exception("timeout")
        result = await execute(mock, {})
        assert result["success"] is False
        assert "timeout" in result["error"]
