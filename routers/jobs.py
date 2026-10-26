from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import models
from auth import CurrentUser
from database import get_db
from routers.helpers import commit_or_raise_conflict, ensure_job_url_available, get_company_or_404, get_job_or_404
from schemas import JobBase, JobCreate, JobResponse, JobUpdate


router = APIRouter()


@router.get("", response_model=list[JobResponse])
async def get_jobs(db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.Job))
    return result.scalars().all()


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(job_data: JobCreate, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    if await db.get(models.Job, job_data.job_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Job ID already exists")
    await get_company_or_404(job_data.company_id, db)
    await ensure_job_url_available(job_data.job_url, db)
    job = models.Job(**job_data.model_dump())
    db.add(job)
    await commit_or_raise_conflict(db)
    await db.refresh(job)
    return job


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, db: Annotated[AsyncSession, Depends(get_db)]):
    return await get_job_or_404(job_id, db)


@router.put("/{job_id}", response_model=JobResponse)
async def replace_job(job_id: str, job_data: JobBase, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
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


@router.patch("/{job_id}", response_model=JobResponse)
async def update_job(job_id: str, job_data: JobUpdate, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    job = await get_job_or_404(job_id, db)
    try:
        job_data.validate_ranges_against(job)
    except ValidationError as exception:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Request conflicts with an existing database constraint") from exception
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


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(job_id: str, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    job = await get_job_or_404(job_id, db)
    dependent_models = (models.Application, models.JobLocation, models.JobWorkMode, models.JobSkill, models.JobEducation, models.JobSource)
    for dependent in dependent_models:
        result = await db.execute(select(dependent.job_id).where(dependent.job_id == job_id))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Job has related records and cannot be deleted")
    await db.delete(job)
    await commit_or_raise_conflict(db)
