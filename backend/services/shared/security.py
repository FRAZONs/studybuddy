import base64
import hashlib
import hmac
import json
import os
import time
from typing import Annotated

from fastapi import Header, HTTPException


def _secret() -> bytes:
    secret = os.getenv("AUTH_TOKEN_SECRET", "").strip().encode()
    if len(secret) < 32:
        raise HTTPException(503, "Configure AUTH_TOKEN_SECRET with at least 32 characters.")
    return secret


def _encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_token(user: dict) -> str:
    header = _encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _encode(json.dumps({
        "sub": user["id"],
        "username": user["username"],
        "role": user["role"],
        "exp": int(time.time()) + 8 * 60 * 60,
    }, separators=(",", ":")).encode())
    message = f"{header}.{payload}".encode()
    signature = _encode(hmac.new(_secret(), message, hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Sign in to continue.")
    token = authorization[7:].strip()
    try:
        header, payload, signature = token.split(".")
        secret = _secret()
        expected = _encode(hmac.new(secret, f"{header}.{payload}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid signature")
        claims = json.loads(_decode(payload))
        if not isinstance(claims.get("sub"), str) or claims["exp"] <= time.time():
            raise ValueError("Invalid token claims")
        if claims.get("role") not in {"admin", "student"}:
            raise ValueError("Invalid role")
        return {"id": claims["sub"], "username": claims["username"], "role": claims["role"]}
    except HTTPException:
        raise
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise HTTPException(401, "Your session is invalid or expired. Sign in again.") from None


def require_admin(user: dict) -> None:
    if user["role"] != "admin":
        raise HTTPException(403, "Administrator access is required.")
