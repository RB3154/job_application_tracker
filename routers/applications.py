from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
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
    paginate,
    slugify,
    unique_id,
)
from schemas import (
    ApplicationCreate,
    ApplicationReplace,
    ApplicationResponse,
    ApplicationStatus,
    ApplicationUpdate,
    JobBase,
    PaginatedApplicationsResponse,
    QuickApplicationCreate,
    StatusChangeResponse,
)


router = APIRouter()

JOB_DETAIL_FIELDS = {
    "JD",
    "application_deadline",
    "exp_min",
    "exp_max",
    "exp_text",
    "salary_text",
    "salary_min",
    "salary_max",
    "salary_currency",
    "salary_period",
}
COMPANY_DETAIL_FIELDS = {"company_site", "company_description"}


def fill_empty_fields(row, values: dict) -> None:
    for field, value in values.items():
        if getattr(row, field) is None:
            setattr(row, field, value)


async def save_application_changes(
    application: models.Application, values: dict, user_id: int, db: AsyncSession
) -> models.Application:
    if "job_id" in values and values["job_id"] != application.job_id:
        await get_job_or_404(values["job_id"], user_id, db)
        await ensure_application_job_available(user_id, values["job_id"], db, application.application_id)
    old_status = application.current_status
    for field, value in values.items():
        setattr(application, field, value)
    leaving_wishlist = old_status == "Wishlist" and values.get("current_status", "Wishlist") != "Wishlist"
    if leaving_wishlist and "date_applied" not in values:
        application.date_applied = date.today()
    if "current_status" in values and values["current_status"] != old_status:
        db.add(
            models.ApplicationStatusChange(
                application_id=application.application_id, from_status=old_status, to_status=values["current_status"]
            )
        )
    await commit_or_raise_conflict(db)
    await db.refresh(application)
    return application


@router.get("", response_model=PaginatedApplicationsResponse)
async def get_applications(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = settings.items_per_page,
    status_filter: Annotated[
        ApplicationStatus | None, Query(alias="status", description="Only applications with this status")
    ] = None,
):
    query = select(models.Application).where(models.Application.user_id == current_user.id)
    if status_filter is not None:
        query = query.where(models.Application.current_status == status_filter)
    query = query.order_by(models.Application.date_applied.desc(), models.Application.application_id.desc())
    page = await paginate(query, db, skip, limit)

    ids = [application.application_id for application in page.items]
    history = models.ApplicationStatusChange
    result = await db.execute(
        select(history.application_id, func.max(history.changed_at))
        .where(history.application_id.in_(ids))
        .group_by(history.application_id)
    )
    last_changes = dict(result.all())

    responses = []
    for application in page.items:
        response = ApplicationResponse.model_validate(application)
        response.last_status_change = last_changes.get(application.application_id)
        responses.append(response)

    return PaginatedApplicationsResponse(
        applications=responses,
        total=page.total,
        skip=skip,
        limit=limit,
        has_more=page.has_more,
    )


@router.post("", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_application(
    application_data: ApplicationCreate, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]
):
    await get_job_or_404(application_data.job_id, current_user.id, db)
    await ensure_application_job_available(current_user.id, application_data.job_id, db)
    values = application_data.model_dump(exclude_unset=True, exclude_none=True)
    application = models.Application(**values, user_id=current_user.id)
    application.status_changes.append(
        models.ApplicationStatusChange(from_status=None, to_status=values.get("current_status", "Applied"))
    )
    db.add(application)
    await commit_or_raise_conflict(db)
    await db.refresh(application)
    return application


@router.post("/quick", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def quick_create_application(
    data: QuickApplicationCreate, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]
):
    job_details = data.model_dump(include=JOB_DETAIL_FIELDS, exclude_none=True)
    company_details = data.model_dump(include=COMPANY_DETAIL_FIELDS, exclude_none=True)

    result = await db.execute(
        select(models.Job).where(models.Job.job_url == data.job_url, models.Job.user_id == current_user.id)
    )
    job = result.scalar_one_or_none()

    if job is None:
        result = await db.execute(
            select(models.Company)
            .where(
                func.lower(models.Company.company_name) == data.company_name.lower(),
                models.Company.user_id == current_user.id,
            )
            .order_by(models.Company.company_id)
        )
        company = result.scalars().first()
        if company is None:
            company_id = await unique_id(models.Company, slugify(data.company_name), "company", db)
            company = models.Company(
                company_id=company_id, company_name=data.company_name, user_id=current_user.id, **company_details
            )
            db.add(company)
        else:
            fill_empty_fields(company, company_details)

        job_id = await unique_id(models.Job, slugify(f"{company.company_id} {data.role}"), "job", db)
        job = models.Job(
            job_id=job_id,
            role=data.role,
            job_url=data.job_url,
            job_posting_date=data.job_posting_date or date.today(),
            company_id=company.company_id,
            user_id=current_user.id,
            **job_details,
        )
        db.add(job)
    else:
        await ensure_application_job_available(current_user.id, job.job_id, db)
        fill_empty_fields(job, job_details)
        try:
            JobBase.model_validate({field: getattr(job, field) for field in JobBase.model_fields})
        except ValidationError as exception:
            raise RequestValidationError(exception.errors()) from exception
        fill_empty_fields(await db.get(models.Company, job.company_id), company_details)

    values = data.model_dump(include={"current_status", "date_applied", "interview_rounds", "notes"}, exclude_none=True)
    application = models.Application(**values, job_id=job.job_id, user_id=current_user.id)
    application.status_changes.append(models.ApplicationStatusChange(from_status=None, to_status=data.current_status))
    db.add(application)
    await commit_or_raise_conflict(db)
    await db.refresh(application)
    return application


@router.get("/{application_id}", response_model=ApplicationResponse)
async def get_application(application_id: int, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    return await get_application_or_404(application_id, current_user.id, db)


@router.get("/{application_id}/history", response_model=list[StatusChangeResponse])
async def get_application_history(
    application_id: int, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]
):
    await get_application_or_404(application_id, current_user.id, db)
    result = await db.execute(
        select(models.ApplicationStatusChange)
        .where(models.ApplicationStatusChange.application_id == application_id)
        .order_by(models.ApplicationStatusChange.changed_at, models.ApplicationStatusChange.id)
    )
    return result.scalars().all()


@router.put("/{application_id}", response_model=ApplicationResponse)
async def replace_application(
    application_id: int,
    application_data: ApplicationReplace,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    application = await get_application_or_404(application_id, current_user.id, db)
    return await save_application_changes(application, application_data.model_dump(), current_user.id, db)


@router.patch("/{application_id}", response_model=ApplicationResponse)
async def update_application(
    application_id: int,
    application_data: ApplicationUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    application = await get_application_or_404(application_id, current_user.id, db)
    values = application_data.model_dump(exclude_unset=True)
    return await save_application_changes(application, values, current_user.id, db)


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(
    application_id: int, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]
):
    application = await get_application_or_404(application_id, current_user.id, db)
    await db.delete(application)
    await commit_or_raise_conflict(db)
