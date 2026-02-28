"""Unit tests for auth.py — JWT extraction and user ID parsing."""

from unittest.mock import MagicMock

import jwt as pyjwt
import pytest
from fastapi import HTTPException

from auth import _extract_token, get_raw_token, get_user_id


def _make_request(auth_header: str | None = None) -> MagicMock:
    """Create a mock Request with the given Authorization header."""
    req = MagicMock()
    if auth_header:
        req.headers = {"Authorization": auth_header}
    else:
        req.headers = {}
    return req


class TestExtractToken:
    def test_valid_bearer_token(self):
        req = _make_request("Bearer abc123")
        assert _extract_token(req) == "abc123"

    def test_missing_auth_header(self):
        req = _make_request()
        with pytest.raises(HTTPException) as exc:
            _extract_token(req)
        assert exc.value.status_code == 401
        assert "Missing Bearer token" in exc.value.detail

    def test_non_bearer_auth(self):
        req = _make_request("Basic abc123")
        with pytest.raises(HTTPException) as exc:
            _extract_token(req)
        assert exc.value.status_code == 401


class TestGetRawToken:
    def test_returns_token(self):
        req = _make_request("Bearer mytoken")
        assert get_raw_token(req) == "mytoken"


class TestGetUserId:
    def test_extracts_id_from_jwt(self):
        token = pyjwt.encode({"id": "user-123"}, "secret", algorithm="HS256")
        req = _make_request(f"Bearer {token}")
        assert get_user_id(req) == "user-123"

    def test_extracts_sub_from_jwt(self):
        token = pyjwt.encode({"sub": "user-456"}, "secret", algorithm="HS256")
        req = _make_request(f"Bearer {token}")
        assert get_user_id(req) == "user-456"

    def test_prefers_id_over_sub(self):
        token = pyjwt.encode({"id": "id-val", "sub": "sub-val"}, "secret", algorithm="HS256")
        req = _make_request(f"Bearer {token}")
        assert get_user_id(req) == "id-val"

    def test_no_user_id_in_token(self):
        token = pyjwt.encode({"role": "admin"}, "secret", algorithm="HS256")
        req = _make_request(f"Bearer {token}")
        with pytest.raises(HTTPException) as exc:
            get_user_id(req)
        assert exc.value.status_code == 401
        assert "no user ID" in exc.value.detail

    def test_invalid_token(self):
        req = _make_request("Bearer not-a-valid-jwt")
        with pytest.raises(HTTPException) as exc:
            get_user_id(req)
        assert exc.value.status_code == 401
        assert "Invalid token" in exc.value.detail
