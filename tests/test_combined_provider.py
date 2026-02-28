"""Tests for the CombinedProvider — merging data from multiple backends."""

from unittest.mock import AsyncMock

import pytest

from services.providers.combined import CombinedProvider


def _make_provider(name: str, **method_results) -> AsyncMock:
    """Create a mock PortfolioProvider with given method results."""
    provider = AsyncMock()
    provider.provider_name = name
    for method_name, result in method_results.items():
        getattr(provider, method_name).return_value = result
    return provider


class TestCombinedProviderName:
    def test_combines_names(self):
        p1 = _make_provider("ghostfolio")
        p2 = _make_provider("rotki")
        combined = CombinedProvider([p1, p2])
        assert combined.provider_name == "Ghostfolio + Rotki"

    def test_single_provider(self):
        p1 = _make_provider("ghostfolio")
        combined = CombinedProvider([p1])
        assert combined.provider_name == "Ghostfolio"


class TestCombinedPortfolioDetails:
    async def test_merges_holdings(self):
        p1 = _make_provider(
            "ghostfolio",
            get_portfolio_details={
                "holdings": [
                    {"symbol": "AAPL", "valueInBaseCurrency": 5000, "allocationInPercentage": 1.0},
                ],
                "summary": {"netWorth": 5000},
            },
        )
        p2 = _make_provider(
            "rotki",
            get_portfolio_details={
                "holdings": [
                    {"symbol": "BTC", "valueInBaseCurrency": 5000, "allocationInPercentage": 1.0},
                ],
                "summary": {"netWorth": 5000},
            },
        )
        combined = CombinedProvider([p1, p2])
        result = await combined.get_portfolio_details()

        assert len(result["holdings"]) == 2
        assert result["summary"]["netWorth"] == 10000

        # Allocations recomputed to 50/50
        aapl = next(h for h in result["holdings"] if h["symbol"] == "AAPL")
        btc = next(h for h in result["holdings"] if h["symbol"] == "BTC")
        assert aapl["allocationInPercentage"] == pytest.approx(0.5)
        assert btc["allocationInPercentage"] == pytest.approx(0.5)

        # Source tags
        assert aapl["_source"] == "ghostfolio"
        assert btc["_source"] == "rotki"

    async def test_handles_one_provider_failure(self):
        p1 = _make_provider(
            "ghostfolio",
            get_portfolio_details={
                "holdings": [{"symbol": "AAPL", "valueInBaseCurrency": 5000}],
                "summary": {},
            },
        )
        p2 = _make_provider("rotki")
        p2.get_portfolio_details.side_effect = Exception("Connection refused")

        combined = CombinedProvider([p1, p2])
        result = await combined.get_portfolio_details()

        # Should still have data from working provider
        assert len(result["holdings"]) == 1
        assert result["holdings"][0]["symbol"] == "AAPL"


class TestCombinedOrders:
    async def test_merges_and_sorts_activities(self):
        p1 = _make_provider(
            "ghostfolio",
            get_orders={
                "activities": [
                    {"id": "1", "date": "2025-01-15", "symbol": "AAPL", "type": "BUY"},
                    {"id": "2", "date": "2025-03-01", "symbol": "MSFT", "type": "BUY"},
                ]
            },
        )
        p2 = _make_provider(
            "rotki",
            get_orders={
                "activities": [
                    {"id": "3", "date": "2025-02-15", "symbol": "BTC", "type": "BUY"},
                ]
            },
        )
        combined = CombinedProvider([p1, p2])
        result = await combined.get_orders()

        assert len(result["activities"]) == 3
        # Sorted descending by date
        assert result["activities"][0]["date"] == "2025-03-01"
        assert result["activities"][1]["date"] == "2025-02-15"
        assert result["activities"][2]["date"] == "2025-01-15"
        # Source tags
        assert result["activities"][2]["_source"] == "ghostfolio"
        assert result["activities"][1]["_source"] == "rotki"


class TestCombinedPerformance:
    async def test_aggregates_performance(self):
        p1 = _make_provider(
            "ghostfolio",
            get_portfolio_performance={
                "chart": [{"date": "2025-01-01", "value": 5000}],
                "performance": {
                    "currentNetWorth": 6000,
                    "totalInvestment": 5000,
                    "netPerformance": 1000,
                },
            },
        )
        p2 = _make_provider(
            "rotki",
            get_portfolio_performance={
                "chart": [],
                "performance": {
                    "currentNetWorth": 4000,
                    "totalInvestment": 3000,
                    "netPerformance": 1000,
                },
            },
        )
        combined = CombinedProvider([p1, p2])
        result = await combined.get_portfolio_performance()

        assert result["performance"]["currentNetWorth"] == 10000
        assert result["performance"]["totalInvestment"] == 8000
        assert result["performance"]["netPerformance"] == 2000
        assert result["performance"]["netPerformancePercentage"] == pytest.approx(0.25)


class TestCombinedDividends:
    async def test_merges_dividends(self):
        p1 = _make_provider("ghostfolio", get_dividends={"dividends": [{"date": "2025-01", "amount": 50}]})
        p2 = _make_provider("rotki", get_dividends={"dividends": []})

        combined = CombinedProvider([p1, p2])
        result = await combined.get_dividends()
        assert len(result["dividends"]) == 1


class TestCombinedAccounts:
    async def test_merges_accounts(self):
        p1 = _make_provider(
            "ghostfolio",
            get_accounts={"accounts": [{"id": "a1", "name": "Brokerage"}]},
        )
        p2 = _make_provider(
            "rotki",
            get_accounts={"accounts": [{"id": "a2", "name": "Binance"}]},
        )
        combined = CombinedProvider([p1, p2])
        result = await combined.get_accounts()
        assert len(result["accounts"]) == 2
        assert result["accounts"][0]["_source"] == "ghostfolio"
        assert result["accounts"][1]["_source"] == "rotki"


class TestCombinedSymbolLookup:
    async def test_returns_first_nonempty(self):
        p1 = _make_provider("ghostfolio", lookup_symbol={"items": []})
        p2 = _make_provider("rotki", lookup_symbol={"items": [{"symbol": "BTC", "name": "Bitcoin"}]})

        combined = CombinedProvider([p1, p2])
        result = await combined.lookup_symbol("BTC")
        assert len(result["items"]) == 1
        assert result["items"][0]["symbol"] == "BTC"

    async def test_returns_empty_when_all_fail(self):
        p1 = _make_provider("ghostfolio")
        p1.lookup_symbol.side_effect = Exception("fail")
        p2 = _make_provider("rotki")
        p2.lookup_symbol.side_effect = Exception("fail")

        combined = CombinedProvider([p1, p2])
        result = await combined.lookup_symbol("XYZ")
        assert result["items"] == []


class TestCombinedWriteOps:
    async def test_create_order_delegates_to_first_supporting(self):
        p1 = _make_provider("ghostfolio", create_order={"id": "new-order"})
        p2 = _make_provider("rotki")
        p2.create_order.side_effect = NotImplementedError

        combined = CombinedProvider([p1, p2])
        result = await combined.create_order({"symbol": "AAPL", "type": "BUY"})
        assert result["id"] == "new-order"

    async def test_create_order_raises_when_none_support(self):
        p1 = _make_provider("rotki")
        p1.create_order.side_effect = NotImplementedError

        combined = CombinedProvider([p1])
        with pytest.raises(NotImplementedError):
            await combined.create_order({})
