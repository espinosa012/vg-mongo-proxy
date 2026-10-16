from __future__ import annotations

import secrets
from typing import Optional

from fastapi import Header, HTTPException, status

from vg_mongo_proxy.config import get_settings


async def verify_api_key(
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
) -> str:
    """Verify that the x-api-key header matches the configured PROXY_API_KEY."""
    settings = get_settings()
    expected_key = settings.proxy_api_key

    # If no key is set or empty in settings, reject for security
    if not expected_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server API key not configured.",
        )

    if not x_api_key or not secrets.compare_digest(x_api_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key in 'x-api-key' header.",
        )

    return x_api_key


async def get_custom_mongo_uri(
    x_mongo_uri: Optional[str] = Header(None, alias="x-mongo-uri"),
) -> Optional[str]:
    """Optional header to override target MongoDB connection string."""
    return x_mongo_uri
