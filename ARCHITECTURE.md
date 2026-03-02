# Agent-Folio: Architecture Document

## Overview

Agent-Folio is a standalone AI financial assistant that acts as a **sidecar service** to [Ghostfolio](https://ghostfol.io) and [Rotki](https://rotki.com). It provides natural-language portfolio analysis by connecting to one or more backend REST APIs and orchestrating LLM-powered tool calls with deterministic verification.

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
              +-------------+-------------+
              |                           |
     +--------v--------+        +--------v--------+
     |   Ghostfolio    |        |     Rotki       |
     |   (NestJS)      |        |   (Python)      |
     |   Port 3333     |        |   Port 8084     |
     +--------+--------+        +-----------------+
              |
     +--------v--------+
     | Postgres + Redis |
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
- OpenRouter support: bring your own API key to access Gemini, Llama, DeepSeek, and more via LiteLLM's `openrouter/` prefix
- Admin UI for real-time SDK/model switching
- LiteLLM provides unified interface to 100+ models

### 5. Backend Clients
- **Ghostfolio** (`services/ghostfolio_client.py`): Async httpx client calling Ghostfolio's REST API (portfolio details, performance, orders, symbol lookup, dividends, accounts, X-Ray report, investments timeline)
- **Rotki** (`services/providers/rotki_client.py`): Async httpx client calling Rotki's REST API (balances, trades, history)
- **Combined** (`services/providers/combined.py`): Merges data from multiple providers, tagging each holding with `_source`
- All providers implement `PortfolioProvider` ABC (`services/providers/base.py`)

### 6. Tools (`tools/`)
11 tools available to the LLM agent:

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
| `stock_history` | Historical price data for a symbol | `GET /api/v1/symbol/{ds}/{sym}/market-data` |

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
- **`golden_data.yaml`**: 75 test cases (22 happy path, 8 tool selection, 10 edge case, 30 adversarial, 5 multi-step)
- **Snapshot + Check pipeline**: Generate snapshots via live agent API, then run deterministic checks (no LLM calls)
- Admin panel UI for running evals and viewing historical results
- Results persisted to Postgres for regression tracking across deploys

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
- **State**: Conversations, feedback, settings, and eval results stored in PostgreSQL

## Design Decisions

1. **Sidecar over embedded**: Keeps Ghostfolio untouched; Python gives access to better AI tooling
2. **LiteLLM as default SDK**: Unified interface to 100+ models; easy to switch providers without code changes
3. **Deterministic verification**: No LLM-as-judge; checks are fast, reproducible, and free
4. **Confidence scoring**: Weighted composite score gives users transparency into response reliability
5. **Postgres persistence**: Conversations, feedback, and settings stored in the shared Ghostfolio Postgres instance via asyncpg, surviving container redeploys

## Security: Jailbreak Prevention

Agent-Folio implements defense-in-depth against prompt injection and jailbreak attacks:

### Pre-Filter (Input Guardrails)
- **Input length limiting**: Messages capped at 2000 characters to prevent token-stuffing
- **Message role validation**: Only `user` and `assistant` roles accepted from client; `system` role injected server-side only
- **Encoding detection**: Base64, ROT13, and hex-encoded payloads are detected and decoded to check for hidden instructions
- **Delimiter injection detection**: ChatML tokens (`<|im_start|>`, `[INST]`, `<<SYS>>`) and fake system message markers are blocked
- **Unicode normalization**: Homoglyph attacks (Cyrillic/Greek lookalikes, fullwidth chars, zero-width chars) are normalized before pattern matching
- **HTML/Markdown stripping**: HTML tags and potentially dangerous markup removed before processing
- **Expanded manipulation patterns**: Detection of DAN, developer mode, persona overrides, "no restrictions" variants, instruction override attempts, hypothetical framing, payload splitting, emotional manipulation
- **Multilingual injection detection**: Common "ignore instructions" phrases in French, Spanish, German, Italian, Chinese, and Japanese
- **Financial keyword matching**: Off-topic messages redirected back to financial domain

### Post-Filter (Output Guardrails)
- **System prompt leakage detection**: Checks if the LLM reveals its own instructions
- **Credential leakage detection**: Regex patterns catch API keys, JWTs, Bearer tokens in responses
- **Harmful financial advice detection**: Blocks guaranteed returns, insider trading references, market manipulation language
- **Tone/persona violation detection**: Catches pirate language, roleplay compliance, creative writing
- **Off-topic content detection**: Catches recipes, sports, stories, SQL/code execution references
- **Response length anomaly**: Flags responses exceeding 10,000 characters

### Architectural Defenses
- **Sandwich defense**: System prompt reinforcement appended after user messages as a reminder
- **Output token limit**: `max_tokens=2000` prevents excessively long responses
- **Tool call validation**: Only whitelisted tools can be executed; tool arguments are sanitized
- **Deterministic verification**: Every response checked for data integrity (allocation sums, valid prices, no hallucinated symbols)
- **Confidence scoring**: Weighted 0-100 score gives users transparency into response reliability

### Eval Coverage
75 test cases including 30 adversarial cases covering:
- Prompt injection (basic + encoded + multilingual)
- DAN/persona/developer mode variants
- System prompt extraction attempts
- Credential extraction attempts
- Delimiter/token smuggling
- Emotional manipulation
- Payload splitting
- HTML/code injection

### Limitations
- No defense is foolproof — prompt injection is a fundamental LLM architectural challenge
- Multi-turn "crescendo" attacks (gradual topic drift) remain the hardest to defend against
- Defense-in-depth approach makes attacks significantly harder, not impossible
- Regular red-teaming and eval suite runs are essential after model/prompt changes
