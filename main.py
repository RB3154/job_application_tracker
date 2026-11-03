from contextlib import asynccontextmanager
from typing import Annotated
from urllib.parse import quote

import sentry_sdk
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.exceptions import HTTPException as StarletteHTTPException

from auth import LoginRequired
from config import settings
from database import engine, get_db
from rate_limit import limiter, rate_limit_exceeded_handler
from routers import applications, companies, jobs, lookups, pages, users
from routers.pages import templates


# Error alerts. Only on when SENTRY_DSN is set, so it stays off on laptops, in tests and in CI.
# Sends errors only (no performance tracing) and no personal data such as emails or IPs.
if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn.get_secret_value(),
        environment=settings.sentry_environment,
        send_default_pii=False,
        traces_sample_rate=0,
    )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

app.include_router(companies.router, prefix="/api/companies", tags=["companies"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(applications.router, prefix="/api/applications", tags=["applications"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(lookups.locations_router, prefix="/api/locations", tags=["lookup lists"])
app.include_router(lookups.work_modes_router, prefix="/api/work-modes", tags=["lookup lists"])
app.include_router(lookups.skills_router, prefix="/api/skills", tags=["lookup lists"])
app.include_router(lookups.education_router, prefix="/api/education", tags=["lookup lists"])
app.include_router(lookups.sources_router, prefix="/api/sources", tags=["lookup lists"])
app.include_router(pages.router)

app.mount("/static", StaticFiles(directory="static"), name="static")


class LimitRequestSize:
    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        detail = "Request is too large"
        content_length = dict(scope["headers"]).get(b"content-length", b"0")
        if content_length.isdigit() and int(content_length) > self.max_bytes:
            response = JSONResponse({"detail": detail}, status_code=status.HTTP_413_CONTENT_TOO_LARGE)
            await response(scope, receive, send)
            return

        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=detail)
            return message

        await self.app(scope, limited_receive, send)


app.add_middleware(LimitRequestSize, max_bytes=settings.max_upload_size_bytes + 1024 * 1024)


@app.middleware("http")
async def add_response_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache" if request.url.path.startswith("/static") else "no-store"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-Content-Type-Options"] = "nosniff"
    if "Referrer-Policy" not in response.headers:
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.get("/health", include_in_schema=False)
async def health_check(db: Annotated[AsyncSession, Depends(get_db)]):
    try:
        await db.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError) as exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable"
        ) from exception
    return {"status": "healthy"}


def wants_json(request: Request) -> bool:
    return request.url.path.startswith(("/api", "/static", "/health"))


@app.exception_handler(LoginRequired)
async def login_required_handler(_request: Request, exception: LoginRequired):
    return RedirectResponse(f"/login?next={quote(exception.next_url, safe='')}", status_code=status.HTTP_303_SEE_OTHER)


@app.exception_handler(StarletteHTTPException)
async def general_http_exception_handler(request: Request, exception: StarletteHTTPException):
    message = exception.detail if exception.detail else "Error occurred. Check the request and try again."

    if wants_json(request):
        return JSONResponse(
            status_code=exception.status_code,
            content={"detail": message},
            headers=exception.headers,
        )

    return templates.TemplateResponse(
        request,
        "error.html",
        {"title": f"{exception.status_code} Error", "status_code": exception.status_code, "message": message},
        status_code=exception.status_code,
    )


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exception: RequestValidationError):
    if wants_json(request):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": jsonable_encoder(exception.errors())},
        )

    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "title": "Invalid request",
            "status_code": status.HTTP_422_UNPROCESSABLE_CONTENT,
            "message": "Invalid request. Check the address and try again.",
        },
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
    )
