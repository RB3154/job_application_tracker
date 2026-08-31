"""Pydantic request and response schemas for core tracker entities."""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ApplicationStatus = Literal[
    "Applied",
    "Screening",
    "Interview",
    "Rejected",
    "Offer",
    "Accepted",
    "Withdrawn",
]


class CompanyBase(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    company_site: str | None = None
    company_description: str | None = None


class CompanyCreate(CompanyBase):
    company_id: str = Field(min_length=1, max_length=100)


class CompanyResponse(CompanyBase):
    model_config = ConfigDict(from_attributes=True)

    company_id: str


class JobBase(BaseModel):
    role: str = Field(min_length=1, max_length=255)
    JD: str = Field(min_length=1)
    job_url: str = Field(min_length=1)
    job_posting_date: date
    application_deadline: date | None = None
    exp_min: Decimal | None = None
    exp_max: Decimal | None = None
    exp_text: str | None = None
    salary_text: str | None = None
    salary_min: Decimal | None = None
    salary_max: Decimal | None = None
    salary_currency: str | None = Field(default=None, min_length=3, max_length=3)
    salary_period: str | None = Field(default=None, max_length=20)
    company_id: str = Field(min_length=1, max_length=100)


class JobCreate(JobBase):
    job_id: str = Field(min_length=1, max_length=100)


class JobResponse(JobBase):
    model_config = ConfigDict(from_attributes=True)

    job_id: str


class ApplicationBase(BaseModel):
    job_id: str = Field(min_length=1, max_length=100)
    date_applied: date | None = None
    current_status: ApplicationStatus | None = None


class ApplicationCreate(ApplicationBase):
    application_id: int


class ApplicationResponse(ApplicationBase):
    model_config = ConfigDict(from_attributes=True)

    application_id: int
