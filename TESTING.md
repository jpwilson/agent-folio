# Testing Guide for Agent-Folio

## Test Categories

### 1. Unit Tests

**`tests/test_guardrails.py`** -- Tests the guardrails pre-filter and post-filter logic:
- Pre-filter allows financial questions and greetings
- Pre-filter blocks prompt injection attempts (jailbreaks, persona overrides, instruction reveals)
- Pre-filter blocks encoded payloads (base64, hex, rot13)
- Pre-filter blocks delimiter injection (ChatML, INST tags, system tags)
- Pre-filter blocks profanity with professional redirect
- Pre-filter blocks multilingual injection (French, Spanish, German, Chinese, Japanese, Italian)
- Post-filter passes clean financial responses
- Post-filter catches pirate/persona language (tone hijacking)
- Post-filter catches system prompt leakage
- Post-filter catches credential leakage (API keys, JWTs, passwords)
- Helper: `validate_message_roles` strips system roles and enforces limits
- Helper: `normalize_unicode` strips zero-width characters
- Helper: `sanitize_input` strips HTML tags and markdown images

**`tests/test_verification.py`** -- Tests the domain-specific verification layer:
- Valid portfolio data with allocations summing to ~100%
- Catches bad allocation sums (over 105% or under 95%)
- Catches invalid/missing/negative market prices
- Tax data consistency (cost basis > 0, current value > 0)
- Performance data validation (netPerformance, chartSummary, currentNetWorth)
- Behavior with no tool results (verified=True, empty checks)
- Confidence scoring ranges (0-100 for all factors)
- Hallucinated symbol detection (symbols not in portfolio flagged)

**`tests/test_tools.py`** -- Tests tool definition structure across all 10 tools:
- Every tool module exports a `TOOL_DEFINITION` dict and `execute` function
- Definitions have `type: "function"` with a `function` key
- Function has `name`, `description`, and `parameters`
- Parameter schemas follow JSON Schema conventions (`type: "object"`, `properties` dict)
- Property values have `type` and `description` keys
- Tool names are unique and match the `ALL_TOOLS` registry

### 2. Integration Tests

**`tests/test_api.py`** -- Tests FastAPI endpoints via httpx `AsyncClient`:
- `GET /api/v1/agent/config` returns 200 with `ghostfolioUrl`
- `GET /health` returns 200 with `status: "ok"`
- `POST /api/v1/agent/chat` without Bearer token returns 401
- `GET /api/v1/agent/admin/settings` returns SDK and model options
- `GET /api/v1/agent/conversations` without auth returns 401
- `POST /api/v1/agent/auth/login` validates request body

### 3. Linting

Ruff is configured in `pyproject.toml` for code quality checks.

## How to Run Tests

### Install dev dependencies

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

### Run all tests

```bash
pytest
```

### Run with verbose output

```bash
pytest -v
```

### Run a specific test file

```bash
pytest tests/test_guardrails.py
pytest tests/test_verification.py
pytest tests/test_tools.py
pytest tests/test_api.py
```

### Run a specific test class or function

```bash
pytest tests/test_guardrails.py::TestPreFilterBlocksPromptInjection
pytest tests/test_guardrails.py::TestPreFilterBlocksPromptInjection::test_jailbreak
```

### Run with coverage

```bash
pytest --cov=services --cov=tools --cov=routers --cov-report=term-missing
```

### Generate HTML coverage report

```bash
pytest --cov=services --cov=tools --cov=routers --cov-report=html
open htmlcov/index.html
```

### Run linter

```bash
ruff check .
```

### Auto-fix lint issues

```bash
ruff check --fix .
```

## Coverage Report

Coverage is configured in `pyproject.toml` under `[tool.coverage.run]`:
- **Source directories**: `services/`, `tools/`, `routers/`, `models/`
- **Excluded**: `tests/`, `eval/`, `sdks/`
- **Minimum threshold**: 50%

## Test Infrastructure

### Fixtures (`tests/conftest.py`)

- `_mock_db` (autouse): Mocks all `services.db` async functions so tests never require a running PostgreSQL database
- `sample_portfolio_result`: Realistic portfolio_summary tool result with 5 holdings
- `sample_tax_result`: Realistic tax_estimate tool result
- `sample_performance_result`: Realistic portfolio_performance tool result

### Database Mocking

Since `asyncpg` requires a running PostgreSQL server, all database functions are automatically mocked via the `_mock_db` fixture. This runs for every test (autouse=True). The mocks return sensible defaults:
- `load_settings` returns `{"sdk": "litellm", "model": "gpt-4o-mini"}`
- `list_conversations` returns `{"conversations": []}`
- Write operations (`create_conversation`, `add_message`, etc.) are no-ops
