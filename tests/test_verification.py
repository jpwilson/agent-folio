"""Unit tests for services/verification.py — verify_response and confidence scoring."""

from services.verification import verify_response

# ============================================================
# Valid portfolio data (allocations sum to ~100%)
# ============================================================


class TestVerifyValidPortfolio:
    """verify_response should pass when allocations sum to ~100%."""

    def test_valid_allocations(self, sample_portfolio_result):
        result = verify_response(
            [sample_portfolio_result],
            "Your portfolio has AAPL at 30%, MSFT at 25%, GOOGL at 20%, NVDA at 15%, VTI at 10%.",
        )
        assert result["verified"] is True
        # allocation_sum check should pass
        alloc_check = next((c for c in result["checks"] if c["check"] == "allocation_sum"), None)
        assert alloc_check is not None
        assert alloc_check["passed"] is True


# ============================================================
# Bad allocation sums
# ============================================================


class TestVerifyCatchesBadAllocations:
    """verify_response should flag allocations that do not sum to ~100%."""

    def test_allocations_sum_over_105(self):
        tool_results = [
            {
                "tool": "portfolio_summary",
                "result": {
                    "success": True,
                    "holdings": [
                        {"symbol": "AAPL", "allocationInPercentage": "60.00", "marketPrice": 227.5},
                        {"symbol": "MSFT", "allocationInPercentage": "55.00", "marketPrice": 415.2},
                    ],
                },
            }
        ]
        result = verify_response(tool_results, "AAPL is 60%, MSFT is 55%.")
        alloc_check = next((c for c in result["checks"] if c["check"] == "allocation_sum"), None)
        assert alloc_check is not None
        assert alloc_check["passed"] is False

    def test_allocations_sum_under_95(self):
        tool_results = [
            {
                "tool": "portfolio_summary",
                "result": {
                    "success": True,
                    "holdings": [
                        {"symbol": "AAPL", "allocationInPercentage": "10.00", "marketPrice": 227.5},
                        {"symbol": "MSFT", "allocationInPercentage": "5.00", "marketPrice": 415.2},
                    ],
                },
            }
        ]
        result = verify_response(tool_results, "Your portfolio is tiny.")
        alloc_check = next((c for c in result["checks"] if c["check"] == "allocation_sum"), None)
        assert alloc_check is not None
        assert alloc_check["passed"] is False


# ============================================================
# Invalid market prices
# ============================================================


class TestVerifyCatchesInvalidMarketPrices:
    """verify_response should flag holdings with missing or zero market prices."""

    def test_zero_market_price(self):
        tool_results = [
            {
                "tool": "portfolio_summary",
                "result": {
                    "success": True,
                    "holdings": [
                        {"symbol": "AAPL", "allocationInPercentage": "50.00", "marketPrice": 0},
                        {"symbol": "MSFT", "allocationInPercentage": "50.00", "marketPrice": 415.2},
                    ],
                },
            }
        ]
        result = verify_response(tool_results, "Here is your portfolio.")
        price_check = next((c for c in result["checks"] if c["check"] == "valid_market_prices"), None)
        assert price_check is not None
        assert price_check["passed"] is False
        assert "AAPL" in price_check["detail"]

    def test_negative_market_price(self):
        tool_results = [
            {
                "tool": "portfolio_summary",
                "result": {
                    "success": True,
                    "holdings": [
                        {"symbol": "BAD", "allocationInPercentage": "100.00", "marketPrice": -5.0},
                    ],
                },
            }
        ]
        result = verify_response(tool_results, "Here is your portfolio.")
        price_check = next((c for c in result["checks"] if c["check"] == "valid_market_prices"), None)
        assert price_check is not None
        assert price_check["passed"] is False

    def test_missing_market_price(self):
        tool_results = [
            {
                "tool": "portfolio_summary",
                "result": {
                    "success": True,
                    "holdings": [
                        {"symbol": "NONE", "allocationInPercentage": "100.00"},
                    ],
                },
            }
        ]
        result = verify_response(tool_results, "Here is your portfolio.")
        price_check = next((c for c in result["checks"] if c["check"] == "valid_market_prices"), None)
        assert price_check is not None
        assert price_check["passed"] is False

    def test_all_valid_market_prices(self, sample_portfolio_result):
        result = verify_response(
            [sample_portfolio_result],
            "AAPL MSFT GOOGL NVDA VTI all have valid prices.",
        )
        price_check = next((c for c in result["checks"] if c["check"] == "valid_market_prices"), None)
        assert price_check is not None
        assert price_check["passed"] is True


