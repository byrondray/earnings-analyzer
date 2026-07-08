import asyncio
import time

import jwt
import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import get_settings

security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)

_jwks_cache: dict | None = None
_jwks_fetched_at: float = 0.0
_jwks_lock = asyncio.Lock()
_JWKS_TTL_SECONDS = 3600


async def _ensure_jwks(force: bool = False):
    global _jwks_cache, _jwks_fetched_at

    if not force and _jwks_cache is not None and (time.monotonic() - _jwks_fetched_at) < _JWKS_TTL_SECONDS:
        return

    async with _jwks_lock:
        if not force and _jwks_cache is not None and (time.monotonic() - _jwks_fetched_at) < _JWKS_TTL_SECONDS:
            return

        settings = get_settings()
        if not settings.CLERK_JWKS_URL:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="CLERK_JWKS_URL not configured",
            )

        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(settings.CLERK_JWKS_URL)
            res.raise_for_status()
            _jwks_cache = res.json()
            _jwks_fetched_at = time.monotonic()


class _KidNotFound(Exception):
    pass


def _decode_token(token: str) -> dict:
    if not _jwks_cache:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWKS not loaded",
        )

    try:
        public_keys = {}
        for key_data in _jwks_cache.get("keys", []):
            kid = key_data.get("kid")
            if kid:
                public_keys[kid] = jwt.algorithms.RSAAlgorithm.from_jwk(key_data)

        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        if kid not in public_keys:
            raise _KidNotFound()

        return jwt.decode(
            token,
            key=public_keys[kid],
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    await _ensure_jwks()
    try:
        payload = _decode_token(credentials.credentials)
    except _KidNotFound:
        await _ensure_jwks(force=True)
        try:
            payload = _decode_token(credentials.credentials)
        except _KidNotFound:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: unrecognized key",
            )
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
        )
    return user_id


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_security),
) -> str | None:
    if credentials is None:
        return None
    await _ensure_jwks()
    try:
        payload = _decode_token(credentials.credentials)
    except _KidNotFound:
        await _ensure_jwks(force=True)
        try:
            payload = _decode_token(credentials.credentials)
        except (_KidNotFound, HTTPException):
            return None
    except HTTPException:
        return None
    return payload.get("sub")
