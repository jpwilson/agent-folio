"""Invest Insight as a PortfolioProvider.

Maps Invest Insight properties into Ghostfolio-compatible holdings so the
agent can reason about real estate alongside traditional securities.
"""

import httpx

from services.providers.base import PortfolioProvider


class InvestInsightProvider(PortfolioProvider):
    """Adapter that presents Invest Insight properties as portfolio holdings."""

    def __init__(self, base_url: str, api_token: str):
        self.base_url = base_url.rstrip("/")
        headers = {"Content-Type": "application/json"}
        if api_token:
            headers["Authorization"] = f"Bearer {api_token}"
        self._client = httpx.AsyncClient(base_url=self.base_url, headers=headers, timeout=30.0)

    @property
    def provider_name(self) -> str:
        return "invest_insight"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_properties(self) -> list[dict]:
        resp = await self._client.get("/api/v1/properties")
        resp.raise_for_status()
        return resp.json().get("properties", [])

    async def _get_summary(self) -> dict:
        resp = await self._client.get("/api/v1/properties/summary")
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Portfolio reads
    # ------------------------------------------------------------------

    async def get_portfolio_details(self) -> dict:
        properties = await self._get_properties()
        summary = await self._get_summary()

        total_value = summary.get("total_current_value", 0) or 1

        holdings = []
        for p in properties:
            current = p.get("current_value") or p.get("purchase_price") or 0
            holdings.append(
                {
                    "name": p["name"],
                    "symbol": p["name"],
                    "currency": "USD",
                    "assetClass": "REAL_ESTATE",
                    "assetSubClass": _map_subclass(p.get("business_type")),
                    "allocationInPercentage": current / total_value if total_value else 0,
                    "marketPrice": current,
                    "quantity": 1,
                    "valueInBaseCurrency": current,
                    "_investInsight": {
                        "id": p.get("id"),
                        "address": p.get("address"),
                        "status": p.get("status"),
                        "purchasePrice": p.get("purchase_price"),
                        "businessType": p.get("business_type"),
                    },
                }
            )

        return {
            "holdings": holdings,
            "summary": {
                "currentNetWorth": summary.get("total_current_value", 0),
                "totalInvestment": summary.get("total_purchase_value", 0),
                "netPerformance": summary.get("total_gain_loss", 0),
                "netPerformancePercentage": (
                    summary.get("total_gain_loss", 0) / summary.get("total_purchase_value", 1)
                    if summary.get("total_purchase_value")
                    else 0
                ),
                "activeCount": summary.get("active_count", 0),
                "soldCount": summary.get("sold_count", 0),
            },
        }

    async def get_orders(self) -> dict:
        """Map properties to BUY activities (and SELL for sold ones)."""
        properties = await self._get_properties()
        activities = []
        for p in properties:
            # Purchase activity
            if p.get("purchase_price"):
                activities.append(
                    {
                        "id": f"{p['id']}-buy",
                        "date": p.get("purchase_date") or p.get("created_at", ""),
                        "symbol": p["name"],
                        "type": "BUY",
                        "quantity": 1,
                        "unitPrice": p["purchase_price"],
                        "fee": 0,
                        "currency": "USD",
                        "dataSource": "INVEST_INSIGHT",
                    }
                )
            # Sale activity
            if p.get("status") == "sold" and p.get("sale_price"):
                activities.append(
                    {
                        "id": f"{p['id']}-sell",
                        "date": p.get("sale_date") or "",
                        "symbol": p["name"],
                        "type": "SELL",
                        "quantity": 1,
                        "unitPrice": p["sale_price"],
                        "fee": 0,
                        "currency": "USD",
                        "dataSource": "INVEST_INSIGHT",
                    }
                )
        return {"activities": activities}

    async def get_portfolio_performance(self, date_range: str = "max") -> dict:
        summary = await self._get_summary()
        return {
            "chart": [],
            "performance": {
                "currentNetWorth": summary.get("total_current_value", 0),
                "totalInvestment": summary.get("total_purchase_value", 0),
                "netPerformance": summary.get("total_gain_loss", 0),
                "netPerformancePercentage": (
                    summary.get("total_gain_loss", 0) / summary.get("total_purchase_value", 1)
                    if summary.get("total_purchase_value")
                    else 0
                ),
            },
        }

    async def get_dividends(self, date_range: str = "max", group_by: str | None = None) -> dict:
        return {"dividends": []}

    async def get_portfolio_report(self) -> dict:
        return {}

    async def get_portfolio_investments(self, date_range: str = "max", group_by: str | None = None) -> dict:
        properties = await self._get_properties()
        investments = []
        for p in properties:
            if p.get("purchase_price") and p.get("purchase_date"):
                investments.append(
                    {
                        "date": p["purchase_date"],
                        "investment": p["purchase_price"],
                    }
                )
        investments.sort(key=lambda x: x["date"])
        return {"investments": investments}

    async def get_accounts(self) -> dict:
        summary = await self._get_summary()
        return {
            "accounts": [
                {
                    "id": "invest-insight-properties",
                    "name": "Invest Insight Properties",
                    "balance": summary.get("total_current_value", 0),
                    "currency": "USD",
                    "platformId": None,
                }
            ]
        }

    # ------------------------------------------------------------------
    # Market data (not applicable — return empty)
    # ------------------------------------------------------------------

    async def lookup_symbol(self, query: str) -> dict:
        return {"items": []}

    async def get_symbol_details(self, data_source: str, symbol: str) -> dict:
        return {}

    async def get_symbol_history(self, data_source: str, symbol: str, days: int = 365) -> dict:
        return {"historicalData": []}


def _map_subclass(business_type: str | None) -> str:
    """Map Invest Insight business type to a Ghostfolio-compatible subclass."""
    if not business_type:
        return "RENTAL_PROPERTY"
    bt = business_type.lower()
    commercial = {
        "restaurant",
        "gym",
        "coffee_shop",
        "bar",
        "bakery",
        "auto_repair",
        "salon",
        "laundromat",
        "pet_store",
        "pharmacy",
        "convenience_store",
        "supermarket",
        "clothing_store",
        "hardware_store",
        "bookstore",
    }
    if bt in commercial:
        return "SMALL_BUSINESS"
    return "RENTAL_PROPERTY"