# ============================================================
# Tax data consistency
# ============================================================


class TestVerifyTaxData:
    """verify_response should check tax data consistency."""

    def test_valid_tax_data(self, sample_tax_result):
        result = verify_response([sample_tax_result], "Your tax estimate is ready.")
        tax_check = next((c for c in result["checks"] if c["check"] == "tax_data_consistency"), None)
        assert tax_check is not None
        assert tax_check["passed"] is True

    def test_zero_cost_basis(self):
        tool_results = [
            {
                "tool": "tax_estimate",
                "result": {
                    "success": True,
                    "taxEstimate": {
                        "totals": {
                            "costBasis": "0",
                            "currentValue": "1000.00",
                        }
                    },
                },
            }
        ]
        result = verify_response(tool_results, "Tax estimate.")
        tax_check = next((c for c in result["checks"] if c["check"] == "tax_data_consistency"), None)
        assert tax_check is not None
        assert tax_check["passed"] is False

    def test_zero_current_value(self):
        tool_results = [
            {
                "tool": "tax_estimate",
                "result": {
                    "success": True,
                    "taxEstimate": {
                        "totals": {
                            "costBasis": "5000.00",
                            "currentValue": "0",
                        }
                    },
                },
            }
        ]
        result = verify_response(tool_results, "Tax estimate.")
        tax_check = next((c for c in result["checks"] if c["check"] == "tax_data_consistency"), None)
        assert tax_check is not None
        assert tax_check["passed"] is False


# ============================================================
# Performance data
# ============================================================


class TestVerifyPerformanceData:
    """verify_response should validate performance data fields."""

    def test_valid_performance_with_net_performance(self, sample_performance_result):
        result = verify_response([sample_performance_result], "Your portfolio returned 21%.")
        perf_check = next((c for c in result["checks"] if c["check"] == "performance_data_valid"), None)
        assert perf_check is not None
        assert perf_check["passed"] is True

    def test_valid_performance_with_chart_summary(self):
        tool_results = [
            {
                "tool": "portfolio_performance",
                "result": {
                    "success": True,
                    "performance": {},
                    "chartSummary": {"dataPoints": 30},
                },
            }
        ]
        result = verify_response(tool_results, "Performance data loaded.")
        perf_check = next((c for c in result["checks"] if c["check"] == "performance_data_valid"), None)
        assert perf_check is not None
        assert perf_check["passed"] is True

    def test_valid_performance_with_current_net_worth(self):
        tool_results = [
            {
                "tool": "portfolio_performance",
                "result": {
                    "success": True,
                    "performance": {"currentNetWorth": 10000.0},
                    "chartSummary": {},
                },
            }
        ]
        result = verify_response(tool_results, "Your net worth is $10,000.")
        perf_check = next((c for c in result["checks"] if c["check"] == "performance_data_valid"), None)
        assert perf_check is not None
        assert perf_check["passed"] is True

    def test_empty_performance_data(self):
        tool_results = [
            {
                "tool": "portfolio_performance",
                "result": {
                    "success": True,
                    "performance": {},
                    "chartSummary": {},
                },
            }
        ]
        result = verify_response(tool_results, "Performance data loaded.")
        perf_check = next((c for c in result["checks"] if c["check"] == "performance_data_valid"), None)
        assert perf_check is not None
        assert perf_check["passed"] is False


# ============================================================
# No tool results
# ============================================================


