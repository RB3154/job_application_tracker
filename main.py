from contextlib import asynccontextmanager
from urllib.parse import quote

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from auth import LoginRequired
from database import engine
from rate_limit import limiter, rate_limit_exceeded_handler
from routers import applications, companies, jobs, lookups, pages, users
from routers.pages import templates


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


@app.middleware("http")
async def revalidate_static_files(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static"):
        response.headers["Cache-Control"] = "no-cache"
    return response


def wants_json(request: Request) -> bool:
    return request.url.path.startswith(("/api", "/static"))


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
