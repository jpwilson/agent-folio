"""Tests for the Rotki provider — mock httpx responses and verify data normalization."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from services.providers.rotki_client import RotkiClient


@pytest.fixture()
def mock_httpx_client():
    """Create a mock httpx.AsyncClient with session cookies."""
    client = AsyncMock()
    return client


@pytest.fixture()
def rotki_client(mock_httpx_client):
    """Create a RotkiClient with a mocked httpx client."""
    return RotkiClient("http://localhost:4242", mock_httpx_client)


def _mock_response(data, status_code=200):
    """Helper to create a mock httpx response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    return resp


class TestRotkiPortfolioDetails:
    async def test_normalizes_balances_to_holdings(self, rotki_client, mock_httpx_client):
        mock_httpx_client.get.return_value = _mock_response({
            "result": {
                "BTC": {"amount": "1.5", "usd_value": "75000.00"},
                "ETH": {"amount": "10.0", "usd_value": "25000.00"},
            }
        })
        result = await rotki_client.get_portfolio_details()

        assert len(result["holdings"]) == 2
        btc = next(h for h in result["holdings"] if h["symbol"] == "BTC")
        assert btc["quantity"] == 1.5
        assert btc["valueInBaseCurrency"] == 75000.0
        assert btc["assetClass"] == "CRYPTO"
        assert result["summary"]["netWorth"] == 100000.0

    async def test_computes_allocations(self, rotki_client, mock_httpx_client):
        mock_httpx_client.get.return_value = _mock_response({
            "result": {
                "BTC": {"amount": "1.0", "usd_value": "75000.00"},
                "ETH": {"amount": "10.0", "usd_value": "25000.00"},
            }
        })
        result = await rotki_client.get_portfolio_details()
        btc = next(h for h in result["holdings"] if h["symbol"] == "BTC")
        eth = next(h for h in result["holdings"] if h["symbol"] == "ETH")
        assert btc["allocationInPercentage"] == pytest.approx(0.75, abs=0.01)
        assert eth["allocationInPercentage"] == pytest.approx(0.25, abs=0.01)

    async def test_handles_empty_balances(self, rotki_client, mock_httpx_client):
        mock_httpx_client.get.return_value = _mock_response({"result": {}})
        result = await rotki_client.get_portfolio_details()
        assert result["holdings"] == []

    async def test_handles_api_error(self, rotki_client, mock_httpx_client):
        mock_httpx_client.get.side_effect = Exception("Connection refused")
        result = await rotki_client.get_portfolio_details()
        assert result["holdings"] == []


class TestRotkiOrders:
    async def test_maps_events_to_activities(self, rotki_client, mock_httpx_client):
        mock_httpx_client.get.return_value = _mock_response({
            "result": {
                "entries": [
                    {
                        "identifier": "tx1",
                        "event_type": "trade",
                        "asset": "BTC",
                        "amount": "0.5",
                        "rate": "50000",
                        "fee": "10",
                        "timestamp": "2025-01-15T10:00:00Z",
                    },
                    {
                        "identifier": "tx2",
                        "event_type": "sell",
                        "asset": "ETH",
                        "amount": "2.0",
                        "rate": "3000",
                        "fee": "5",
                        "timestamp": "2025-02-01T12:00:00Z",
                    },
                ]
            }
        })
        result = await rotki_client.get_orders()
        assert len(result["activities"]) == 2
        assert result["activities"][0]["type"] == "BUY"
        assert result["activities"][1]["type"] == "SELL"
        assert result["activities"][0]["symbol"] == "BTC"
        assert result["activities"][0]["quantity"] == 0.5

    async def test_handles_empty_events(self, rotki_client, mock_httpx_client):
        mock_httpx_client.get.return_value = _mock_response({"result": {"entries": []}})
        result = await rotki_client.get_orders()
        assert result["activities"] == []


class TestRotkiPerformance:
    async def test_normalizes_netvalue(self, rotki_client, mock_httpx_client):
        mock_httpx_client.get.return_value = _mock_response({
            "result": {
                "times": [1700000000, 1700100000, 1700200000],
                "data": [50000, 55000, 60000],
            }
        })
        result = await rotki_client.get_portfolio_performance()
        assert len(result["chart"]) == 3
        assert result["performance"]["currentNetWorth"] == 60000
        assert result["performance"]["totalInvestment"] == 50000
        assert result["performance"]["netPerformance"] == 10000

    async def test_handles_error(self, rotki_client, mock_httpx_client):
        mock_httpx_client.get.side_effect = Exception("fail")
        result = await rotki_client.get_portfolio_performance()
        assert result["chart"] == []


class TestRotkiDividendsAndStubs:
    async def test_dividends_returns_empty(self, rotki_client):
        result = await rotki_client.get_dividends()
        assert result == {"dividends": []}

    async def test_report_returns_empty(self, rotki_client):
        result = await rotki_client.get_portfolio_report()
        assert result == {}

    async def test_investments_returns_empty(self, rotki_client):
        result = await rotki_client.get_portfolio_investments()
        assert result == {"investments": []}


class TestRotkiAccounts:
    async def test_lists_exchanges(self, rotki_client, mock_httpx_client):
        # First call: exchanges, second call: blockchains
        mock_httpx_client.get.side_effect = [
            _mock_response({"result": [{"name": "Binance", "location": "binance"}]}),
            _mock_response({"result": ["ETH", "BTC"]}),
        ]
        result = await rotki_client.get_accounts()
        assert len(result["accounts"]) == 3  # 1 exchange + 2 blockchains
        assert result["accounts"][0]["name"] == "Binance"


class TestRotkiProviderName:
    def test_provider_name(self, rotki_client):
        assert rotki_client.provider_name == "rotki"


class TestRotkiSymbolLookup:
    async def test_lookup_returns_items(self, rotki_client, mock_httpx_client):
        mock_httpx_client.post.return_value = _mock_response({
            "result": [
                {"identifier": "BTC", "name": "Bitcoin"},
                {"identifier": "ETH", "name": "Ethereum"},
            ]
        })
        result = await rotki_client.lookup_symbol("BTC")
        assert len(result["items"]) == 2
        assert result["items"][0]["symbol"] == "BTC"
        assert result["items"][0]["name"] == "Bitcoin"

    async def test_lookup_handles_error(self, rotki_client, mock_httpx_client):
        mock_httpx_client.post.side_effect = Exception("fail")
        mock_httpx_client.get.side_effect = Exception("also fail")
        result = await rotki_client.lookup_symbol("XYZ")
        assert result["items"] == []


class TestRotkiSymbolDetails:
    async def test_gets_price(self, rotki_client, mock_httpx_client):
        mock_httpx_client.post.return_value = _mock_response({
            "result": {"assets": {"BTC": {"USD": 65000}}}
        })
        result = await rotki_client.get_symbol_details("rotki", "BTC")
        assert result["marketPrice"] == 65000
        assert result["symbol"] == "BTC"

    async def test_handles_error(self, rotki_client, mock_httpx_client):
        mock_httpx_client.post.side_effect = Exception("fail")
        result = await rotki_client.get_symbol_details("rotki", "BTC")
        assert result["marketPrice"] == 0
