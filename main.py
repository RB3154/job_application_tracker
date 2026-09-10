from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import ValidationError

import models
from database import Base, engine, get_db
from schemas import (
    ApplicationCreate,
    ApplicationReplace,
    ApplicationResponse,
    ApplicationUpdate,
    CompanyBase,
    CompanyCreate,
    CompanyResponse,
    CompanyUpdate,
    JobBase,
    JobCreate,
    JobResponse,
    JobUpdate,
)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Create the schema on startup and release async connections on shutdown."""

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(lifespan=lifespan)


async def commit_or_raise_conflict(db: AsyncSession) -> None:
    """Commit a change and turn an unexpected database constraint error into a 409."""

    try:
        await db.commit()
    except IntegrityError as exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Request conflicts with an existing database constraint",
        ) from exception


async def get_company_or_404(company_id: str, db: AsyncSession) -> models.Company:
    company = await db.get(models.Company, company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company


async def get_job_or_404(job_id: str, db: AsyncSession) -> models.Job:
    job = await db.get(models.Job, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


async def get_application_or_404(application_id: int, db: AsyncSession) -> models.Application:
    application = await db.get(models.Application, application_id)
    if not application:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return application


async def ensure_job_url_available(job_url: str, db: AsyncSession, current_job_id: str | None = None) -> None:
    result = await db.execute(select(models.Job).where(models.Job.job_url == job_url))
    existing_job = result.scalar_one_or_none()
    if existing_job and existing_job.job_id != current_job_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Job URL already exists")


async def ensure_application_job_available(job_id: str, db: AsyncSession, current_application_id: int | None = None) -> None:
    result = await db.execute(select(models.Application).where(models.Application.job_id == job_id))
    existing_application = result.scalar_one_or_none()
    if existing_application and existing_application.application_id != current_application_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An application already exists for this job")


@app.get("/api/companies", response_model=list[CompanyResponse])
async def get_companies(db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.Company))
    return result.scalars().all()


@app.post("/api/companies", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(company_data: CompanyCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    if await db.get(models.Company, company_data.company_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Company ID already exists")
    company = models.Company(**company_data.model_dump())
    db.add(company)
    await commit_or_raise_conflict(db)
    await db.refresh(company)
    return company


@app.get("/api/companies/{company_id}", response_model=CompanyResponse)
async def get_company(company_id: str, db: Annotated[AsyncSession, Depends(get_db)]):
    return await get_company_or_404(company_id, db)


@app.put("/api/companies/{company_id}", response_model=CompanyResponse)
async def replace_company(company_id: str, company_data: CompanyBase, db: Annotated[AsyncSession, Depends(get_db)]):
    company = await get_company_or_404(company_id, db)
    for field, value in company_data.model_dump().items():
        setattr(company, field, value)
    await commit_or_raise_conflict(db)
    await db.refresh(company)
    return company


@app.patch("/api/companies/{company_id}", response_model=CompanyResponse)
async def update_company(company_id: str, company_data: CompanyUpdate, db: Annotated[AsyncSession, Depends(get_db)]):
    company = await get_company_or_404(company_id, db)
    for field, value in company_data.model_dump(exclude_unset=True).items():
        setattr(company, field, value)
    await commit_or_raise_conflict(db)
    await db.refresh(company)
    return company


@app.delete("/api/companies/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(company_id: str, db: Annotated[AsyncSession, Depends(get_db)]):
    company = await get_company_or_404(company_id, db)
    result = await db.execute(select(models.Job.job_id).where(models.Job.company_id == company_id))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Company has related jobs and cannot be deleted")
    await db.delete(company)
    await commit_or_raise_conflict(db)


@app.get("/api/jobs", response_model=list[JobResponse])
async def get_jobs(db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.Job))
    return result.scalars().all()


@app.post("/api/jobs", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(job_data: JobCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    if await db.get(models.Job, job_data.job_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Job ID already exists")
    await get_company_or_404(job_data.company_id, db)
    await ensure_job_url_available(job_data.job_url, db)
    job = models.Job(**job_data.model_dump())
    db.add(job)
    await commit_or_raise_conflict(db)
    await db.refresh(job)
    return job


@app.get("/api/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, db: Annotated[AsyncSession, Depends(get_db)]):
    return await get_job_or_404(job_id, db)


@app.put("/api/jobs/{job_id}", response_model=JobResponse)
async def replace_job(
    job_id: str,
    job_data: JobBase,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    job = await get_job_or_404(job_id, db)

    values = job_data.model_dump()

    if "company_id" in values and values["company_id"] != job.company_id:
        await get_company_or_404(values["company_id"], db)

    if "job_url" in values and values["job_url"] != job.job_url:
        await ensure_job_url_available(values["job_url"], db, job.job_id)

    for field, value in values.items():
        setattr(job, field, value)

    await commit_or_raise_conflict(db)
    await db.refresh(job)

    return job


@app.patch("/api/jobs/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: str,
    job_data: JobUpdate,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    job = await get_job_or_404(job_id, db)

    try:
        job_data.validate_ranges_against(job)
    except ValidationError as exception:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Request conflicts with an existing database constraint",
        ) from exception

    values = job_data.model_dump(exclude_unset=True)

    if "company_id" in values and values["company_id"] != job.company_id:
        await get_company_or_404(values["company_id"], db)

    if "job_url" in values and values["job_url"] != job.job_url:
        await ensure_job_url_available(values["job_url"], db, job.job_id)

    for field, value in values.items():
        setattr(job, field, value)

    await commit_or_raise_conflict(db)
    await db.refresh(job)

    return job


@app.delete("/api/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(job_id: str, db: Annotated[AsyncSession, Depends(get_db)]):
    job = await get_job_or_404(job_id, db)
    dependent_models = (models.Application, models.JobLocation, models.JobWorkMode, models.JobSkill, models.JobEducation, models.JobSource)
    for dependent in dependent_models:
        result = await db.execute(select(dependent.job_id).where(dependent.job_id == job_id))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Job has related records and cannot be deleted")
    await db.delete(job)
    await commit_or_raise_conflict(db)


@app.get("/api/applications", response_model=list[ApplicationResponse])
async def get_applications(db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.Application))
    return result.scalars().all()


@app.post("/api/applications", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_application(application_data: ApplicationCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    if await db.get(models.Application, application_data.application_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Application ID already exists")
    await get_job_or_404(application_data.job_id, db)
    await ensure_application_job_available(application_data.job_id, db)
    application = models.Application(**application_data.model_dump(exclude_unset=True))
    db.add(application)
    await commit_or_raise_conflict(db)
    await db.refresh(application)
    return application


@app.get("/api/applications/{application_id}", response_model=ApplicationResponse)
async def get_application(application_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    return await get_application_or_404(application_id, db)


@app.put("/api/applications/{application_id}", response_model=ApplicationResponse)
async def replace_application(
    application_id: int,
    application_data: ApplicationReplace,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    application = await get_application_or_404(application_id, db)

    values = application_data.model_dump()

    if "job_id" in values and values["job_id"] != application.job_id:
        await get_job_or_404(values["job_id"], db)
        await ensure_application_job_available(
            values["job_id"],
            db,
            application.application_id
        )

    for field, value in values.items():
        setattr(application, field, value)

    await commit_or_raise_conflict(db)
    await db.refresh(application)

    return application


@app.patch("/api/applications/{application_id}", response_model=ApplicationResponse)
async def update_application(
    application_id: int,
    application_data: ApplicationUpdate,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    application = await get_application_or_404(application_id, db)

    values = application_data.model_dump(exclude_unset=True)

    if "job_id" in values and values["job_id"] != application.job_id:
        await get_job_or_404(values["job_id"], db)
        await ensure_application_job_available(
            values["job_id"],
            db,
            application.application_id
        )

    for field, value in values.items():
        setattr(application, field, value)

    await commit_or_raise_conflict(db)
    await db.refresh(application)

    return application


@app.delete("/api/applications/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(application_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    application = await get_application_or_404(application_id, db)
    await db.delete(application)
    await commit_or_raise_conflict(db)


@app.exception_handler(StarletteHTTPException)
async def general_http_exception_handler(request: Request, exception: StarletteHTTPException):
    message = exception.detail if exception.detail else "Error occurred. Check the request and try again."

    if request.url.path.startswith("/api"):
        return JSONResponse(
            status_code=exception.status_code,
            content={"detail": message},
        )


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exception: RequestValidationError):
    if request.url.path.startswith("/api"):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": exception.errors()},
        )
