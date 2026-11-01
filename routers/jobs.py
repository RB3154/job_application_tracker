from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

import models
from auth import CurrentUser
from database import get_db
from routers.helpers import (
    commit_or_raise_conflict,
    ensure_ids_exist,
    ensure_job_url_available,
    filter_jobs,
    get_company_or_404,
    get_job_or_404,
    get_job_with_details_or_404,
    paginate,
    slugify,
    unique_id,
)
from schemas import (
    JobBase,
    JobCreate,
    JobDetails,
    JobDetailsResponse,
    JobEducationResponse,
    JobListQuery,
    JobResponse,
    JobSkillResponse,
    JobUpdate,
    LookupResponse,
    PaginatedJobsResponse,
)


router = APIRouter()

JOB_LINK_MODELS = (models.JobLocation, models.JobWorkMode, models.JobSkill, models.JobEducation, models.JobSource)


def sorted_by_name(items):
    return sorted(items, key=lambda item: item.name.lower())


def job_details_response(job: models.Job) -> JobDetailsResponse:
    return JobDetailsResponse(
        locations=sorted_by_name(LookupResponse(id=item.loc_id, name=item.name) for item in job.locations),
        work_modes=sorted_by_name(LookupResponse(id=item.work_mode_id, name=item.name) for item in job.work_modes),
        sources=sorted_by_name(LookupResponse(id=item.source_id, name=item.source_name) for item in job.sources),
        skills=sorted_by_name(
            JobSkillResponse(id=link.skill_id, name=link.skill.skill_name, skill_type=link.skill_type or "required")
            for link in job.job_skills
        ),
        education=sorted_by_name(
            JobEducationResponse(
                id=link.education_id, name=link.education_requirement.education_name, note=link.ed_req_txt
            )
            for link in job.job_educations
        ),
    )


async def save_job_changes(job: models.Job, values: dict, user_id: int, db: AsyncSession) -> models.Job:
    if "company_id" in values and values["company_id"] != job.company_id:
        await get_company_or_404(values["company_id"], user_id, db)
    if "job_url" in values and values["job_url"] != job.job_url:
        await ensure_job_url_available(values["job_url"], user_id, db, job.job_id)
    for field, value in values.items():
        setattr(job, field, value)
    await commit_or_raise_conflict(db)
    await db.refresh(job)
    return job


@router.get("", response_model=PaginatedJobsResponse)
async def get_jobs(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    params: Annotated[JobListQuery, Query()],
):
    query = filter_jobs(select(models.Job), params, current_user.id)
    query = query.order_by(models.Job.job_posting_date.desc(), models.Job.job_id)
    page = await paginate(query, db, params.skip, params.limit)

    return PaginatedJobsResponse(
        jobs=[JobResponse.model_validate(job) for job in page.items],
        total=page.total,
        skip=params.skip,
        limit=params.limit,
        has_more=page.has_more,
    )


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(job_data: JobCreate, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    company = await get_company_or_404(job_data.company_id, current_user.id, db)
    await ensure_job_url_available(job_data.job_url, current_user.id, db)
    job_id = await unique_id(models.Job, slugify(f"{company.company_id} {job_data.role}"), "job", db)
    job = models.Job(**job_data.model_dump(), job_id=job_id, user_id=current_user.id)
    db.add(job)
    await commit_or_raise_conflict(db)
    await db.refresh(job)
    return job


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    return await get_job_or_404(job_id, current_user.id, db)


@router.put("/{job_id}", response_model=JobResponse)
async def replace_job(
    job_id: str, job_data: JobBase, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]
):
    job = await get_job_or_404(job_id, current_user.id, db)
    return await save_job_changes(job, job_data.model_dump(), current_user.id, db)


@router.patch("/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: str, job_data: JobUpdate, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]
):
    job = await get_job_or_404(job_id, current_user.id, db)
    try:
        job_data.validate_ranges_against(job)
    except ValidationError as exception:
        raise RequestValidationError(exception.errors()) from exception
    return await save_job_changes(job, job_data.model_dump(exclude_unset=True), current_user.id, db)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(job_id: str, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    job = await get_job_or_404(job_id, current_user.id, db)
    result = await db.execute(select(models.Application.job_id).where(models.Application.job_id == job_id).limit(1))
    if result.scalars().first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Job has applications and cannot be deleted")
    for link_model in JOB_LINK_MODELS:
        await db.execute(delete(link_model).where(link_model.job_id == job_id))
    await db.delete(job)
    await commit_or_raise_conflict(db)


@router.get("/{job_id}/details", response_model=JobDetailsResponse)
async def get_job_details(job_id: str, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    return job_details_response(await get_job_with_details_or_404(job_id, current_user.id, db))


@router.put("/{job_id}/details", response_model=JobDetailsResponse)
async def replace_job_details(
    job_id: str, details: JobDetails, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]
):
    await get_job_or_404(job_id, current_user.id, db)
    user_id = current_user.id
    await ensure_ids_exist(models.Location.loc_id, details.location_ids, "Location", user_id, db)
    await ensure_ids_exist(models.WorkMode.work_mode_id, details.work_mode_ids, "Work mode", user_id, db)
    await ensure_ids_exist(models.Source.source_id, details.source_ids, "Source", user_id, db)
    await ensure_ids_exist(models.Skill.skill_id, [item.skill_id for item in details.skills], "Skill", user_id, db)
    await ensure_ids_exist(
        models.EducationRequirement.education_id,
        [item.education_id for item in details.education],
        "Education requirement",
        user_id,
        db,
    )

    for link_model in JOB_LINK_MODELS:
        await db.execute(delete(link_model).where(link_model.job_id == job_id))
    db.add_all(
        [models.JobLocation(job_id=job_id, loc_id=loc_id) for loc_id in details.location_ids]
        + [models.JobWorkMode(job_id=job_id, work_mode_id=work_mode_id) for work_mode_id in details.work_mode_ids]
        + [models.JobSource(job_id=job_id, source_id=source_id) for source_id in details.source_ids]
        + [
            models.JobSkill(job_id=job_id, skill_id=item.skill_id, skill_type=item.skill_type)
            for item in details.skills
        ]
        + [
            models.JobEducation(job_id=job_id, education_id=item.education_id, ed_req_txt=item.note)
            for item in details.education
        ]
    )
    await commit_or_raise_conflict(db)
    return job_details_response(await get_job_with_details_or_404(job_id, current_user.id, db))
