"""Abstract base class for portfolio backend providers.

Every provider normalizes its data to match the shapes that tools expect.
The canonical shapes are documented in each method's docstring and follow
Ghostfolio's API response format (since that was the original backend).
"""

from abc import ABC, abstractmethod


class PortfolioProvider(ABC):
    """Interface that all portfolio backends must implement."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Short identifier, e.g. 'ghostfolio' or 'rotki'."""
        ...

    # ------------------------------------------------------------------
    # Portfolio reads
    # ------------------------------------------------------------------

    @abstractmethod
    async def get_portfolio_details(self) -> dict:
        """Return portfolio holdings and summary.

        Expected shape::

            {
                "holdings": [
                    {
                        "name": str,
                        "symbol": str,
                        "currency": str,
                        "assetClass": str,
                        "assetSubClass": str | None,
                        "allocationInPercentage": float,  # 0-1 scale
                        "marketPrice": float,
                        "quantity": float,
                        "valueInBaseCurrency": float,
                    },
                    ...
                ],
                "summary": { ... }
            }
        """
        ...

    @abstractmethod
    async def get_orders(self) -> dict:
        """Return transaction activities.

        Expected shape::

            {
                "activities": [
                    {
                        "id": str,
                        "date": str (ISO),
                        "symbol": str,
                        "type": "BUY" | "SELL" | "DIVIDEND",
                        "quantity": float,
                        "unitPrice": float,
                        "fee": float,
                        "currency": str,
                        "dataSource": str | None,
                    },
                    ...
                ]
            }
        """
        ...

    @abstractmethod
    async def get_portfolio_performance(self, date_range: str = "max") -> dict:
        """Return performance with chart data.

        Expected shape::

            {
                "chart": [ {"date": str, "value": float}, ... ],
                "performance": {
                    "currentNetWorth": float,
                    "totalInvestment": float,
                    "netPerformance": float,
                    "netPerformancePercentage": float,
                },
            }
        """
        ...

    @abstractmethod
    async def get_dividends(self, date_range: str = "max", group_by: str | None = None) -> dict:
        """Return dividend history.

        Expected shape::

            {
                "dividends": [ {"date": str, "amount": float}, ... ]
            }
        """
        ...

    @abstractmethod
    async def get_portfolio_report(self) -> dict:
        """Return X-Ray rules engine analysis.

        Expected shape: Ghostfolio report JSON or empty ``{}``.
        """
        ...

    @abstractmethod
    async def get_portfolio_investments(self, date_range: str = "max", group_by: str | None = None) -> dict:
        """Return investment timeline.

        Expected shape::

            {
                "investments": [ {"date": str, "investment": float}, ... ]
            }
        """
        ...

    @abstractmethod
    async def get_accounts(self) -> dict:
        """Return accounts list.

        Expected shape::

            {
                "accounts": [
                    {"id": str, "name": str, "balance": float, "currency": str, "platformId": str | None},
                    ...
                ]
            }
        """
        ...

    # ------------------------------------------------------------------
    # Market data
    # ------------------------------------------------------------------

    @abstractmethod
    async def lookup_symbol(self, query: str) -> dict:
        """Search for a symbol by name or ticker.

        Expected shape::

            { "items": [ {"symbol": str, "name": str, "dataSource": str, "currency": str, ...}, ... ] }
        """
        ...

    @abstractmethod
    async def get_symbol_details(self, data_source: str, symbol: str) -> dict:
        """Get detailed info + current price for a symbol."""
        ...

    @abstractmethod
    async def get_symbol_history(self, data_source: str, symbol: str, days: int = 365) -> dict:
        """Get historical price data for a symbol."""
        ...

    # ------------------------------------------------------------------
    # Write operations (optional — default raises)
    # ------------------------------------------------------------------

    async def create_order(self, order_data: dict) -> dict:
        """Create a new activity/order. Override if the backend supports writes."""
        raise NotImplementedError(f"{self.provider_name} does not support creating orders")

    async def delete_order(self, order_id: str) -> bool:
        """Delete an activity/order. Override if the backend supports writes."""
        raise NotImplementedError(f"{self.provider_name} does not support deleting orders")
