"""Combined provider that merges data from multiple backends.

When a user has multiple active backends (e.g., Ghostfolio + Rotki), this
provider fetches from all of them and merges the results. If one backend
fails, the other's data still returns (graceful degradation).
"""

import logging

from services.providers.base import PortfolioProvider

logger = logging.getLogger(__name__)


class CombinedProvider(PortfolioProvider):
    """Merges data from multiple PortfolioProvider instances."""

    def __init__(self, providers: list[PortfolioProvider]):
        self._providers = providers

    @property
    def provider_name(self) -> str:
        names = [p.provider_name for p in self._providers]
        return " + ".join(n.capitalize() for n in names)

    async def _gather_results(self, method_name: str, *args, **kwargs) -> list[tuple[str, dict]]:
        """Call the same method on all providers, returning (provider_name, result) pairs.

        Failed providers are silently skipped with logging.
        """
        results = []
        for provider in self._providers:
            try:
                method = getattr(provider, method_name)
                result = await method(*args, **kwargs)
                results.append((provider.provider_name, result))
            except Exception as e:
                logger.warning("Provider %s.%s failed: %s", provider.provider_name, method_name, e)
        return results

    # ------------------------------------------------------------------
    # Portfolio reads
    # ------------------------------------------------------------------

    async def get_portfolio_details(self) -> dict:
        """Merge holdings from all providers, recompute allocations, tag with _source."""
        results = await self._gather_results("get_portfolio_details")
        if not results:
            return {"holdings": [], "summary": {}}

        all_holdings = []
        total_value = 0.0
        summary = {}

        for source, data in results:
            for h in data.get("holdings", []):
                h["_source"] = source
                all_holdings.append(h)
                total_value += float(h.get("valueInBaseCurrency", 0))
            # Merge summary info
            if data.get("summary"):
                summary.update(data["summary"])

        # Recompute allocations to sum to 100%
        for h in all_holdings:
            if total_value > 0:
                h["allocationInPercentage"] = float(h.get("valueInBaseCurrency", 0)) / total_value
            else:
                h["allocationInPercentage"] = 0

        summary["netWorth"] = total_value
        return {"holdings": all_holdings, "summary": summary}

    async def get_orders(self) -> dict:
        """Merge all activities, sort by date descending, tag with _source."""
        results = await self._gather_results("get_orders")
        all_activities = []
        for source, data in results:
            activities = data.get("activities", [])
            for a in activities:
                a["_source"] = source
                all_activities.append(a)

        # Sort by date descending
        all_activities.sort(key=lambda a: a.get("date", ""), reverse=True)
        return {"activities": all_activities}

    async def get_portfolio_performance(self, date_range: str = "max") -> dict:
        """Aggregate performance from all providers."""
        results = await self._gather_results("get_portfolio_performance", date_range)
        if not results:
            return {"chart": [], "performance": {}}

        # Take the first provider's chart as base, sum performance stats
        combined_chart = []
        total_net_worth = 0.0
        total_investment = 0.0
        total_net_perf = 0.0

        for _source, data in results:
            perf = data.get("performance", {})
            total_net_worth += float(perf.get("currentNetWorth", 0))
            total_investment += float(perf.get("totalInvestment", 0))
            total_net_perf += float(perf.get("netPerformance", 0))
            if not combined_chart and data.get("chart"):
                combined_chart = data["chart"]

        return {
            "chart": combined_chart,
            "performance": {
                "currentNetWorth": total_net_worth,
                "totalInvestment": total_investment,
                "netPerformance": total_net_perf,
                "netPerformancePercentage": total_net_perf / total_investment if total_investment > 0 else 0,
            },
        }

    async def get_dividends(self, date_range: str = "max", group_by: str | None = None) -> dict:
        """Merge available dividend data from all providers."""
        results = await self._gather_results("get_dividends", date_range, group_by)
        all_dividends = []
        for _source, data in results:
            all_dividends.extend(data.get("dividends", []))
        return {"dividends": all_dividends}

    async def get_portfolio_report(self) -> dict:
        """Return first non-empty report."""
        results = await self._gather_results("get_portfolio_report")
        for _source, data in results:
            if data:
                return data
        return {}

    async def get_portfolio_investments(self, date_range: str = "max", group_by: str | None = None) -> dict:
        """Merge investment timeline data."""
        results = await self._gather_results("get_portfolio_investments", date_range, group_by)
        all_investments = []
        for _source, data in results:
            all_investments.extend(data.get("investments", []))
        return {"investments": all_investments}

    async def get_accounts(self) -> dict:
        """Concatenate accounts from all providers, tag with _source."""
        results = await self._gather_results("get_accounts")
        all_accounts = []
        for source, data in results:
            accounts = data.get("accounts", data) if isinstance(data, dict) else data if isinstance(data, list) else []
            if isinstance(accounts, list):
                for acct in accounts:
                    if isinstance(acct, dict):
                        acct["_source"] = source
                        all_accounts.append(acct)
        return {"accounts": all_accounts}

    # ------------------------------------------------------------------
    # Market data — try each provider, return first non-empty
    # ------------------------------------------------------------------

    async def lookup_symbol(self, query: str) -> dict:
        """Try each provider, return first non-empty result."""
        for provider in self._providers:
            try:
                result = await provider.lookup_symbol(query)
                if result.get("items"):
                    return result
            except Exception:
                continue
        return {"items": []}

    async def get_symbol_details(self, data_source: str, symbol: str) -> dict:
        """Try each provider for symbol details."""
        for provider in self._providers:
            try:
                result = await provider.get_symbol_details(data_source, symbol)
                if result.get("marketPrice"):
                    return result
            except Exception:
                continue
        return {}

    async def get_symbol_history(self, data_source: str, symbol: str, days: int = 365) -> dict:
        """Try each provider for historical data."""
        for provider in self._providers:
            try:
                result = await provider.get_symbol_history(data_source, symbol, days)
                if result.get("historicalData"):
                    return result
            except Exception:
                continue
        return {"historicalData": []}

    # ------------------------------------------------------------------
    # Write operations — delegate to first provider that supports it
    # ------------------------------------------------------------------

    async def create_order(self, order_data: dict) -> dict:
        for provider in self._providers:
            try:
                return await provider.create_order(order_data)
            except NotImplementedError:
                continue
        raise NotImplementedError("No connected backend supports creating orders")

    async def delete_order(self, order_id: str) -> bool:
        for provider in self._providers:
            try:
                return await provider.delete_order(order_id)
            except NotImplementedError:
                continue
        raise NotImplementedError("No connected backend supports deleting orders")
