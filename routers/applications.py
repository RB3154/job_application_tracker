from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import models
from database import get_db
from routers.helpers import commit_or_raise_conflict, ensure_application_job_available, get_application_or_404, get_job_or_404
from schemas import ApplicationCreate, ApplicationReplace, ApplicationResponse, ApplicationUpdate


router = APIRouter()


@router.get("", response_model=list[ApplicationResponse])
async def get_applications(db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.Application))
    return result.scalars().all()


@router.post("", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
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


@router.get("/{application_id}", response_model=ApplicationResponse)
async def get_application(application_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    return await get_application_or_404(application_id, db)


@router.put("/{application_id}", response_model=ApplicationResponse)
async def replace_application(application_id: int, application_data: ApplicationReplace, db: Annotated[AsyncSession, Depends(get_db)]):
    application = await get_application_or_404(application_id, db)
    values = application_data.model_dump()
    if "job_id" in values and values["job_id"] != application.job_id:
        await get_job_or_404(values["job_id"], db)
        await ensure_application_job_available(values["job_id"], db, application.application_id)
    for field, value in values.items():
        setattr(application, field, value)
    await commit_or_raise_conflict(db)
    await db.refresh(application)
    return application


@router.patch("/{application_id}", response_model=ApplicationResponse)
async def update_application(application_id: int, application_data: ApplicationUpdate, db: Annotated[AsyncSession, Depends(get_db)]):
    application = await get_application_or_404(application_id, db)
    values = application_data.model_dump(exclude_unset=True)
    if "job_id" in values and values["job_id"] != application.job_id:
        await get_job_or_404(values["job_id"], db)
        await ensure_application_job_available(values["job_id"], db, application.application_id)
    for field, value in values.items():
        setattr(application, field, value)
    await commit_or_raise_conflict(db)
    await db.refresh(application)
    return application


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(application_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    application = await get_application_or_404(application_id, db)
    await db.delete(application)
    await commit_or_raise_conflict(db)
