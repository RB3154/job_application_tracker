import re
import unicodedata
from collections.abc import Sequence
from datetime import date
from typing import Any, NamedTuple

from fastapi import HTTPException, status
from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute, selectinload

import models
from schemas import JobFilters


class Page(NamedTuple):
    items: Sequence[Any]
    total: int
    has_more: bool


async def paginate(query: Select, db: AsyncSession, skip: int, limit: int) -> Page:
    count_result = await db.execute(select(func.count()).select_from(query.order_by(None).subquery()))
    total = count_result.scalar() or 0

    result = await db.execute(query.offset(skip).limit(limit))
    items = result.scalars().all()
    return Page(items=items, total=total, has_more=skip + len(items) < total)


def slugify(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")


async def unique_id(model: type[models.Base], base: str, fallback: str, db: AsyncSession) -> str:
    base = base[:90] or fallback
    candidate, number = base, 1
    while await db.get(model, candidate) is not None:
        number += 1
        candidate = f"{base}-{number}"
    return candidate


def contains_pattern(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def filter_jobs(query: Select, filters: JobFilters, user_id: int) -> Select:
    query = query.where(models.Job.user_id == user_id)
    if filters.q:
        pattern = contains_pattern(filters.q)
        query = query.join(models.Job.company).where(
            or_(models.Job.role.ilike(pattern, escape="\\"), models.Company.company_name.ilike(pattern, escape="\\"))
        )
    if filters.company_id:
        query = query.where(models.Job.company_id == filters.company_id)
    if filters.location_id is not None:
        query = query.where(
            models.Job.job_id.in_(
                select(models.JobLocation.job_id).where(models.JobLocation.loc_id == filters.location_id)
            )
        )
    if filters.skill_id is not None:
        query = query.where(
            models.Job.job_id.in_(select(models.JobSkill.job_id).where(models.JobSkill.skill_id == filters.skill_id))
        )
    if filters.work_mode_id is not None:
        query = query.where(
            models.Job.job_id.in_(
                select(models.JobWorkMode.job_id).where(models.JobWorkMode.work_mode_id == filters.work_mode_id)
            )
        )
    if filters.open_only:
        query = query.where(
            or_(models.Job.application_deadline.is_(None), models.Job.application_deadline >= date.today())
        )
    return query


async def commit_or_raise_conflict(db: AsyncSession) -> None:
    try:
        await db.commit()
    except IntegrityError as exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Request conflicts with an existing database constraint",
        ) from exception


async def get_company_or_404(company_id: str, user_id: int, db: AsyncSession) -> models.Company:
    company = await db.get(models.Company, company_id)
    if company is None or company.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company


async def get_job_or_404(job_id: str, user_id: int, db: AsyncSession) -> models.Job:
    job = await db.get(models.Job, job_id)
    if job is None or job.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


async def get_job_with_details_or_404(job_id: str, user_id: int, db: AsyncSession) -> models.Job:
    result = await db.execute(
        select(models.Job)
        .options(
            selectinload(models.Job.company),
            selectinload(models.Job.locations),
            selectinload(models.Job.work_modes),
            selectinload(models.Job.sources),
            selectinload(models.Job.job_skills).selectinload(models.JobSkill.skill),
            selectinload(models.Job.job_educations).selectinload(models.JobEducation.education_requirement),
        )
        .where(models.Job.job_id == job_id, models.Job.user_id == user_id)
        .execution_options(populate_existing=True)
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


async def ensure_ids_exist(
    id_column: InstrumentedAttribute, ids: list[int], item_name: str, user_id: int, db: AsyncSession
) -> None:
    if not ids:
        return
    owner_column = id_column.class_.user_id
    result = await db.execute(select(id_column).where(id_column.in_(ids), owner_column == user_id))
    missing = sorted(set(ids) - set(result.scalars().all()))
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{item_name} not found: {', '.join(str(item_id) for item_id in missing)}",
        )


async def get_application_or_404(application_id: int, user_id: int, db: AsyncSession) -> models.Application:
    application = await db.get(models.Application, application_id)
    if application is None or application.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return application


async def ensure_job_url_available(
    job_url: str, user_id: int, db: AsyncSession, current_job_id: str | None = None
) -> None:
    result = await db.execute(select(models.Job).where(models.Job.job_url == job_url, models.Job.user_id == user_id))
    existing_job = result.scalar_one_or_none()
    if existing_job and existing_job.job_id != current_job_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You already saved a job with this link")


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
