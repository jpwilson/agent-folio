import jwt
from fastapi import HTTPException, Request


def get_user_id(request: Request) -> str:
    """Extract user ID from JWT Bearer token (unverified decode).

    We don't verify the JWT signature here — Ghostfolio does that when
    we forward the token. We just need the user ID for conversation
    namespacing.
    """
    token = _extract_token(request)
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        user_id = payload.get("id") or payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: no user ID")
        return user_id
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_raw_token(request: Request) -> str:
    """Extract raw JWT token to forward to Ghostfolio API."""
    return _extract_token(request)


def _extract_token(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    return auth_header[7:]
