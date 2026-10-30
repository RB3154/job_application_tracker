from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

import models
from auth import CurrentUser
from config import settings
from database import get_db
from routers.helpers import (
    commit_or_raise_conflict,
    contains_pattern,
    ensure_ids_exist,
    get_company_or_404,
    paginate,
    slugify,
    unique_id,
)
from schemas import (
    CompanyBase,
    CompanyCreate,
    CompanyLocations,
    CompanyResponse,
    CompanyUpdate,
    LookupResponse,
    PaginatedCompaniesResponse,
)


router = APIRouter()


def filter_companies(query: Select, q: str | None, user_id: int) -> Select:
    """Keep only the user's own companies, and of those the ones whose name contains q (any upper/lower case).

    Also used by the /companies page.
    """

    query = query.where(models.Company.user_id == user_id)
    if q and q.strip():
        query = query.where(models.Company.company_name.ilike(contains_pattern(q.strip()), escape="\\"))
    return query


@router.get("", response_model=PaginatedCompaniesResponse)
async def get_companies(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = settings.items_per_page,
    q: Annotated[str | None, Query(max_length=100, description="Text to find in the company name")] = None,
):
    query = filter_companies(select(models.Company), q, current_user.id)
    # A-Z by name; company_id breaks ties so companies with the same name keep a fixed order between pages.
    query = query.order_by(models.Company.company_name, models.Company.company_id)
    page = await paginate(query, db, skip, limit)

    return PaginatedCompaniesResponse(
        companies=[CompanyResponse.model_validate(company) for company in page.items],
        total=page.total,
        skip=skip,
        limit=limit,
        has_more=page.has_more,
    )


@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(
    company_data: CompanyCreate, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]
):
    company_id = await unique_id(models.Company, slugify(company_data.company_name), "company", db)
    company = models.Company(**company_data.model_dump(), company_id=company_id, user_id=current_user.id)
    db.add(company)
    await commit_or_raise_conflict(db)
    await db.refresh(company)
    return company


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(company_id: str, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    return await get_company_or_404(company_id, current_user.id, db)


@router.put("/{company_id}", response_model=CompanyResponse)
async def replace_company(
    company_id: str, company_data: CompanyBase, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]
):
    company = await get_company_or_404(company_id, current_user.id, db)
    for field, value in company_data.model_dump().items():
        setattr(company, field, value)
    await commit_or_raise_conflict(db)
    await db.refresh(company)
    return company


@router.patch("/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: str,
    company_data: CompanyUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    company = await get_company_or_404(company_id, current_user.id, db)
    for field, value in company_data.model_dump(exclude_unset=True).items():
        setattr(company, field, value)
    await commit_or_raise_conflict(db)
    await db.refresh(company)
    return company


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(company_id: str, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    company = await get_company_or_404(company_id, current_user.id, db)
    # Only need to know if at least one job exists, so fetch a single row.
    result = await db.execute(select(models.Job.job_id).where(models.Job.company_id == company_id).limit(1))
    if result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Company has related jobs and cannot be deleted"
        )
    # Its locations are part of the company itself, so they go with it.
    await db.execute(delete(models.CompanyLocation).where(models.CompanyLocation.company_id == company_id))
    await db.delete(company)
    await commit_or_raise_conflict(db)


async def company_locations_response(company_id: str, db: AsyncSession) -> list[LookupResponse]:
    result = await db.execute(
        select(models.Location)
        .join(models.CompanyLocation, models.CompanyLocation.loc_id == models.Location.loc_id)
        .where(models.CompanyLocation.company_id == company_id)
        .order_by(models.Location.name)
    )
    return [LookupResponse(id=location.loc_id, name=location.name) for location in result.scalars().all()]


@router.get("/{company_id}/locations", response_model=list[LookupResponse])
async def get_company_locations(
    company_id: str, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]
):
    await get_company_or_404(company_id, current_user.id, db)
    return await company_locations_response(company_id, db)


@router.put("/{company_id}/locations", response_model=list[LookupResponse])
async def replace_company_locations(
    company_id: str, data: CompanyLocations, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]
):
    """Replace the company's locations with the list sent (an empty list removes them all)."""

    await get_company_or_404(company_id, current_user.id, db)
    await ensure_ids_exist(models.Location.loc_id, data.location_ids, "Location", current_user.id, db)
    await db.execute(delete(models.CompanyLocation).where(models.CompanyLocation.company_id == company_id))
    db.add_all([models.CompanyLocation(company_id=company_id, loc_id=loc_id) for loc_id in data.location_ids])
    await commit_or_raise_conflict(db)
    return await company_locations_response(company_id, db)
