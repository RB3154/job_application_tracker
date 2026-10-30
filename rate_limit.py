"""Rate limiting for routes that attackers like to hammer (login, password reset)."""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


# Counts requests per IP address. The counts live in this process's memory, so they reset when
# the server restarts and aren't shared between several server processes (fine for one server).
limiter = Limiter(key_func=get_remote_address)


async def rate_limit_exceeded_handler(request: Request, exception: RateLimitExceeded) -> JSONResponse:
    """Answer with 429 in the same {"detail": ...} shape as our other errors, so the frontend can show it."""

    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "Too many attempts. Please wait a while and try again."},
    )
