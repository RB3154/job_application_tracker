from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import models
from auth import CurrentUser
from config import settings
from database import get_db
from routers.helpers import commit_or_raise_conflict, get_company_or_404
from schemas import CompanyBase, CompanyCreate, CompanyResponse, CompanyUpdate, PaginatedCompaniesResponse


router = APIRouter()


@router.get("", response_model=PaginatedCompaniesResponse)
async def get_companies(
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = settings.items_per_page,
):
    count_result = await db.execute(select(func.count()).select_from(models.Company))
    total = count_result.scalar() or 0

    # A-Z by name; company_id breaks ties so companies with the same name keep a fixed order between pages.
    result = await db.execute(
        select(models.Company)
        .order_by(models.Company.company_name, models.Company.company_id)
        .offset(skip)
        .limit(limit)
    )
    companies = result.scalars().all()

    return PaginatedCompaniesResponse(
        companies=[CompanyResponse.model_validate(company) for company in companies],
        total=total,
        skip=skip,
        limit=limit,
        has_more=skip + len(companies) < total,
    )


@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(company_data: CompanyCreate, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    if await db.get(models.Company, company_data.company_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Company ID already exists")
    company = models.Company(**company_data.model_dump())
    db.add(company)
    await commit_or_raise_conflict(db)
    await db.refresh(company)
    return company


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(company_id: str, db: Annotated[AsyncSession, Depends(get_db)]):
    return await get_company_or_404(company_id, db)


@router.put("/{company_id}", response_model=CompanyResponse)
async def replace_company(company_id: str, company_data: CompanyBase, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    company = await get_company_or_404(company_id, db)
    for field, value in company_data.model_dump().items():
        setattr(company, field, value)
    await commit_or_raise_conflict(db)
    await db.refresh(company)
    return company


@router.patch("/{company_id}", response_model=CompanyResponse)
async def update_company(company_id: str, company_data: CompanyUpdate, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    company = await get_company_or_404(company_id, db)
    for field, value in company_data.model_dump(exclude_unset=True).items():
        setattr(company, field, value)
    await commit_or_raise_conflict(db)
    await db.refresh(company)
    return company


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(company_id: str, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    company = await get_company_or_404(company_id, db)
    result = await db.execute(select(models.Job.job_id).where(models.Job.company_id == company_id))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Company has related jobs and cannot be deleted")
    await db.delete(company)
    await commit_or_raise_conflict(db)
