"""Unit tests for services/ghostfolio_client.py — constructor and header setup."""

from services.ghostfolio_client import GhostfolioClient


class TestGhostfolioClientInit:
    def test_sets_base_url(self):
        client = GhostfolioClient("http://localhost:3333", "test-token")
        assert client.base_url == "http://localhost:3333"

    def test_sets_auth_header(self):
        client = GhostfolioClient("http://localhost:3333", "my-jwt-token")
        assert client.headers["Authorization"] == "Bearer my-jwt-token"

    def test_sets_content_type(self):
        client = GhostfolioClient("http://localhost:3333", "tok")
        assert client.headers["Content-Type"] == "application/json"

    def test_different_tokens(self):
        c1 = GhostfolioClient("http://localhost:3333", "token-a")
        c2 = GhostfolioClient("http://localhost:3333", "token-b")
        assert c1.headers["Authorization"] != c2.headers["Authorization"]

    def test_provider_name(self):
        client = GhostfolioClient("http://localhost:3333", "tok")
        assert client.provider_name == "ghostfolio"
