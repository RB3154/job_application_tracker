from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from database import engine
from image_utils import PROFILE_PICS_DIR
from routers import applications, companies, jobs, pages, users
from routers.pages import templates


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Release async database connections on shutdown.

    Tables are not created here: Alembic migrations (`alembic upgrade head`) own the schema.
    """

    yield
    await engine.dispose()


app = FastAPI(lifespan=lifespan)

app.include_router(companies.router, prefix="/api/companies", tags=["companies"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(applications.router, prefix="/api/applications", tags=["applications"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(pages.router)

# CSS, JavaScript and icons used by the HTML pages.
app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve uploaded files, so /media/profile_pics/<file>.jpg opens the picture.
# StaticFiles needs the folder to exist when the app starts.
PROFILE_PICS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory="media"), name="media")


def wants_json(request: Request) -> bool:
    """API calls get JSON errors; pages opened in the browser get the HTML error page."""

    return request.url.path.startswith(("/api", "/media", "/static"))


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
                content={"detail": exception.errors()},
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
