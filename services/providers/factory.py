"""Build a PortfolioProvider from a database connection record."""

import httpx

from services.providers.base import PortfolioProvider


async def build_provider(connection: dict) -> PortfolioProvider:
    """Create the right provider instance from a backend connection record.

    Args:
        connection: Dict with keys: provider, base_url, credentials, label, id

    Returns:
        A ready-to-use PortfolioProvider instance.
    """
    provider_type = connection["provider"]
    base_url = connection["base_url"]
    creds = connection.get("credentials", {})

    if provider_type == "ghostfolio":
        return await _build_ghostfolio(base_url, creds)
    elif provider_type == "rotki":
        return await _build_rotki(base_url, creds)
    else:
        raise ValueError(f"Unknown provider type: {provider_type}")


async def _build_ghostfolio(base_url: str, creds: dict) -> PortfolioProvider:
    """Obtain a fresh JWT from the security_token and return a GhostfolioClient."""
    from services.ghostfolio_client import GhostfolioClient

    security_token = creds.get("security_token", "")
    if not security_token:
        raise ValueError("Ghostfolio connection missing security_token in credentials")

    # Exchange security token for JWT
    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.post(
            f"{base_url}/api/v1/auth/anonymous",
            json={"accessToken": security_token},
        )
        res.raise_for_status()
        jwt = res.json().get("authToken", "")

    return GhostfolioClient(base_url, jwt)


async def _build_rotki(base_url: str, creds: dict) -> PortfolioProvider:
    """Create and authenticate a RotkiClient."""
    from services.providers.rotki_client import RotkiClient

    return await RotkiClient.create(base_url, creds)
