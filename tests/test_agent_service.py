"""Unit tests for services/agent_service.py — extract_followups and constants."""

from services.agent_service import GUARDRAIL_FOLLOWUPS, SYSTEM_PROMPT, _extract_followups

# ============================================================
# _extract_followups
# ============================================================


class TestExtractFollowups:
    """Tests for the >>> follow-up extraction logic."""

    def test_extracts_three_followups(self):
        text = (
            "Your portfolio is worth $10,000.\n"
            ">>> How has AAPL performed?\n"
            ">>> What are my dividends?\n"
            ">>> Show me my risk assessment"
        )
        cleaned, followups = _extract_followups(text)
        assert cleaned == "Your portfolio is worth $10,000."
        assert len(followups) == 3
        assert followups[0] == "How has AAPL performed?"
        assert followups[1] == "What are my dividends?"
        assert followups[2] == "Show me my risk assessment"

    def test_caps_at_three(self):
        text = "Response text.\n>>> Q1\n>>> Q2\n>>> Q3\n>>> Q4\n>>> Q5"
        _, followups = _extract_followups(text)
        assert len(followups) == 3

    def test_no_followups(self):
        text = "Just a normal response with no suggestions."
        cleaned, followups = _extract_followups(text)
        assert cleaned == text
        assert followups == []

    def test_empty_followup_lines_skipped(self):
        text = "Response.\n>>>\n>>> Valid question?"
        _, followups = _extract_followups(text)
        assert len(followups) == 1
        assert followups[0] == "Valid question?"

    def test_preserves_non_followup_lines(self):
        text = "Line 1\nLine 2\n>>> Follow up?\nLine 3"
        cleaned, followups = _extract_followups(text)
        assert "Line 1" in cleaned
        assert "Line 2" in cleaned
        assert "Line 3" in cleaned
        assert ">>>" not in cleaned
        assert len(followups) == 1

    def test_strips_trailing_blank_lines(self):
        text = "Response.\n\n\n>>> Question?"
        cleaned, _ = _extract_followups(text)
        assert not cleaned.endswith("\n")

    def test_followups_with_extra_spaces(self):
        text = "Data.\n>>>   Spaced out question?  "
        _, followups = _extract_followups(text)
        assert followups[0] == "Spaced out question?"


# ============================================================
# Constants
# ============================================================


class TestConstants:
    """Verify important constants are configured correctly."""

    def test_guardrail_followups_has_three(self):
        assert len(GUARDRAIL_FOLLOWUPS) == 3

    def test_guardrail_followups_are_financial(self):
        for q in GUARDRAIL_FOLLOWUPS:
            assert isinstance(q, str)
            assert len(q) > 10

    def test_system_prompt_has_tool_list(self):
        assert "portfolio_summary" in SYSTEM_PROMPT
        assert "market_data" in SYSTEM_PROMPT
        assert "transaction_history" in SYSTEM_PROMPT

    def test_system_prompt_has_chart_instructions(self):
        assert "chart" in SYSTEM_PROMPT
        assert "pie" in SYSTEM_PROMPT

    def test_system_prompt_has_followup_instructions(self):
        assert ">>>" in SYSTEM_PROMPT

    def test_system_prompt_has_guardrail_rules(self):
        assert "STRICT RULES" in SYSTEM_PROMPT
        assert "Stay on topic" in SYSTEM_PROMPT
        assert "prompt injection" in SYSTEM_PROMPT
