import os
import secrets

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(api_key: str | None = Depends(api_key_header)):
    expected_key = os.getenv("FIXWRIGHT_API_KEY")
    if not expected_key:
        raise HTTPException(
            status_code=500,
            detail="API key is not configured"
        )

    if api_key is None or not secrets.compare_digest(api_key.encode(), expected_key.encode()):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "APIKey"}
        )