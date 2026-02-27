# Agent-Folio: Architecture Document

## Overview

Agent-Folio is a standalone AI financial assistant that acts as a **sidecar service** to [Ghostfolio](https://ghostfol.io), an open-source wealth management application. It provides natural-language portfolio analysis by connecting to Ghostfolio's REST API and orchestrating LLM-powered tool calls.

## System Architecture

```
                    +-----------------+
                    |   User Browser  |
                    |  (Chat UI/HTML) |
                    +--------+--------+
                             |
                    HTTPS (JWT Auth)
                             |
                    +--------v--------+
                    |   Agent-Folio   |
                    |   (FastAPI)     |
                    |   Port 8000     |
                    +--------+--------+
                             |
                   HTTP (Bearer Token)
                             |
                    +--------v--------+
                    |   Ghostfolio    |
                    |   (NestJS)      |
                    |   Port 3333     |
                    +--------+--------+
                             |
                    +--------v--------+
                    | Postgres + Redis|
                    +-----------------+
```

## Components

### 1. FastAPI Application (`main.py`)
- Entry point serving REST API and static chat UI
- CORS-enabled for cross-origin browser access
- Routes: `/api/v1/agent/*` (chat, conversations, feedback, admin)

### 2. Authentication (`auth.py`)
- Validates JWT tokens from Ghostfolio
- Extracts user ID from token payload
- Forwards Bearer token to Ghostfolio API calls

### 3. Agent Service (`services/agent_service.py`)
- Core orchestration: receives user message, runs guardrails, calls LLM, executes tools, verifies output
- Conversation persistence (JSON files)
- System prompt with strict financial-domain rules

### 4. SDK Registry (`services/sdk_registry.py`, `sdks/`)
- Switchable LLM backends: LiteLLM (default), OpenAI, Anthropic, LangChain
- Admin UI for real-time SDK/model switching
- LiteLLM provides unified interface to 100+ models

### 5. Ghostfolio HTTP Client (`services/ghostfolio_client.py`)
- Async HTTP client (httpx) calling Ghostfolio's REST API
- Endpoints: portfolio details, performance, orders, symbol lookup, dividends, accounts, X-Ray report, investments timeline

### 6. Tools (`tools/`)
10 tools available to the LLM agent:

| Tool | Purpose | Ghostfolio Endpoint |
|------|---------|-------------------|
| `portfolio_summary` | Holdings, allocations, total value | `GET /api/v1/portfolio/details` |
| `market_data` | Stock/ETF lookup and quotes | `GET /api/v1/symbol/lookup` + `/symbol/{ds}/{sym}` |
| `transaction_history` | Buy/sell activity log | `GET /api/v1/order` |
| `risk_assessment` | Diversification analysis | `GET /api/v1/portfolio/details` (computed) |
| `tax_estimate` | Unrealized gains, cost basis | `GET /api/v1/portfolio/details` (computed) |
| `portfolio_performance` | Returns over time periods | `GET /api/v2/portfolio/performance` |
| `dividend_history` | Dividend income by period | `GET /api/v1/portfolio/dividends` |
| `portfolio_report` | X-Ray health check rules | `GET /api/v1/portfolio/report` |
| `investment_timeline` | Monthly/yearly investment amounts | `GET /api/v1/portfolio/investments` |
| `account_overview` | Account balances and platforms | `GET /api/v1/account` |

### 7. Guardrails (`services/guardrails.py`)
- **Pre-filter**: Keyword-based topic detection (financial domain only)
- **Post-filter**: Checks LLM output for tone violations (pirate speak, persona leakage, creative writing)
- Automatic redirect response for off-topic or manipulated outputs

### 8. Verification (`services/verification.py`)
Deterministic checks run after every response:

| Check | Type | Description |
|-------|------|-------------|
| `allocation_sum` | Data integrity | Portfolio percentages sum to ~100% |
| `valid_market_prices` | Data integrity | All holdings have prices > 0 |
| `tax_data_consistency` | Data integrity | Cost basis and values are positive |
| `no_hallucinated_symbols` | Hallucination detection | All mentioned tickers exist in portfolio |
| `performance_data_valid` | Output validation | Performance metrics are present |
| `dividend_data_valid` | Output validation | Dividend totals are non-negative |
| `report_structure_valid` | Output validation | X-Ray has categories |
| `account_data_valid` | Output validation | Accounts exist |
| `timeline_data_valid` | Output validation | Timeline has data points |
| Confidence scoring | Quality metric | Weighted score (0-100) from tool success, check pass rate, response quality, data backing |

### 9. Eval System (`eval/`)
- **`golden_data.yaml`**: 55 test cases (22 happy path, 8 tool selection, 10 edge case, 10 adversarial, 5 multi-step)
- **`eval_snapshot.py`**: Generates snapshots by hitting the live agent API
- **`eval_check.py`**: Deterministic checker (no LLM calls) with regression detection
- **`history/`**: Timestamped eval results for tracking quality over time

### 10. Observability
- **Langfuse** integration via LiteLLM callback (automatic tracing of all LLM calls)
- Admin panel tabs: Analytics (latency, usage, traces from Langfuse), Cost Analysis (dev spend, production projections)
- User feedback (thumbs up/down) persisted as JSONL

## Request Flow

```
User Message
    |
    v
Pre-filter (guardrails) --> [blocked] --> redirect response
    |
    v [passed]
LLM Call (via SDK adapter)
    |
    v
Tool Calls (0-N iterations)
    |   - LLM decides which tools to call
    |   - Each tool calls Ghostfolio API
    |   - Results fed back to LLM
    v
Post-filter (tone check) --> [failed] --> corrected response
    |
    v [passed]
Verification (deterministic checks + confidence score)
    |
    v
Response to User (with verification metadata)
```

## Deployment

- **Railway**: Both Ghostfolio and Agent-Folio run as separate services
- **Private networking**: Agent-Folio calls Ghostfolio via Railway's internal network
- **Environment**: Python 3.12, FastAPI, uvicorn
- **State**: Conversations and feedback stored as JSON/JSONL files

## Design Decisions

1. **Sidecar over embedded**: Keeps Ghostfolio untouched; Python gives access to better AI tooling
2. **LiteLLM as default SDK**: Unified interface to 100+ models; easy to switch providers without code changes
3. **Deterministic verification**: No LLM-as-judge; checks are fast, reproducible, and free
4. **Confidence scoring**: Weighted composite score gives users transparency into response reliability
5. **File-based persistence**: Simple, no additional database needed for MVP