class TestVerifyNoToolResults:
    """verify_response with no tool results should return verified=True with empty checks."""

    def test_empty_tool_results(self):
        result = verify_response([], "Hello! How can I help with your investments?")
        assert result["verified"] is True
        assert result["checks"] == []

    def test_failed_tool_result(self):
        tool_results = [
            {
                "tool": "portfolio_summary",
                "result": {
                    "success": False,
                    "error": "Failed to fetch",
                },
            }
        ]
        result = verify_response(tool_results, "Sorry, I couldn't fetch your portfolio data.")
        # No checks should run since success is False
        assert result["verified"] is True


# ============================================================
# Confidence scoring
# ============================================================


class TestConfidenceScoring:
    """Confidence scores should be in range 0-100."""

    def test_confidence_range_with_tools(self, sample_portfolio_result):
        result = verify_response(
            [sample_portfolio_result],
            "AAPL MSFT GOOGL NVDA VTI are your holdings. Your portfolio is worth $8,323.",
        )
        confidence = result["confidence"]
        assert 0 <= confidence["overall"] <= 100
        for factor_name, factor_val in confidence["factors"].items():
            assert 0 <= factor_val <= 100, f"{factor_name} out of range: {factor_val}"

    def test_confidence_range_no_tools(self):
        result = verify_response([], "Hello!")
        confidence = result["confidence"]
        assert 0 <= confidence["overall"] <= 100

    def test_confidence_higher_with_successful_tools(self, sample_portfolio_result):
        result_with = verify_response(
            [sample_portfolio_result],
            "AAPL MSFT GOOGL NVDA VTI are your holdings. Your portfolio is well diversified.",
        )
        result_without = verify_response([], "I don't have data.")
        assert result_with["confidence"]["overall"] >= result_without["confidence"]["overall"]

    def test_confidence_factors_present(self, sample_portfolio_result):
        result = verify_response(
            [sample_portfolio_result],
            "AAPL MSFT GOOGL NVDA VTI portfolio summary.",
        )
        factors = result["confidence"]["factors"]
        assert "toolSuccess" in factors
        assert "checkPassRate" in factors
        assert "responseQuality" in factors
        assert "dataBacked" in factors

    def test_confidence_with_short_response(self):
        result = verify_response([], "OK")
        # Short response should lower responseQuality
        assert result["confidence"]["factors"]["responseQuality"] <= 60

    def test_confidence_with_uncertainty(self):
        result = verify_response([], "I'm not sure about that, I cannot find the data.")
        assert result["confidence"]["factors"]["responseQuality"] <= 70


# ============================================================
# Hallucinated symbol detection
# ============================================================


class TestHallucinatedSymbolDetection:
    """verify_response should detect symbols not in the portfolio."""

    def test_no_hallucination(self, sample_portfolio_result):
        result = verify_response(
            [sample_portfolio_result],
            "Your AAPL position is 30% of the portfolio. MSFT is at 25%.",
        )
        sym_check = next((c for c in result["checks"] if c["check"] == "no_hallucinated_symbols"), None)
        assert sym_check is not None
        assert sym_check["passed"] is True

    def test_hallucinated_symbol(self, sample_portfolio_result):
        result = verify_response(
            [sample_portfolio_result],
            "You should consider adding RIVN and PLTR to your portfolio alongside AAPL.",
        )
        sym_check = next((c for c in result["checks"] if c["check"] == "no_hallucinated_symbols"), None)
        assert sym_check is not None
        assert sym_check["passed"] is False
        assert "RIVN" in sym_check["detail"] or "PLTR" in sym_check["detail"]

    def test_common_words_not_flagged(self, sample_portfolio_result):
        """Words like 'USD', 'ETF', 'THE' should not be flagged as hallucinated symbols."""
        result = verify_response(
            [sample_portfolio_result],
            "Your AAPL and MSFT holdings are both in USD. The ETF VTI is diversified.",
        )
        sym_check = next((c for c in result["checks"] if c["check"] == "no_hallucinated_symbols"), None)
        assert sym_check is not None
        assert sym_check["passed"] is True
