from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request


def _rate_limit_key(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        return f"token:{auth[7:][:40]}"
    return get_remote_address(request)


limiter = Limiter(key_func=_rate_limit_key)
