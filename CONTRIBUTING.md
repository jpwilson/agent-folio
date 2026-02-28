# Contributing to Agent-Folio

Thanks for your interest in contributing! Agent-Folio is an AI portfolio agent that supports multiple backends (Ghostfolio, Rotki, and more).

## Dev Setup

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/agent-folio.git
cd agent-folio

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your database URL, JWT secret, and LLM API key

# Run (requires at least one backend like Ghostfolio on port 3333)
uvicorn main:app --reload --port 8000

# Run tests
pytest
```

## Project Structure

```
agent-folio/
  main.py                    # FastAPI entry point
  services/
    providers/
      base.py                # PortfolioProvider ABC
      factory.py             # Provider factory
      rotki_client.py        # Rotki implementation
      combined.py            # Multi-backend merger
    ghostfolio_client.py     # Ghostfolio implementation
    agent_service.py         # Chat orchestration
    db.py                    # PostgreSQL layer
  tools/                     # 11 AI agent tools
  routers/                   # API routes
  sdks/                      # LLM provider adapters
  tests/                     # Test suite
```

## Adding a New Backend Provider

1. Create `services/providers/your_provider.py`
2. Extend `PortfolioProvider` from `services/providers/base.py`
3. Implement all required methods — normalize data to match the contract shapes defined in the ABC docstrings
4. Methods your backend can't support should return valid empty structures (e.g., `{"activities": []}`)
5. Register it in `services/providers/factory.py`
6. Add the provider name to the `CHECK` constraint in `db.py` (`agent_backend_connections` table)
7. Add tests in `tests/test_your_provider.py`

## PR Guidelines

- Keep PRs focused — one feature or fix per PR
- Include tests for new functionality
- Run `pytest` and `ruff check .` before submitting
- Update documentation if you change public behavior
- Follow existing code style (ruff-formatted, 120 char line length)

## Code Style

- Python 3.11+
- Formatted with [Ruff](https://docs.astral.sh/ruff/)
- Type hints encouraged
- Async-first (all I/O is async)
