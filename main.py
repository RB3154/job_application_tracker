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
from image_utils import PROFILE_PICS_DIR
from rate_limit import limiter, rate_limit_exceeded_handler
from routers import applications, companies, jobs, lookups, pages, users
from routers.pages import templates


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Release async database connections on shutdown.

    Tables are not created here: Alembic migrations (`alembic upgrade head`) own the schema.
    """

    yield
    await engine.dispose()


app = FastAPI(lifespan=lifespan)

# slowapi finds the limiter on app.state; the handler turns "too many requests" into a 429 JSON error.
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

# CSS, JavaScript and icons used by the HTML pages.
app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve uploaded files, so /media/profile_pics/<file>.jpg opens the picture.
# StaticFiles needs the folder to exist when the app starts.
PROFILE_PICS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory="media"), name="media")


@app.middleware("http")
async def revalidate_static_files(request: Request, call_next):
    """Make the browser check for a newer CSS/JS file on every page load.

    Without this, browsers may keep using an old copy after a file changes. If the file hasn't
    changed, the server answers with a tiny "304 Not Modified", so this stays fast.
    """

    response = await call_next(request)
    if request.url.path.startswith("/static"):
        response.headers["Cache-Control"] = "no-cache"
    return response


def wants_json(request: Request) -> bool:
    """API calls get JSON errors; pages opened in the browser get the HTML error page."""

    return request.url.path.startswith(("/api", "/media", "/static"))


@app.exception_handler(LoginRequired)
async def login_required_handler(_request: Request, exception: LoginRequired):
    """A page that needs login was opened while logged out: go to the login page, then come back."""

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
        # jsonable_encoder turns the ValueError objects inside some errors into text; plain JSON can't handle them.
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
