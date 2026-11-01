from fastapi import Request, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


limiter = Limiter(key_func=get_remote_address)


async def rate_limit_exceeded_handler(request: Request, exception: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "Too many attempts. Please wait a while and try again."},
    )
