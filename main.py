from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

import models
from database import Base, engine
from routers import applications, companies, jobs


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Create the schema on startup and release async connections on shutdown."""

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(lifespan=lifespan)

app.include_router(companies.router, prefix="/api/companies", tags=["companies"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(applications.router, prefix="/api/applications", tags=["applications"])


@app.exception_handler(StarletteHTTPException)
async def general_http_exception_handler(request: Request, exception: StarletteHTTPException):
    message = exception.detail if exception.detail else "Error occurred. Check the request and try again."

    return JSONResponse(
            status_code=exception.status_code,
            content={"detail": message},
        )


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exception: RequestValidationError):
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": exception.errors()},
        )
