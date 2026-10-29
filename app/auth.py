import os
import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import APIKeyHeader

from app.config import SESSION_SECRET_MIN_LENGTH

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

SESSION_ROLES = {"admin", "demo"}
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def session_secret() -> str:
    secret = os.getenv("SESSION_SECRET", "")
    if len(secret) < SESSION_SECRET_MIN_LENGTH:
        raise RuntimeError(
            f"SESSION_SECRET must be set to at least {SESSION_SECRET_MIN_LENGTH} characters"
        )
    return secret


def session_https_only() -> bool:
    # Only an explicit "false" (plain http in local development) turns Secure off
    return os.getenv("SESSION_HTTPS_ONLY", "true").lower() != "false"


def check_api_key(api_key: str) -> bool:
    expected_key = os.getenv("FIXWRIGHT_API_KEY")
    if not expected_key:
        raise HTTPException(
            status_code=500,
            detail="API key is not configured"
        )
    return secrets.compare_digest(api_key.encode(), expected_key.encode())


def require_web_client(x_fixwright_client: Annotated[str | None, Header()] = None) -> None:
    if x_fixwright_client != "web":
        raise HTTPException(
            status_code=403,
            detail="Missing X-Fixwright-Client header"
        )


def unauthorized() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail="Invalid or missing API key",
        headers={"WWW-Authenticate": "APIKey"}
    )


def require_auth(request: Request, api_key: str | None = Depends(api_key_header)) -> str:
    """Returns the caller's role: "api" (X-API-Key header), "admin" or "demo" (session)."""
    if not os.getenv("FIXWRIGHT_API_KEY"):
        raise HTTPException(
            status_code=500,
            detail="API key is not configured"
        )

    # A key in the header always decides, even when a session cookie is also present
    if api_key is not None:
        if check_api_key(api_key):
            return "api"
        raise unauthorized()

    role = request.session.get("role")
    if role in SESSION_ROLES:
        if request.method not in SAFE_METHODS:
            require_web_client(request.headers.get("x-fixwright-client"))
        return role

    raise unauthorized()