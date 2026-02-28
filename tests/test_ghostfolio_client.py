"""Unit tests for services/ghostfolio_client.py — constructor and header setup."""

from services.ghostfolio_client import GhostfolioClient


class TestGhostfolioClientInit:
    def test_sets_base_url(self):
        client = GhostfolioClient("test-token")
        assert client.base_url is not None
        assert isinstance(client.base_url, str)

    def test_sets_auth_header(self):
        client = GhostfolioClient("my-jwt-token")
        assert client.headers["Authorization"] == "Bearer my-jwt-token"

    def test_sets_content_type(self):
        client = GhostfolioClient("tok")
        assert client.headers["Content-Type"] == "application/json"

    def test_different_tokens(self):
        c1 = GhostfolioClient("token-a")
        c2 = GhostfolioClient("token-b")
        assert c1.headers["Authorization"] != c2.headers["Authorization"]
