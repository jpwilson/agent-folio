import httpx
from config import GHOSTFOLIO_URL


class GhostfolioClient:
    """Async HTTP client for Ghostfolio's public REST API."""

    def __init__(self, token: str):
        self.base_url = GHOSTFOLIO_URL
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    async def get_portfolio_details(self) -> dict:
        """GET /api/v1/portfolio/details — holdings, summary, accounts."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.get(
                f"{self.base_url}/api/v1/portfolio/details",
                headers=self.headers,
            )
            res.raise_for_status()
            return res.json()

    async def get_orders(self) -> dict:
        """GET /api/v1/order — transaction activities."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.get(
                f"{self.base_url}/api/v1/order",
                headers=self.headers,
            )
            res.raise_for_status()
            return res.json()

    async def lookup_symbol(self, query: str) -> dict:
        """GET /api/v1/symbol/lookup?query= — search for a symbol."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.get(
                f"{self.base_url}/api/v1/symbol/lookup",
                params={"query": query},
                headers=self.headers,
            )
            res.raise_for_status()
            return res.json()

    async def get_symbol_details(self, data_source: str, symbol: str) -> dict:
        """GET /api/v1/symbol/{dataSource}/{symbol} — symbol details + price."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.get(
                f"{self.base_url}/api/v1/symbol/{data_source}/{symbol}",
                headers=self.headers,
            )
            res.raise_for_status()
            return res.json()
