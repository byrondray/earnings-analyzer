from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request


def _rate_limit_key(request: Request) -> str:
    """Key rate limits by client IP, not by the client-supplied bearer
    token. Keying by the raw token would let a client defeat the limiter
    by sending a new, unverified token value on every request (the token's
    signature isn't checked until the route's own auth dependency runs,
    which happens after rate limiting)."""
    return get_remote_address(request)


limiter = Limiter(key_func=_rate_limit_key)
