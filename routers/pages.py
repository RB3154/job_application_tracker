from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import models
from auth import PageUser
from config import settings
from database import get_db
from routers.companies import filter_companies
from routers.helpers import filter_jobs, get_job_with_details_or_404, paginate
from schemas import CompanyResponse, JobFilters, JobResponse


router = APIRouter(include_in_schema=False)

templates = Jinja2Templates(directory="templates")
templates.env.globals["show_api_docs"] = settings.show_api_docs


@router.get("/", name="home")
async def home_page(request: Request):
    return templates.TemplateResponse(request, "home.html", {"title": "My applications"})


@router.get("/jobs", name="jobs_page")
async def jobs_page(
    request: Request,
    user: PageUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    filters: Annotated[JobFilters, Query()],
):
    query = filter_jobs(select(models.Job).options(selectinload(models.Job.company)), filters, user.id)
    query = query.order_by(models.Job.job_posting_date.desc(), models.Job.job_id)
    page = await paginate(query, db, skip=0, limit=settings.items_per_page)

    async def own_entries(model, name_column):
        result = await db.execute(select(model).where(model.user_id == user.id).order_by(name_column))
        return result.scalars().all()

    locations = await own_entries(models.Location, models.Location.name)
    skills = await own_entries(models.Skill, models.Skill.skill_name)
    work_modes = await own_entries(models.WorkMode, models.WorkMode.name)

    return templates.TemplateResponse(
        request,
        "jobs.html",
        {
            "title": "Jobs",
            "jobs": page.items,
            "total": page.total,
            "limit": settings.items_per_page,
            "has_more": page.has_more,
            "today": date.today(),
            "filters": filters,
            "is_filtered": filters != JobFilters(),
            "locations": locations,
            "skills": skills,
            "work_modes": work_modes,
        },
    )


@router.get("/jobs/{job_id}", name="job_page")
async def job_page(request: Request, user: PageUser, job_id: str, db: Annotated[AsyncSession, Depends(get_db)]):
    job = await get_job_with_details_or_404(job_id, user.id, db)

    return templates.TemplateResponse(
        request,
        "job.html",
        {
            "title": job.role[:50],
            "job": job,
            "job_data": JobResponse.model_validate(job).model_dump(mode="json"),
            "today": date.today(),
        },
    )


@router.get("/companies", name="companies_page")
async def companies_page(
    request: Request,
    user: PageUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    q: Annotated[str | None, Query(max_length=100)] = None,
):
    query = filter_companies(select(models.Company), q, user.id)
    query = query.order_by(models.Company.company_name, models.Company.company_id)
    page = await paginate(query, db, skip=0, limit=settings.items_per_page)

    return templates.TemplateResponse(
        request,
        "companies.html",
        {
            "title": "Companies",
            "companies": page.items,
            "total": page.total,
            "limit": settings.items_per_page,
            "has_more": page.has_more,
            "q": (q or "").strip(),
        },
    )


@router.get("/companies/{company_id}", name="company_page")
async def company_page(request: Request, user: PageUser, company_id: str, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(
        select(models.Company)
        .options(selectinload(models.Company.locations), selectinload(models.Company.jobs))
        .where(models.Company.company_id == company_id, models.Company.user_id == user.id)
    )
    company = result.scalar_one_or_none()
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    jobs = sorted(company.jobs, key=lambda job: (-job.job_posting_date.toordinal(), job.job_id))

    return templates.TemplateResponse(
        request,
        "company.html",
        {
            "title": company.company_name[:50],
            "company": company,
            "company_data": CompanyResponse.model_validate(company).model_dump(mode="json"),
            "jobs": jobs,
            "today": date.today(),
        },
    )


@router.get("/login", name="login_page")
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"title": "Log in"})


@router.get("/register", name="register_page")
async def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html", {"title": "Create account"})


@router.get("/account", name="account_page")
async def account_page(request: Request, user: PageUser):
    return templates.TemplateResponse(request, "account.html", {"title": "Account"})


@router.get("/forgot-password", name="forgot_password_page")
async def forgot_password_page(request: Request):
    return templates.TemplateResponse(request, "forgot_password.html", {"title": "Forgot password"})


@router.get("/reset-password", name="reset_password_page")
async def reset_password_page(request: Request):
    response = templates.TemplateResponse(request, "reset_password.html", {"title": "Reset password"})
    response.headers["Referrer-Policy"] = "no-referrer"
    return response
