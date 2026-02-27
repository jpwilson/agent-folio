"""Integration tests for API endpoints using httpx AsyncClient."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from main import app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def client():
    """Async HTTP client wired to the FastAPI app (no real server needed)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# GET /api/v1/agent/config
# ---------------------------------------------------------------------------


class TestGetConfig:
    """The config endpoint is public (no auth required)."""

    @pytest.mark.asyncio
    async def test_config_returns_200(self, client):
        response = await client.get("/api/v1/agent/config")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_config_has_ghostfolio_url(self, client):
        response = await client.get("/api/v1/agent/config")
        data = response.json()
        assert "ghostfolioUrl" in data


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------


class TestHealth:
    """Health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, client):
        response = await client.get("/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_health_returns_ok(self, client):
        response = await client.get("/health")
        data = response.json()
        assert data["status"] == "ok"


# ---------------------------------------------------------------------------
# POST /api/v1/agent/chat without auth
# ---------------------------------------------------------------------------


class TestChatAuth:
    """The chat endpoint requires a Bearer token."""

    @pytest.mark.asyncio
    async def test_chat_without_auth_returns_401(self, client):
        response = await client.post(
            "/api/v1/agent/chat",
            json={"messages": [{"role": "user", "content": "hello"}]},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_chat_with_empty_auth_returns_401(self, client):
        response = await client.post(
            "/api/v1/agent/chat",
            json={"messages": [{"role": "user", "content": "hello"}]},
            headers={"Authorization": ""},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_chat_with_bad_token_returns_401(self, client):
        response = await client.post(
            "/api/v1/agent/chat",
            json={"messages": [{"role": "user", "content": "hello"}]},
            headers={"Authorization": "Bearer not-a-valid-jwt"},
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v1/agent/admin/settings
# ---------------------------------------------------------------------------


class TestAdminSettings:
    """The admin settings endpoint returns SDK and model options."""

    @pytest.mark.asyncio
    async def test_settings_returns_200(self, client):
        response = await client.get("/api/v1/agent/admin/settings")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_settings_has_sdk(self, client):
        response = await client.get("/api/v1/agent/admin/settings")
        data = response.json()
        assert "sdk" in data

    @pytest.mark.asyncio
    async def test_settings_has_model(self, client):
        response = await client.get("/api/v1/agent/admin/settings")
        data = response.json()
        assert "model" in data

    @pytest.mark.asyncio
    async def test_settings_has_sdk_options(self, client):
        response = await client.get("/api/v1/agent/admin/settings")
        data = response.json()
        assert "sdkOptions" in data
        assert isinstance(data["sdkOptions"], list)
        assert len(data["sdkOptions"]) > 0

    @pytest.mark.asyncio
    async def test_settings_has_model_options(self, client):
        response = await client.get("/api/v1/agent/admin/settings")
        data = response.json()
        assert "modelOptions" in data
        assert isinstance(data["modelOptions"], list)
        assert len(data["modelOptions"]) > 0

    @pytest.mark.asyncio
    async def test_settings_sdk_options_have_id_and_name(self, client):
        response = await client.get("/api/v1/agent/admin/settings")
        data = response.json()
        for option in data["sdkOptions"]:
            assert "id" in option
            assert "name" in option

    @pytest.mark.asyncio
    async def test_settings_model_options_have_id_and_name(self, client):
        response = await client.get("/api/v1/agent/admin/settings")
        data = response.json()
        for option in data["modelOptions"]:
            assert "id" in option
            assert "name" in option


# ---------------------------------------------------------------------------
# GET /api/v1/agent/conversations (requires auth)
# ---------------------------------------------------------------------------


class TestConversationsAuth:
    """Conversations endpoint requires authentication."""

    @pytest.mark.asyncio
    async def test_conversations_without_auth_returns_401(self, client):
        response = await client.get("/api/v1/agent/conversations")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/v1/agent/auth/login (proxied to Ghostfolio)
# ---------------------------------------------------------------------------


class TestLoginEndpoint:
    """Login endpoint proxies to Ghostfolio."""

    @pytest.mark.asyncio
    async def test_login_missing_body_returns_422(self, client):
        response = await client.post("/api/v1/agent/auth/login", json={})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_login_with_invalid_token_format(self, client):
        """Login with a token that Ghostfolio rejects should return 401 or 502."""
        # This will try to reach Ghostfolio which is not running in tests,
        # so we expect a connection error -> 502
        response = await client.post(
            "/api/v1/agent/auth/login",
            json={"securityToken": "invalid-token"},
        )
        # Could be 401 (Ghostfolio rejects) or 502 (can't reach Ghostfolio)
        assert response.status_code in (401, 502)
