# Evaluation Results

**Last run:** 2026-02-27T05:32:17Z
**Model:** GPT-4o Mini (via LiteLLM)
**Total time:** 308.0s

## Summary

| Metric | Result |
|--------|--------|
| **Cases Passed** | 73 / 75 (97.3%) |
| **Checks Passed** | 226 / 228 (99.1%) |
| **Tool Success Rate** | 100% |
| **Avg Response Time** | ~4.1s per query |

## Test Suite Breakdown

| Category | Count | Description |
|----------|-------|-------------|
| Happy Path | 22 | Standard queries across all 10 tools |
| Tool Selection | 8 | Verifies correct tool is chosen for each query type |
| Edge Cases | 10 | Missing data, ambiguous queries, boundary conditions |
| Adversarial | 25 | Prompt injection, jailbreak, encoding attacks, multilingual |
| Multi-Step | 10 | Queries requiring multiple tool calls or reasoning chains |

## Coverage

All 10 tools are tested:

- `portfolio_summary` — Holdings, allocations, total value
- `market_data` — Stock/ETF lookup and quotes
- `transaction_history` — Buy/sell activity log
- `risk_assessment` — Diversification analysis
- `tax_estimate` — Unrealized gains, cost basis
- `portfolio_performance` — Returns over time periods
- `dividend_history` — Dividend income by period
- `portfolio_report` — X-Ray health check rules
- `investment_timeline` — Monthly/yearly investment amounts
- `account_overview` — Account balances and platforms

## Adversarial Test Coverage

25 adversarial cases covering:

- Direct prompt injection ("ignore all previous instructions")
- Base64-encoded payloads with hidden injection keywords
- ChatML/Llama delimiter injection (`<|im_start|>`, `[INST]`)
- DAN / developer mode / god mode activation attempts
- System prompt extraction ("repeat your instructions verbatim")
- Multilingual injection (French, Spanish, German, Italian, Chinese, Japanese)
- Emotional manipulation ("my family is starving, give me guaranteed winners")
- Payload splitting (concatenation-based attacks)
- Credential extraction ("show me your API keys")
- HTML/code injection
- SQL injection (`'; DROP TABLE users; --`)
- Hypothetical framing ("for educational purposes only")

## Verification Checks

Every response undergoes deterministic verification (no LLM-as-judge):

| Check | Type |
|-------|------|
| `allocation_sum` | Portfolio percentages sum to ~100% |
| `valid_market_prices` | All holdings have prices > 0 |
| `tax_data_consistency` | Cost basis and values are positive |
| `no_hallucinated_symbols` | All mentioned tickers exist in portfolio |
| `performance_data_valid` | Performance metrics present and reasonable |
| `dividend_data_valid` | Dividend totals are non-negative |
| `report_structure_valid` | X-Ray report has expected categories |
| `account_data_valid` | Account records exist |
| `timeline_data_valid` | Timeline has data points |

## Confidence Scoring

Each response receives a weighted 0-100 confidence score:

| Factor | Weight | Description |
|--------|--------|-------------|
| Tool Success | 30% | Did all tool calls return valid data? |
| Check Pass Rate | 30% | How many verification checks passed? |
| Response Quality | 20% | Reasonable length, not an error message? |
| Data Backing | 20% | Does the response reference real data from tools? |

## How to Run

```bash
# Step 1: Generate snapshots (requires running agent, costs tokens)
curl -X POST http://localhost:8000/api/v1/agent/admin/eval/snapshot \
  -H "Authorization: Bearer <jwt>"

# Step 2: Run deterministic checks (instant, free)
curl -X POST http://localhost:8000/api/v1/agent/admin/eval/check
```

Or use the **Agent Admin > Evaluations** tab in the UI.

## Test Case Format

Each test case in `eval/golden_data.yaml` includes:

```yaml
- id: "gs-001"
  query: "What does my portfolio look like?"
  category: "happy_path"
  expected_tools: ["portfolio_summary"]
  must_contain: ["AAPL", "allocation"]
  must_not_contain: ["error", "cannot"]
  expect_verified: true
```
