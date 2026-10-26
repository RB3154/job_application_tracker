from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import models


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


async def get_application_or_404(application_id: int, user_id: int, db: AsyncSession) -> models.Application:
    """Return the user's application; 404 if it doesn't exist, 403 if it belongs to another user."""

    application = await db.get(models.Application, application_id)
    if not application:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    if application.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this application")
    return application


async def get_user_or_404(user_id: int, db: AsyncSession) -> models.User:
    user = await db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


async def ensure_job_url_available(job_url: str, db: AsyncSession, current_job_id: str | None = None) -> None:
    result = await db.execute(select(models.Job).where(models.Job.job_url == job_url))
    existing_job = result.scalar_one_or_none()
    if existing_job and existing_job.job_id != current_job_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Job URL already exists")


async def ensure_application_job_available(
    user_id: int, job_id: str, db: AsyncSession, current_application_id: int | None = None
) -> None:
    result = await db.execute(
        select(models.Application).where(models.Application.user_id == user_id, models.Application.job_id == job_id)
    )
    existing_application = result.scalar_one_or_none()
    if existing_application and existing_application.application_id != current_application_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This user has already applied to this job")


async def ensure_username_available(username: str, db: AsyncSession, current_user_id: int | None = None) -> None:
    result = await db.execute(select(models.User).where(func.lower(models.User.username) == username.lower()))
    existing_user = result.scalar_one_or_none()
    if existing_user and existing_user.id != current_user_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")


async def ensure_email_available(email: str, db: AsyncSession, current_user_id: int | None = None) -> None:
    result = await db.execute(select(models.User).where(func.lower(models.User.email) == email.lower()))
    existing_user = result.scalar_one_or_none()
    if existing_user and existing_user.id != current_user_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
