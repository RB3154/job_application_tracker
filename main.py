from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from pydantic import ValidationError

import models
from database import get_db
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

app = FastAPI()


def commit_or_raise_conflict(db: Session) -> None:
    """Commit a change and turn an unexpected database constraint error into a 409."""

    try:
        db.commit()
    except IntegrityError as exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Request conflicts with an existing database constraint",
        ) from exception


def get_company_or_404(company_id: str, db: Session) -> models.Company:
    company = db.get(models.Company, company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company


def get_job_or_404(job_id: str, db: Session) -> models.Job:
    job = db.get(models.Job, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


def get_application_or_404(application_id: int, db: Session) -> models.Application:
    application = db.get(models.Application, application_id)
    if not application:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return application


def ensure_job_url_available(job_url: str, db: Session, current_job_id: str | None = None) -> None:
    existing_job = db.scalar(select(models.Job).where(models.Job.job_url == job_url))
    if existing_job and existing_job.job_id != current_job_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Job URL already exists")


def ensure_application_job_available(job_id: str, db: Session, current_application_id: int | None = None) -> None:
    existing_application = db.scalar(select(models.Application).where(models.Application.job_id == job_id))
    if existing_application and existing_application.application_id != current_application_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An application already exists for this job")


@app.get("/api/companies", response_model=list[CompanyResponse])
def get_companies(db: Annotated[Session, Depends(get_db)]):
    return db.scalars(select(models.Company)).all()


@app.post("/api/companies", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
def create_company(company_data: CompanyCreate, db: Annotated[Session, Depends(get_db)]):
    if db.get(models.Company, company_data.company_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Company ID already exists")
    company = models.Company(**company_data.model_dump())
    db.add(company)
    commit_or_raise_conflict(db)
    db.refresh(company)
    return company


@app.get("/api/companies/{company_id}", response_model=CompanyResponse)
def get_company(company_id: str, db: Annotated[Session, Depends(get_db)]):
    return get_company_or_404(company_id, db)


@app.put("/api/companies/{company_id}", response_model=CompanyResponse)
def replace_company(company_id: str, company_data: CompanyBase, db: Annotated[Session, Depends(get_db)]):
    company = get_company_or_404(company_id, db)
    for field, value in company_data.model_dump().items():
        setattr(company, field, value)
    commit_or_raise_conflict(db)
    db.refresh(company)
    return company


@app.patch("/api/companies/{company_id}", response_model=CompanyResponse)
def update_company(company_id: str, company_data: CompanyUpdate, db: Annotated[Session, Depends(get_db)]):
    company = get_company_or_404(company_id, db)
    for field, value in company_data.model_dump(exclude_unset=True).items():
        setattr(company, field, value)
    commit_or_raise_conflict(db)
    db.refresh(company)
    return company


@app.delete("/api/companies/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(company_id: str, db: Annotated[Session, Depends(get_db)]):
    company = get_company_or_404(company_id, db)
    if db.scalar(select(models.Job.job_id).where(models.Job.company_id == company_id)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Company has related jobs and cannot be deleted")
    db.delete(company)
    commit_or_raise_conflict(db)


@app.get("/api/jobs", response_model=list[JobResponse])
def get_jobs(db: Annotated[Session, Depends(get_db)]):
    return db.scalars(select(models.Job)).all()


@app.post("/api/jobs", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job(job_data: JobCreate, db: Annotated[Session, Depends(get_db)]):
    if db.get(models.Job, job_data.job_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Job ID already exists")
    get_company_or_404(job_data.company_id, db)
    ensure_job_url_available(job_data.job_url, db)
    job = models.Job(**job_data.model_dump())
    db.add(job)
    commit_or_raise_conflict(db)
    db.refresh(job)
    return job


@app.get("/api/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str, db: Annotated[Session, Depends(get_db)]):
    return get_job_or_404(job_id, db)


@app.put("/api/jobs/{job_id}", response_model=JobResponse)
def replace_job(
    job_id: str,
    job_data: JobBase,
    db: Annotated[Session, Depends(get_db)]
):
    job = get_job_or_404(job_id, db)

    values = job_data.model_dump()

    if "company_id" in values and values["company_id"] != job.company_id:
        get_company_or_404(values["company_id"], db)

    if "job_url" in values and values["job_url"] != job.job_url:
        ensure_job_url_available(values["job_url"], db, job.job_id)

    for field, value in values.items():
        setattr(job, field, value)

    commit_or_raise_conflict(db)
    db.refresh(job)

    return job


@app.patch("/api/jobs/{job_id}", response_model=JobResponse)
def update_job(
    job_id: str,
    job_data: JobUpdate,
    db: Annotated[Session, Depends(get_db)]
):
    job = get_job_or_404(job_id, db)

    try:
        job_data.validate_ranges_against(job)
    except ValidationError as exception:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Request conflicts with an existing database constraint",
        ) from exception

    values = job_data.model_dump(exclude_unset=True)

    if "company_id" in values and values["company_id"] != job.company_id:
        get_company_or_404(values["company_id"], db)

    if "job_url" in values and values["job_url"] != job.job_url:
        ensure_job_url_available(values["job_url"], db, job.job_id)

    for field, value in values.items():
        setattr(job, field, value)

    commit_or_raise_conflict(db)
    db.refresh(job)

    return job


@app.delete("/api/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(job_id: str, db: Annotated[Session, Depends(get_db)]):
    job = get_job_or_404(job_id, db)
    dependent_models = (models.Application, models.JobLocation, models.JobWorkMode, models.JobSkill, models.JobEducation, models.JobSource)
    if any(db.scalar(select(dependent.job_id).where(dependent.job_id == job_id)) for dependent in dependent_models):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Job has related records and cannot be deleted")
    db.delete(job)
    commit_or_raise_conflict(db)


@app.get("/api/applications", response_model=list[ApplicationResponse])
def get_applications(db: Annotated[Session, Depends(get_db)]):
    return db.scalars(select(models.Application)).all()


@app.post("/api/applications", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
def create_application(application_data: ApplicationCreate, db: Annotated[Session, Depends(get_db)]):
    if db.get(models.Application, application_data.application_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Application ID already exists")
    get_job_or_404(application_data.job_id, db)
    ensure_application_job_available(application_data.job_id, db)
    application = models.Application(**application_data.model_dump(exclude_unset=True))
    db.add(application)
    commit_or_raise_conflict(db)
    db.refresh(application)
    return application


@app.get("/api/applications/{application_id}", response_model=ApplicationResponse)
def get_application(application_id: int, db: Annotated[Session, Depends(get_db)]):
    return get_application_or_404(application_id, db)


@app.put("/api/applications/{application_id}", response_model=ApplicationResponse)
def replace_application(
    application_id: int,
    application_data: ApplicationReplace,
    db: Annotated[Session, Depends(get_db)]
):
    application = get_application_or_404(application_id, db)

    values = application_data.model_dump()

    if "job_id" in values and values["job_id"] != application.job_id:
        get_job_or_404(values["job_id"], db)
        ensure_application_job_available(
            values["job_id"],
            db,
            application.application_id
        )

    for field, value in values.items():
        setattr(application, field, value)

    commit_or_raise_conflict(db)
    db.refresh(application)

    return application


@app.patch("/api/applications/{application_id}", response_model=ApplicationResponse)
def update_application(
    application_id: int,
    application_data: ApplicationUpdate,
    db: Annotated[Session, Depends(get_db)]
):
    application = get_application_or_404(application_id, db)

    values = application_data.model_dump(exclude_unset=True)

    if "job_id" in values and values["job_id"] != application.job_id:
        get_job_or_404(values["job_id"], db)
        ensure_application_job_available(
            values["job_id"],
            db,
            application.application_id
        )

    for field, value in values.items():
        setattr(application, field, value)

    commit_or_raise_conflict(db)
    db.refresh(application)

    return application


@app.delete("/api/applications/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(application_id: int, db: Annotated[Session, Depends(get_db)]):
    application = get_application_or_404(application_id, db)
    db.delete(application)
    commit_or_raise_conflict(db)


@app.exception_handler(StarletteHTTPException)
def general_http_exception_handler(request: Request, exception: StarletteHTTPException):
    message = exception.detail if exception.detail else "Error occurred. Check the request and try again."

    if request.url.path.startswith("/api"):
        return JSONResponse(
            status_code=exception.status_code,
            content={"detail": message},
        )


@app.exception_handler(RequestValidationError)
def validation_handler(request: Request, exception: RequestValidationError):
    if request.url.path.startswith("/api"):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": exception.errors()},
        )