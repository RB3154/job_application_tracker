"""Pydantic request and response schemas for core tracker entities."""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


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


class CompanyUpdate(BaseModel):
    company_name: str = Field(default=None, min_length=1, max_length=255)
    company_site: str | None = None
    company_description: str | None = None


class JobBase(BaseModel):
    role: str = Field(min_length=1, max_length=255)
    JD: str = Field(min_length=1)
    job_url: str = Field(min_length=1)
    job_posting_date: date
    application_deadline: date | None = None
    exp_min: Decimal | None = Field(default=None, ge=0)
    exp_max: Decimal | None = Field(default=None, ge=0)
    exp_text: str | None = None
    salary_text: str | None = None
    salary_min: Decimal | None = Field(default=None, ge=0)
    salary_max: Decimal | None = Field(default=None, ge=0)
    salary_currency: str | None = Field(default=None, min_length=3, max_length=3)
    salary_period: str | None = Field(default=None, max_length=20)
    company_id: str = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_ranges(self) -> "JobBase":
        if self.application_deadline and self.application_deadline < self.job_posting_date:
            raise ValueError("application_deadline must not be before job_posting_date")
        if self.exp_min is not None and self.exp_max is not None and self.exp_max < self.exp_min:
            raise ValueError("exp_max must be greater than or equal to exp_min")
        if self.salary_min is not None and self.salary_max is not None and self.salary_max < self.salary_min:
            raise ValueError("salary_max must be greater than or equal to salary_min")
        return self


class JobCreate(JobBase):
    job_id: str = Field(min_length=1, max_length=100)


class JobResponse(JobBase):
    model_config = ConfigDict(from_attributes=True)

    job_id: str


class JobUpdate(BaseModel):
    role: str = Field(default=None, min_length=1, max_length=255)
    JD: str = Field(default=None, min_length=1)
    job_url: str = Field(default=None, min_length=1)
    job_posting_date: date = None
    application_deadline: date | None = None
    exp_min: Decimal | None = Field(default=None, ge=0)
    exp_max: Decimal | None = Field(default=None, ge=0)
    exp_text: str | None = None
    salary_text: str | None = None
    salary_min: Decimal | None = Field(default=None, ge=0)
    salary_max: Decimal | None = Field(default=None, ge=0)
    salary_currency: str | None = Field(default=None, min_length=3, max_length=3)
    salary_period: str | None = Field(default=None, max_length=20)
    company_id: str = Field(default=None, min_length=1, max_length=100)

    def validate_ranges_against(self, job: object) -> None:
        """Validate PATCH range fields after merging them with the persisted job."""

        current_values = {
            field_name: getattr(job, field_name)
            for field_name in JobBase.model_fields
        }
        JobBase.model_validate(current_values | self.model_dump(exclude_unset=True))


class ApplicationBase(BaseModel):
    job_id: str = Field(min_length=1, max_length=100)
    date_applied: date | None = None
    current_status: ApplicationStatus | None = None


class ApplicationCreate(ApplicationBase):
    pass


class ApplicationResponse(ApplicationBase):
    model_config = ConfigDict(from_attributes=True)

    application_id: int
    user_id: int


class ApplicationReplace(BaseModel):
    job_id: str = Field(min_length=1, max_length=100)
    date_applied: date
    current_status: ApplicationStatus | None = None


class ApplicationUpdate(BaseModel):
    job_id: str = Field(default=None, min_length=1, max_length=100)
    date_applied: date = None
    current_status: ApplicationStatus | None = None


class UserBase(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    email: EmailStr = Field(max_length=255)


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserPublic(BaseModel):
    """What anyone can see about a user."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    image_file: str | None
    image_path: str | None


class UserPrivate(UserPublic):
    """What only the user themselves can see."""

    email: EmailStr


class UserUpdate(BaseModel):
    username: str = Field(default=None, min_length=1, max_length=50)
    email: EmailStr = Field(default=None, max_length=255)


class Token(BaseModel):
    access_token: str
    token_type: str
