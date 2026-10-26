from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import models
from auth import CurrentUser
from database import get_db
from routers.helpers import (
    commit_or_raise_conflict,
    ensure_application_job_available,
    get_application_or_404,
    get_job_or_404,
)
from schemas import ApplicationCreate, ApplicationReplace, ApplicationResponse, ApplicationUpdate


router = APIRouter()


@router.get("", response_model=list[ApplicationResponse])
async def get_applications(current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.Application).where(models.Application.user_id == current_user.id))
    return result.scalars().all()


@router.post("", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_application(
    application_data: ApplicationCreate, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]
):
    await get_job_or_404(application_data.job_id, db)
    await ensure_application_job_available(current_user.id, application_data.job_id, db)
    application = models.Application(**application_data.model_dump(exclude_unset=True), user_id=current_user.id)
    db.add(application)
    await commit_or_raise_conflict(db)
    await db.refresh(application)
    return application


@router.get("/{application_id}", response_model=ApplicationResponse)
async def get_application(application_id: int, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    return await get_application_or_404(application_id, current_user.id, db)


@router.put("/{application_id}", response_model=ApplicationResponse)
async def replace_application(
    application_id: int,
    application_data: ApplicationReplace,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    application = await get_application_or_404(application_id, current_user.id, db)
    values = application_data.model_dump()
    if "job_id" in values and values["job_id"] != application.job_id:
        await get_job_or_404(values["job_id"], db)
        await ensure_application_job_available(current_user.id, values["job_id"], db, application.application_id)
    for field, value in values.items():
        setattr(application, field, value)
    await commit_or_raise_conflict(db)
    await db.refresh(application)
    return application


@router.patch("/{application_id}", response_model=ApplicationResponse)
async def update_application(
    application_id: int,
    application_data: ApplicationUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    application = await get_application_or_404(application_id, current_user.id, db)
    values = application_data.model_dump(exclude_unset=True)
    if "job_id" in values and values["job_id"] != application.job_id:
        await get_job_or_404(values["job_id"], db)
        await ensure_application_job_available(current_user.id, values["job_id"], db, application.application_id)
    for field, value in values.items():
        setattr(application, field, value)
    await commit_or_raise_conflict(db)
    await db.refresh(application)
    return application


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(application_id: int, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    application = await get_application_or_404(application_id, current_user.id, db)
    await db.delete(application)
    await commit_or_raise_conflict(db)
