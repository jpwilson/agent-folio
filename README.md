# Agent-Folio

AI-powered financial assistant for [Ghostfolio](https://ghostfol.io) — a standalone sidecar service that provides natural-language portfolio analysis.

## Features

- **10 financial tools**: Portfolio summary, market data, transactions, risk assessment, tax estimates, performance tracking, dividends, X-Ray health check, investment timeline, account overview
- **Switchable LLM backends**: LiteLLM (default, 100+ models), OpenAI, Anthropic, LangChain
- **Guardrails**: Pre/post filtering for topic enforcement, tone control, and prompt injection defense
- **Verification**: Deterministic checks on every response (allocation sums, price validity, hallucination detection, confidence scoring)
- **Eval system**: 55 golden test cases with regression detection
- **Observability**: Langfuse integration for tracing, latency monitoring, and cost analysis
- **User feedback**: Thumbs up/down with optional explanations

## Quick Start

```bash
# Clone and install
cd agent-folio
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Ghostfolio URL, JWT secret, and LLM API key

# Run (requires Ghostfolio running on port 3333)
uvicorn main:app --reload --port 8000
```

Open http://localhost:8000 in your browser.

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full system design.

```
Browser (Chat UI) --> Agent-Folio (FastAPI) --> Ghostfolio (NestJS) --> Postgres + Redis
                           |
                      LLM Provider
                    (OpenAI/Anthropic/etc)
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GHOSTFOLIO_URL` | Ghostfolio API base URL | `http://localhost:3333` |
| `JWT_SECRET_KEY` | JWT secret (same as Ghostfolio) | required |
| `OPENAI_API_KEY` | OpenAI API key | required for OpenAI models |
| `ANTHROPIC_API_KEY` | Anthropic API key | optional |
| `LANGFUSE_PUBLIC_KEY` | Langfuse public key | optional |
| `LANGFUSE_SECRET_KEY` | Langfuse secret key | optional |
| `LANGFUSE_HOST` | Langfuse host URL | optional |

## Running Evals

```bash
# Step 1: Generate snapshots (hits live agent, costs tokens)
AGENT_EVAL_TOKEN=<jwt> python eval/eval_snapshot.py

# Step 2: Run deterministic checks (instant, free)
python eval/eval_check.py
```

55 test cases across 5 categories: happy path (22), tool selection (8), edge cases (10), adversarial (10), multi-step (5).

## Admin Panel

Click the gear icon in the chat UI to access:
- **SDK/Provider**: Switch LLM backend and model in real-time
- **Overview**: System stats and conversation count
- **Display**: Toggle markdown, tool calls, verification display
- **Evaluations**: Run eval suite + view user feedback
- **Analytics**: Langfuse tracing data (latency, usage, traces)
- **Cost Analysis**: AI spend breakdown and production projections

## Tech Stack

- **Python 3.12** + **FastAPI** + **uvicorn**
- **httpx** for async Ghostfolio API calls
- **LiteLLM** for unified LLM access
- **Langfuse** for observability
- **Docker** for deployment

## License

Open source. Built as part of the Gauntlet AgentForge project.
