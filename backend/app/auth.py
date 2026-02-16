import jwt
import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import get_settings

security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)

_jwks_cache: dict | None = None


async def _ensure_jwks():
    global _jwks_cache
    if _jwks_cache is not None:
        return

    settings = get_settings()
    if not settings.CLERK_JWKS_URL:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="CLERK_JWKS_URL not configured",
        )

    async with httpx.AsyncClient() as client:
        res = await client.get(settings.CLERK_JWKS_URL)
        res.raise_for_status()
        _jwks_cache = res.json()


def _decode_token(token: str) -> dict:
    """Synchronous JWT decode — _ensure_jwks() must be awaited before calling."""
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
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token key ID",
            )

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
    payload = _decode_token(credentials.credentials)
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
        return payload.get("sub")
    except HTTPException:
        return None
