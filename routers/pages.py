"""HTML pages for the browser frontend.

These routes return Jinja2 templates instead of JSON and are hidden from /docs.
Public data (jobs, companies) is rendered on the server; anything that needs the
logged-in user (dashboard, account) is loaded by JavaScript calling the /api routes,
because the login token lives in the browser's localStorage, not in a cookie.
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import models
from config import settings
from database import get_db
from schemas import CompanyResponse, JobResponse


router = APIRouter(include_in_schema=False)

templates = Jinja2Templates(directory="templates")


@router.get("/", name="home")
async def home_page(request: Request):
    return templates.TemplateResponse(request, "home.html", {"title": "Dashboard"})


@router.get("/jobs", name="jobs_page")
async def jobs_page(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    count_result = await db.execute(select(func.count()).select_from(models.Job))
    total = count_result.scalar() or 0

    # Same order as GET /api/jobs, so "Load more" continues exactly where this page stops.
    result = await db.execute(
        select(models.Job)
        .options(selectinload(models.Job.company))
        .order_by(models.Job.job_posting_date.desc(), models.Job.job_id)
        .limit(settings.items_per_page)
    )
    jobs = result.scalars().all()

    return templates.TemplateResponse(
        request,
        "jobs.html",
        {
            "title": "Jobs",
            "jobs": jobs,
            "total": total,
            "limit": settings.items_per_page,
            "has_more": len(jobs) < total,
            "today": date.today(),
        },
    )


@router.get("/jobs/{job_id}", name="job_page")
async def job_page(request: Request, job_id: str, db: Annotated[AsyncSession, Depends(get_db)]):
    # selectinload fetches the related rows up front; async sessions can't lazy-load them later in the template.
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
        .where(models.Job.job_id == job_id)
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    return templates.TemplateResponse(
        request,
        "job.html",
        {
            "title": job.role[:50],
            "job": job,
            # The same JSON the API returns, so the page's JavaScript can prefill the Edit form.
            "job_data": JobResponse.model_validate(job).model_dump(mode="json"),
            "today": date.today(),
        },
    )


@router.get("/companies", name="companies_page")
async def companies_page(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    count_result = await db.execute(select(func.count()).select_from(models.Company))
    total = count_result.scalar() or 0

    result = await db.execute(
        select(models.Company)
        .order_by(models.Company.company_name, models.Company.company_id)
        .limit(settings.items_per_page)
    )
    companies = result.scalars().all()

    return templates.TemplateResponse(
        request,
        "companies.html",
        {
            "title": "Companies",
            "companies": companies,
            "total": total,
            "limit": settings.items_per_page,
            "has_more": len(companies) < total,
        },
    )


@router.get("/companies/{company_id}", name="company_page")
async def company_page(request: Request, company_id: str, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(
        select(models.Company)
        .options(selectinload(models.Company.locations), selectinload(models.Company.jobs))
        .where(models.Company.company_id == company_id)
    )
    company = result.scalar_one_or_none()
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    jobs = sorted(company.jobs, key=lambda job: (job.job_posting_date, job.job_id), reverse=True)

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
async def account_page(request: Request):
    return templates.TemplateResponse(request, "account.html", {"title": "Account"})


@router.get("/forgot-password", name="forgot_password_page")
async def forgot_password_page(request: Request):
    return templates.TemplateResponse(request, "forgot_password.html", {"title": "Forgot password"})


@router.get("/reset-password", name="reset_password_page")
async def reset_password_page(request: Request):
    response = templates.TemplateResponse(request, "reset_password.html", {"title": "Reset password"})
    # The reset token is in this page's URL; don't leak it to the CDNs the page loads CSS/JS from.
    response.headers["Referrer-Policy"] = "no-referrer"
    return response
