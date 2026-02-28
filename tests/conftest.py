"""Shared fixtures for agent-folio tests."""

import os
import sys
from unittest.mock import AsyncMock

import pytest

# Ensure the project root is on sys.path so `from services.X import Y` works
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Mock the db module BEFORE any application code tries to import asyncpg.
# asyncpg is a C-extension that requires a running Postgres, so we replace
# the entire services.db module with an in-memory stub during tests.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _mock_db(monkeypatch):
    """Replace every async db function with a no-op AsyncMock.

    This runs automatically for every test so that importing routers or
    agent_service never triggers a real database call.
    """
    from services import db

    monkeypatch.setattr(db, "init_db", AsyncMock())
    monkeypatch.setattr(db, "close_db", AsyncMock())
    monkeypatch.setattr(db, "list_conversations", AsyncMock(return_value={"conversations": []}))
    monkeypatch.setattr(db, "get_conversation", AsyncMock(return_value={"conversation": {}}))
    monkeypatch.setattr(db, "create_conversation", AsyncMock())
    monkeypatch.setattr(db, "add_message", AsyncMock())
    monkeypatch.setattr(db, "delete_conversation", AsyncMock(return_value={"success": True}))
    monkeypatch.setattr(db, "add_feedback", AsyncMock(return_value={"success": True}))
    monkeypatch.setattr(db, "get_feedback_summary", AsyncMock(return_value={"total": 0}))
    monkeypatch.setattr(
        db,
        "load_settings",
        AsyncMock(return_value={"sdk": "litellm", "model": "gpt-4o-mini"}),
    )
    monkeypatch.setattr(db, "save_settings", AsyncMock())
    monkeypatch.setattr(db, "save_eval_run", AsyncMock(return_value="fake-run-id"))
    monkeypatch.setattr(db, "list_eval_runs", AsyncMock(return_value=[]))
    monkeypatch.setattr(db, "list_backend_connections", AsyncMock(return_value=[]))
    monkeypatch.setattr(db, "add_backend_connection", AsyncMock(return_value="fake-conn-id"))
    monkeypatch.setattr(db, "update_backend_connection", AsyncMock(return_value=True))
    monkeypatch.setattr(db, "delete_backend_connection", AsyncMock(return_value=True))
    monkeypatch.setattr(db, "get_active_backends", AsyncMock(return_value=[]))


@pytest.fixture()
def sample_portfolio_result():
    """A realistic portfolio_summary tool result."""
    return {
        "tool": "portfolio_summary",
        "result": {
            "success": True,
            "holdings": [
                {
                    "name": "Apple Inc.",
                    "symbol": "AAPL",
                    "currency": "USD",
                    "assetClass": "EQUITY",
                    "allocationInPercentage": "30.00",
                    "marketPrice": 227.50,
                    "quantity": 10,
                    "valueInBaseCurrency": 2275.0,
                },
                {
                    "name": "Microsoft Corp.",
                    "symbol": "MSFT",
                    "currency": "USD",
                    "assetClass": "EQUITY",
                    "allocationInPercentage": "25.00",
                    "marketPrice": 415.20,
                    "quantity": 5,
                    "valueInBaseCurrency": 2076.0,
                },
                {
                    "name": "Alphabet Inc.",
                    "symbol": "GOOGL",
                    "currency": "USD",
                    "assetClass": "EQUITY",
                    "allocationInPercentage": "20.00",
                    "marketPrice": 175.30,
                    "quantity": 8,
                    "valueInBaseCurrency": 1402.4,
                },
                {
                    "name": "NVIDIA Corp.",
                    "symbol": "NVDA",
                    "currency": "USD",
                    "assetClass": "EQUITY",
                    "allocationInPercentage": "15.00",
                    "marketPrice": 880.00,
                    "quantity": 2,
                    "valueInBaseCurrency": 1760.0,
                },
                {
                    "name": "Vanguard Total Stock Market ETF",
                    "symbol": "VTI",
                    "currency": "USD",
                    "assetClass": "EQUITY",
                    "allocationInPercentage": "10.00",
                    "marketPrice": 270.00,
                    "quantity": 3,
                    "valueInBaseCurrency": 810.0,
                },
            ],
            "summary": {},
        },
    }


@pytest.fixture()
def sample_tax_result():
    """A realistic tax_estimate tool result."""
    return {
        "tool": "tax_estimate",
        "result": {
            "success": True,
            "taxEstimate": {
                "taxRateUsed": 15,
                "positions": [],
                "totals": {
                    "costBasis": "7000.00",
                    "currentValue": "8323.40",
                    "totalUnrealizedGain": "1323.40",
                    "totalEstimatedTax": "198.51",
                    "gainPercentage": "18.91",
                },
            },
        },
    }


@pytest.fixture()
def sample_performance_result():
    """A realistic portfolio_performance tool result."""
    return {
        "tool": "portfolio_performance",
        "result": {
            "success": True,
            "range": "ytd",
            "performance": {
                "currentNetWorth": 8500.0,
                "totalInvestment": 7000.0,
                "netPerformance": 1500.0,
                "netPerformancePercentage": 0.2143,
            },
            "chartSummary": {
                "startDate": "2026-01-01",
                "endDate": "2026-02-27",
                "dataPoints": 58,
            },
        },
    }
