from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import models
from auth import CurrentUser
from config import settings
from database import get_db
from routers.helpers import (
    commit_or_raise_conflict,
    ensure_application_job_available,
    get_application_or_404,
    get_job_or_404,
)
from schemas import (
    ApplicationCreate,
    ApplicationReplace,
    ApplicationResponse,
    ApplicationUpdate,
    PaginatedApplicationsResponse,
)


router = APIRouter()


@router.get("", response_model=PaginatedApplicationsResponse)
async def get_applications(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = settings.items_per_page,
):
    count_result = await db.execute(
        select(func.count()).select_from(models.Application).where(models.Application.user_id == current_user.id)
    )
    total = count_result.scalar() or 0

    # Most recent first; application_id breaks ties so applications on the same day keep a fixed order between pages.
    result = await db.execute(
        select(models.Application)
        .where(models.Application.user_id == current_user.id)
        .order_by(models.Application.date_applied.desc(), models.Application.application_id.desc())
        .offset(skip)
        .limit(limit)
    )
    applications = result.scalars().all()

    return PaginatedApplicationsResponse(
        applications=[ApplicationResponse.model_validate(application) for application in applications],
        total=total,
        skip=skip,
        limit=limit,
        has_more=skip + len(applications) < total,
    )


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
