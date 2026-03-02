# Agent-Folio

AI-powered portfolio assistant for [Ghostfolio](https://ghostfol.io), [Rotki](https://rotki.com), and more. A standalone sidecar service that provides natural-language portfolio analysis, verification, and multi-backend support.

**[Live Demo](https://agent-folio-production.up.railway.app)** | [Architecture](ARCHITECTURE.md) | [Contributing](CONTRIBUTING.md) | [Security](SECURITY.md) | [Eval Results](EVAL_RESULTS.md)

## What It Does

Ask questions about your portfolio in plain English. Agent-Folio connects to your existing wealth management tools, calls the right APIs, and returns verified answers.

```
You:   "How diversified is my portfolio? Am I too concentrated in tech?"
Agent: Calls risk_assessment tool -> analyzes holdings -> returns sector breakdown
       with risk flags and diversification score, verified against actual data.
```

## Features

- **11 financial tools** — Portfolio summary, market data, transactions, risk assessment, tax estimates, performance, dividends, X-Ray health check, investment timeline, account overview, stock history
- **Multi-backend** — Connect Ghostfolio (stocks/ETFs), Rotki (crypto), or both simultaneously via a unified provider interface
- **4 SDK adapters + OpenRouter** — LiteLLM (default, 100+ models), OpenAI, Anthropic, LangChain. Bring your own API key via OpenRouter for access to Gemini, Llama, DeepSeek, and more
- **Verification layer** — Deterministic checks on every response: allocation sums, price validity, hallucination detection, confidence scoring (no LLM-as-judge)
- **Guardrails** — Pre/post filtering for topic enforcement, tone control, prompt injection defense, and credential leakage prevention
- **75 eval test cases** — Happy path, tool selection, edge cases, adversarial/jailbreak, multi-step reasoning
- **Observability** — Langfuse integration for tracing, latency monitoring, token usage, and cost analysis
- **Portfolio import** — Drag-and-drop CSV/JSON import with duplicate detection and rollback
- **Admin panel** — Switch models, run evals, view analytics, manage feedback — all from the UI
- **User feedback** — Thumbs up/down with optional explanations, persisted for analysis

## Quick Start

### Prerequisites

- Python 3.11+ (or Docker)
- PostgreSQL database (can share with Ghostfolio)
- At least one backend running (Ghostfolio and/or Rotki)
- At least one LLM API key (OpenAI, Anthropic, or OpenRouter)

### Option 1: Docker (recommended)

```bash
git clone https://github.com/jpwilson/agent-folio.git
cd agent-folio

# Configure
cp .env.example .env
# Edit .env — set DATABASE_URL, JWT_SECRET, and an LLM API key

# Run
docker compose up -d

# Open http://localhost:8000
```

### Option 2: Local Python

```bash
git clone https://github.com/jpwilson/agent-folio.git
cd agent-folio

pip install -r requirements.txt

cp .env.example .env
# Edit .env — set DATABASE_URL, JWT_SECRET, and an LLM API key

uvicorn main:app --reload --port 8000

# Open http://localhost:8000
```

### Connecting Backends

Agent-Folio needs at least one portfolio backend to query:

**Ghostfolio** (stocks, ETFs, mutual funds):
1. Run Ghostfolio locally or use a hosted instance
2. Set `GHOSTFOLIO_URL` and `JWT_SECRET` in `.env` (same secret Ghostfolio uses)
3. Log in via the Agent-Folio UI — it authenticates against Ghostfolio's JWT

**Rotki** (crypto):
1. Run Rotki with the REST API enabled (`docker compose up` from the [Rotki repo](https://github.com/jpwilson/rotki))
2. Go to Settings > Backends in the Agent-Folio UI and add a Rotki connection
3. Enter the Rotki URL, username, and password

**Both**: Connect both backends and Agent-Folio merges data into a single unified view, tagging each holding with its source.

## Architecture

```
Browser (Chat UI)
    |
    v
Agent-Folio (FastAPI, port 8000)
    |--- Guardrails (pre-filter)
    |--- LLM Provider (OpenAI / Anthropic / LiteLLM / LangChain)
    |--- 11 Tools (each calls a backend API)
    |--- Verification (deterministic checks)
    |--- Guardrails (post-filter)
    |
    v
Ghostfolio (port 3333)    Rotki (port 8084)
    |                         |
    v                         v
  Postgres + Redis          SQLite
```

All backends implement the `PortfolioProvider` ABC (`services/providers/base.py`), so tools work identically regardless of data source. Adding a new backend means implementing one Python class — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Tools

| Tool | Description |
|------|-------------|
| `portfolio_summary` | Holdings, allocations, total value |
| `market_data` | Stock/ETF/crypto lookup and quotes |
| `transaction_history` | Buy/sell activity log |
| `risk_assessment` | Diversification and concentration analysis |
| `tax_estimate` | Unrealized gains, cost basis, estimated liability |
| `portfolio_performance` | Returns over configurable time periods |
| `dividend_history` | Dividend income by month/quarter/year |
| `portfolio_report` | X-Ray health check (Ghostfolio's rule engine) |
| `investment_timeline` | Monthly/yearly investment amounts and streaks |
| `account_overview` | Account balances across platforms |
| `stock_history` | Historical price data for individual symbols |

## Verification

Every response is checked by deterministic verification (no LLM-as-judge):

| Check | What It Validates |
|-------|-------------------|
| `allocation_sum` | Portfolio percentages sum to ~100% |
| `valid_market_prices` | All holdings have prices > 0 |
| `tax_data_consistency` | Cost basis and current values are positive |
| `no_hallucinated_symbols` | All mentioned tickers exist in the user's portfolio |
| `performance_data_valid` | Performance metrics are present and numeric |
| `dividend_data_valid` | Dividend totals are non-negative |
| `report_structure_valid` | X-Ray report has expected categories |
| `account_data_valid` | Account records exist |
| `timeline_data_valid` | Timeline has data points |
| Confidence score | Weighted 0-100 composite of tool success, check pass rate, response quality, and data backing |

## Eval System

75 test cases across 5 categories:

| Category | Count | Examples |
|----------|-------|---------|
| Happy path | 22 | "What does my portfolio look like?" |
| Tool selection | 8 | "What's my net worth?" (should pick performance, not summary) |
| Edge cases | 10 | Empty input, off-topic, mixed queries |
| Adversarial | 30 | Jailbreak, prompt injection, credential extraction, emotional manipulation |
| Multi-step | 5 | "Full financial checkup: holdings, risk, taxes, and health warnings" |

Run evals from the Admin panel or CLI:

```bash
# Generate snapshots (hits live agent — costs LLM tokens)
curl -X POST http://localhost:8000/api/v1/agent/admin/eval/snapshot \
  -H "Authorization: Bearer YOUR_JWT"

# Run deterministic checks (instant, free)
curl -X POST http://localhost:8000/api/v1/agent/admin/eval/check
```

See [EVAL_RESULTS.md](EVAL_RESULTS.md) for detailed results.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `JWT_SECRET` | Yes | JWT secret (must match Ghostfolio) |
| `GHOSTFOLIO_URL` | Yes | Ghostfolio API URL |
| `OPENAI_API_KEY` | One of these | OpenAI API key |
| `ANTHROPIC_API_KEY` | One of these | Anthropic API key |
| `OPENROUTER_API_KEY` | One of these | OpenRouter API key (access 100+ models) |
| `DEFAULT_SDK` | No | SDK adapter: `litellm`, `openai`, `anthropic`, `langchain` (default: `litellm`) |
| `DEFAULT_MODEL` | No | Model ID (default: `gpt-4o-mini`) |
| `LANGFUSE_PUBLIC_KEY` | No | Langfuse observability (tracing, cost tracking) |
| `LANGFUSE_SECRET_KEY` | No | Langfuse secret key |
| `LANGFUSE_HOST` | No | Langfuse host URL |

See [.env.example](.env.example) for the full template.

## Admin Panel

Click the gear icon in the chat UI:

- **SDK/Provider** — Switch LLM backend and model in real-time, configure API keys
- **Overview** — System stats, conversation count, backend health
- **Evaluations** — Run eval suite, view results, check user feedback
- **Analytics** — Langfuse tracing data (latency distribution, success rate, recent traces)
- **Cost Analysis** — Development spend breakdown and production cost projections at 100/1K/10K/100K users

## Project Structure

```
agent-folio/
  main.py                          # FastAPI entry point + static file serving
  config.py                        # Environment variable loading
  auth.py                          # JWT authentication
  services/
    agent_service.py               # Chat orchestration (guardrails -> LLM -> tools -> verify)
    guardrails.py                  # Pre/post input/output filtering
    verification.py                # Deterministic verification checks
    db.py                          # PostgreSQL persistence layer
    ghostfolio_client.py           # Ghostfolio HTTP client
    providers/
      base.py                      # PortfolioProvider ABC
      factory.py                   # Provider factory
      rotki_client.py              # Rotki HTTP client
      combined.py                  # Multi-backend data merger
  tools/                           # 11 AI agent tools
  sdks/                            # LLM adapter layer (LiteLLM, OpenAI, Anthropic, LangChain)
  routers/                         # API route handlers
  eval/                            # Golden test cases + eval runner
  static/                          # Chat UI (single-page HTML)
  seed-data/                       # Sample portfolio data for testing imports
  tests/                           # Test suite
```

## Tech Stack

- **Python 3.12** + **FastAPI** + **uvicorn** — async API server
- **httpx** — async HTTP client for backend API calls
- **asyncpg** — async PostgreSQL driver
- **LiteLLM** — unified interface to 100+ LLM providers
- **Langfuse** — observability (tracing, cost tracking)
- **Docker** — containerized deployment

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — System design, component details, request flow, security model
- [CONTRIBUTING.md](CONTRIBUTING.md) — Dev setup, how to add a new backend provider, PR guidelines
- [SECURITY.md](SECURITY.md) — Jailbreak prevention, guardrails, prompt injection defenses
- [EVAL_RESULTS.md](EVAL_RESULTS.md) — Evaluation results and analysis
- [TESTING.md](TESTING.md) — Test suite guide

## License

[MIT](LICENSE)
