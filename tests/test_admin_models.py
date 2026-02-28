"""Unit tests for admin router Pydantic models."""

import pytest
from pydantic import ValidationError

from routers.admin import ImportRequest, RollbackRequest


class TestImportRequest:
    def test_valid_request(self):
        req = ImportRequest(
            orders=[{"symbol": "AAPL", "type": "BUY", "quantity": 10}],
            fileName="portfolio.csv",
            fileHash="abc123",
            accountId="acct-1",
        )
        assert req.fileName == "portfolio.csv"
        assert len(req.orders) == 1

    def test_empty_orders(self):
        req = ImportRequest(orders=[], fileName="empty.csv", fileHash="hash", accountId="acct")
        assert req.orders == []

    def test_missing_required_field(self):
        with pytest.raises(ValidationError):
            ImportRequest(orders=[], fileName="f.csv", fileHash="h")  # missing accountId

    def test_multiple_orders(self):
        orders = [
            {"symbol": "AAPL", "type": "BUY"},
            {"symbol": "MSFT", "type": "SELL"},
            {"symbol": "GOOGL", "type": "BUY"},
        ]
        req = ImportRequest(orders=orders, fileName="multi.csv", fileHash="xyz", accountId="a1")
        assert len(req.orders) == 3


class TestRollbackRequest:
    def test_empty_model(self):
        req = RollbackRequest()
        assert req is not None
