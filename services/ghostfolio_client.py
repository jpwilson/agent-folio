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

    async def get_portfolio_performance(self, date_range: str = "max") -> dict:
        """GET /api/v2/portfolio/performance — performance with chart data."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.get(
                f"{self.base_url}/api/v2/portfolio/performance",
                params={"range": date_range},
                headers=self.headers,
            )
            res.raise_for_status()
            return res.json()

    async def get_dividends(self, date_range: str = "max", group_by: str | None = None) -> dict:
        """GET /api/v1/portfolio/dividends — dividend history."""
        params: dict = {"range": date_range}
        if group_by:
            params["groupBy"] = group_by
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.get(
                f"{self.base_url}/api/v1/portfolio/dividends",
                params=params,
                headers=self.headers,
            )
            res.raise_for_status()
            return res.json()

    async def get_portfolio_report(self) -> dict:
        """GET /api/v1/portfolio/report — X-Ray rules engine analysis."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.get(
                f"{self.base_url}/api/v1/portfolio/report",
                headers=self.headers,
            )
            res.raise_for_status()
            return res.json()

    async def get_portfolio_investments(self, date_range: str = "max", group_by: str | None = None) -> dict:
        """GET /api/v1/portfolio/investments — investment timeline."""
        params: dict = {"range": date_range}
        if group_by:
            params["groupBy"] = group_by
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.get(
                f"{self.base_url}/api/v1/portfolio/investments",
                params=params,
                headers=self.headers,
            )
            res.raise_for_status()
            return res.json()

    async def get_benchmarks(self) -> dict:
        """GET /api/v1/benchmarks — available benchmark indices."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.get(
                f"{self.base_url}/api/v1/benchmarks",
                headers=self.headers,
            )
            res.raise_for_status()
            return res.json()

    async def get_accounts(self) -> dict:
        """GET /api/v1/account — all accounts with balances."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.get(
                f"{self.base_url}/api/v1/account",
                headers=self.headers,
            )
            res.raise_for_status()
            return res.json()
