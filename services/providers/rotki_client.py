"""Rotki portfolio backend provider.

Rotki is an open-source crypto portfolio tracker. Key differences from Ghostfolio:
- Session-based auth (login with username/password, cookies maintained)
- Many endpoints return a task_id that must be polled for completion
- Crypto-native data model (events rather than orders, balances rather than holdings)
"""

import asyncio
import logging

import httpx

from services.providers.base import PortfolioProvider

logger = logging.getLogger(__name__)

# Polling config for async task results
TASK_POLL_INTERVAL = 0.5  # seconds
TASK_POLL_TIMEOUT = 30.0  # max seconds to wait


class RotkiClient(PortfolioProvider):
    """Async HTTP client for Rotki's REST API."""

    def __init__(self, base_url: str, client: httpx.AsyncClient):
        self._base_url = base_url.rstrip("/")
        self._client = client  # Authenticated httpx client with session cookies

    @property
    def provider_name(self) -> str:
        return "rotki"

    @classmethod
    async def create(cls, base_url: str, credentials: dict) -> "RotkiClient":
        """Authenticate and return a ready-to-use RotkiClient."""
        base_url = base_url.rstrip("/")
        username = credentials.get("username", "")
        password = credentials.get("password", "")
        if not username or not password:
            raise ValueError("Rotki connection requires username and password")

        client = httpx.AsyncClient(timeout=30.0, base_url=base_url)
        res = await client.patch(
            "/api/1/users",
            json={"name": username, "password": password, "action": "login"},
        )
        if res.status_code == 401:
            await client.aclose()
            raise ValueError("Rotki authentication failed: invalid credentials")
        res.raise_for_status()
        return cls(base_url, client)

    async def _poll_task(self, task_id: int) -> dict:
        """Poll a Rotki async task until it completes."""
        elapsed = 0.0
        while elapsed < TASK_POLL_TIMEOUT:
            res = await self._client.get(f"/api/1/tasks/{task_id}")
            res.raise_for_status()
            data = res.json()
            result = data.get("result", {})
            if result.get("status") == "completed":
                return result.get("outcome", result)
            if result.get("status") == "failed":
                raise RuntimeError(f"Rotki task {task_id} failed: {result}")
            await asyncio.sleep(TASK_POLL_INTERVAL)
            elapsed += TASK_POLL_INTERVAL
        raise TimeoutError(f"Rotki task {task_id} did not complete within {TASK_POLL_TIMEOUT}s")

    async def _get_or_poll(self, path: str, **kwargs) -> dict:
        """GET an endpoint. If it returns a task_id, poll for the result."""
        res = await self._client.get(path, **kwargs)
        res.raise_for_status()
        data = res.json()
        result = data.get("result")

        # Some endpoints return immediately, others return a task_id
        if isinstance(result, dict) and "task_id" in result:
            return await self._poll_task(result["task_id"])
        return result if result is not None else data

    # ------------------------------------------------------------------
    # Portfolio reads
    # ------------------------------------------------------------------

    async def get_portfolio_details(self) -> dict:
        """GET /api/1/balances — normalize to holdings array."""
        try:
            result = await self._get_or_poll("/api/1/balances")
        except Exception as e:
            logger.warning("Rotki balances failed: %s", e)
            return {"holdings": [], "summary": {}}

        holdings = []
        assets = result if isinstance(result, dict) else {}
        total_value = 0.0

        for asset_id, balance_info in assets.items():
            if isinstance(balance_info, dict):
                amount = float(balance_info.get("amount", 0))
                usd_value = float(balance_info.get("usd_value", 0))
            else:
                continue
            total_value += usd_value
            holdings.append({
                "name": asset_id,
                "symbol": asset_id,
                "currency": "USD",
                "assetClass": "CRYPTO",
                "assetSubClass": None,
                "allocationInPercentage": 0,  # Computed below
                "marketPrice": usd_value / amount if amount > 0 else 0,
                "quantity": amount,
                "valueInBaseCurrency": usd_value,
            })

        # Compute allocations
        for h in holdings:
            if total_value > 0:
                h["allocationInPercentage"] = h["valueInBaseCurrency"] / total_value

        return {
            "holdings": holdings,
            "summary": {"netWorth": total_value},
        }

    async def get_orders(self) -> dict:
        """GET /api/1/history/events — map to BUY/SELL activities."""
        try:
            result = await self._get_or_poll("/api/1/history/events")
        except Exception as e:
            logger.warning("Rotki events failed: %s", e)
            return {"activities": []}

        events = result.get("entries", []) if isinstance(result, dict) else result if isinstance(result, list) else []

        # Map Rotki event types to standard types
        type_map = {
            "trade": "BUY",
            "buy": "BUY",
            "sell": "SELL",
            "deposit": "BUY",
            "withdrawal": "SELL",
            "staking": "DIVIDEND",
            "receive": "BUY",
            "spend": "SELL",
        }

        activities = []
        for event in events:
            if isinstance(event, dict):
                event_type = str(event.get("event_type", event.get("type", ""))).lower()
                activities.append({
                    "id": str(event.get("identifier", event.get("tx_hash", ""))),
                    "date": event.get("timestamp", ""),
                    "symbol": event.get("asset", event.get("base_asset", "")),
                    "type": type_map.get(event_type, "BUY"),
                    "quantity": float(event.get("amount", event.get("base_amount", 0))),
                    "unitPrice": float(event.get("rate", event.get("price", 0))),
                    "fee": float(event.get("fee", 0)),
                    "currency": "USD",
                    "dataSource": None,
                })

        return {"activities": activities}

    async def get_portfolio_performance(self, date_range: str = "max") -> dict:
        """GET /api/1/statistics/netvalue — net worth over time."""
        try:
            result = await self._get_or_poll("/api/1/statistics/netvalue")
        except Exception:
            return {"chart": [], "performance": {}}

        times = result.get("times", []) if isinstance(result, dict) else []
        values = result.get("data", []) if isinstance(result, dict) else []

        chart = []
        for i, t in enumerate(times):
            if i < len(values):
                chart.append({"date": str(t), "value": float(values[i])})

        current_value = float(values[-1]) if values else 0
        first_value = float(values[0]) if values else 0
        net_perf = current_value - first_value

        return {
            "chart": chart,
            "performance": {
                "currentNetWorth": current_value,
                "totalInvestment": first_value,
                "netPerformance": net_perf,
                "netPerformancePercentage": net_perf / first_value if first_value > 0 else 0,
            },
        }

    async def get_dividends(self, date_range: str = "max", group_by: str | None = None) -> dict:
        """Crypto doesn't have a traditional dividends concept — return empty."""
        return {"dividends": []}

    async def get_portfolio_report(self) -> dict:
        """No X-Ray equivalent in Rotki — return empty."""
        return {}

    async def get_portfolio_investments(self, date_range: str = "max", group_by: str | None = None) -> dict:
        """No direct equivalent — return empty."""
        return {"investments": []}

    async def get_accounts(self) -> dict:
        """GET /api/1/exchanges + blockchain accounts."""
        accounts = []
        try:
            # Centralized exchanges
            res = await self._client.get("/api/1/exchanges")
            res.raise_for_status()
            data = res.json()
            exchanges = data.get("result", []) if isinstance(data, dict) else []
            for ex in exchanges:
                if isinstance(ex, dict):
                    accounts.append({
                        "id": ex.get("name", ""),
                        "name": ex.get("name", ""),
                        "balance": 0,
                        "currency": "USD",
                        "platformId": ex.get("location", ""),
                    })
                elif isinstance(ex, str):
                    accounts.append({
                        "id": ex,
                        "name": ex,
                        "balance": 0,
                        "currency": "USD",
                        "platformId": ex,
                    })
        except Exception as e:
            logger.warning("Rotki exchanges failed: %s", e)

        try:
            # Blockchain accounts
            res = await self._client.get("/api/1/blockchains/supported")
            res.raise_for_status()
            data = res.json()
            chains = data.get("result", []) if isinstance(data, dict) else []
            for chain in chains:
                chain_name = chain if isinstance(chain, str) else chain.get("id", "") if isinstance(chain, dict) else ""
                if chain_name:
                    accounts.append({
                        "id": f"blockchain-{chain_name}",
                        "name": f"{chain_name} Blockchain",
                        "balance": 0,
                        "currency": "USD",
                        "platformId": chain_name,
                    })
        except Exception:
            pass

        return {"accounts": accounts}

    # ------------------------------------------------------------------
    # Market data
    # ------------------------------------------------------------------

    async def lookup_symbol(self, query: str) -> dict:
        """GET /api/1/assets — search by identifier."""
        try:
            res = await self._client.post("/api/1/assets/search", json={"value": query, "limit": 10})
            res.raise_for_status()
            data = res.json()
            result = data.get("result", []) if isinstance(data, dict) else []
            items = []
            for asset in result:
                if isinstance(asset, dict):
                    items.append({
                        "symbol": asset.get("identifier", asset.get("symbol", "")),
                        "name": asset.get("name", asset.get("identifier", "")),
                        "dataSource": "rotki",
                        "currency": "USD",
                        "assetClass": "CRYPTO",
                    })
                elif isinstance(asset, str):
                    items.append({
                        "symbol": asset,
                        "name": asset,
                        "dataSource": "rotki",
                        "currency": "USD",
                        "assetClass": "CRYPTO",
                    })
            return {"items": items}
        except Exception:
            # Fallback: try the simpler /api/1/assets endpoint
            try:
                res = await self._client.get("/api/1/assets", params={"search": query})
                res.raise_for_status()
                data = res.json()
                assets = data.get("result", {}) if isinstance(data, dict) else {}
                items = [
                    {"symbol": k, "name": k, "dataSource": "rotki", "currency": "USD", "assetClass": "CRYPTO"}
                    for k in (list(assets.keys())[:10] if isinstance(assets, dict) else [])
                ]
                return {"items": items}
            except Exception:
                return {"items": []}

    async def get_symbol_details(self, data_source: str, symbol: str) -> dict:
        """GET /api/1/assets/prices/latest — get current price."""
        try:
            res = await self._client.post(
                "/api/1/assets/prices/latest",
                json={"assets": [symbol], "target_asset": "USD", "ignore_cache": False},
            )
            res.raise_for_status()
            data = res.json()
            result = data.get("result", {}) if isinstance(data, dict) else {}

            # Result is typically {symbol: {target: price}}
            price_data = result.get("assets", result)
            price = 0
            if isinstance(price_data, dict):
                sym_prices = price_data.get(symbol, {})
                if isinstance(sym_prices, dict):
                    price = float(sym_prices.get("USD", sym_prices.get("usd", 0)))
                elif isinstance(sym_prices, (int, float)):
                    price = float(sym_prices)

            return {
                "symbol": symbol,
                "name": symbol,
                "marketPrice": price,
                "currency": "USD",
                "dataSource": "rotki",
            }
        except Exception:
            return {"symbol": symbol, "name": symbol, "marketPrice": 0, "currency": "USD", "dataSource": "rotki"}

    async def get_symbol_history(self, data_source: str, symbol: str, days: int = 365) -> dict:
        """Get historical price data — Rotki may not have this readily available."""
        return {
            "symbol": symbol,
            "name": symbol,
            "historicalData": [],
            "dataSource": "rotki",
        }
