"""Pydantic request and response schemas for core tracker entities."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from config import settings


ApplicationStatus = Literal[
    "Wishlist",  # saved to apply to later; date_applied then means "date saved"
    "Applied",
    "Screening",
    "Interview",
    "Rejected",
    "Offer",
    "Accepted",
    "Withdrawn",
]


def check_web_address(value: str) -> str:
    """Allow only http(s) addresses with a site name, e.g. "https://careers.example.com/123"."""

    parts = urlparse(value)
    if parts.scheme.lower() not in ("http", "https") or not parts.netloc:
        raise ValueError("must be a web address starting with http:// or https://")
    return value


# A str that must be an http(s) address. Kept as plain text (not pydantic's HttpUrl), so the value
# is saved exactly as typed instead of being rewritten (HttpUrl would e.g. add a trailing "/").
WebAddress = Annotated[str, AfterValidator(check_web_address)]


class CompanyBase(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    company_site: WebAddress | None = None
    company_description: str | None = None


class CompanyCreate(CompanyBase):
    """The id isn't sent: the server makes it from the name (see unique_id() in routers/helpers.py)."""


class CompanyResponse(CompanyBase):
    model_config = ConfigDict(from_attributes=True)

    # Plain str in responses: an odd value already in the database shouldn't break reading it.
    company_site: str | None = None
    company_id: str


class CompanyUpdate(BaseModel):
    # PATCH pattern used by all *Update schemas: `str = Field(default=None)` (not `str | None`) on purpose.
    # Pydantic never validates defaults, so a left-out field stays None and the route skips it
    # (model_dump(exclude_unset=True)), while an explicit null is checked against `str` and gets a 422.
    # That keeps required columns from being set to NULL. Fields typed `X | None` can be cleared with null.
    company_name: str = Field(default=None, min_length=1, max_length=255)
    company_site: WebAddress | None = None
    company_description: str | None = None


class PaginatedCompaniesResponse(BaseModel):
    companies: list[CompanyResponse]
    total: int
    skip: int
    limit: int
    has_more: bool


def check_job_ranges(job) -> None:
    """The job's date, experience and salary ranges must make sense (same rules as the database checks).

    Used by JobBase and by the Add application form's optional job details.
    """

    if job.application_deadline and job.job_posting_date and job.application_deadline < job.job_posting_date:
        raise ValueError("application_deadline must not be before job_posting_date")
    if job.exp_min is not None and job.exp_max is not None and job.exp_max < job.exp_min:
        raise ValueError("exp_max must be greater than or equal to exp_min")
    if job.salary_min is not None and job.salary_max is not None and job.salary_max < job.salary_min:
        raise ValueError("salary_max must be greater than or equal to salary_min")


class JobBase(BaseModel):
    role: str = Field(min_length=1, max_length=255)
    JD: str | None = None
    job_url: WebAddress = Field(min_length=1)
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
        check_job_ranges(self)
        return self


class JobCreate(JobBase):
    """The id isn't sent: the server makes it from the company and role (see unique_id())."""


class JobResponse(JobBase):
    model_config = ConfigDict(from_attributes=True)

    # Plain str in responses: an odd value already in the database shouldn't break reading it.
    job_url: str
    job_id: str


class JobUpdate(BaseModel):
    role: str = Field(default=None, min_length=1, max_length=255)
    JD: str | None = None
    job_url: WebAddress = Field(default=None, min_length=1)
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

        current_values = {field_name: getattr(job, field_name) for field_name in JobBase.model_fields}
        JobBase.model_validate(current_values | self.model_dump(exclude_unset=True))


class JobFilters(BaseModel):
    """Optional filters for the job list, read from the URL, e.g. /api/jobs?q=backend&location_id=3&open_only=true.

    Used by both GET /api/jobs and the /jobs page, so "Load more" filters exactly like the page did.
    """

    q: str | None = Field(default=None, max_length=100, description="Text to find in the role or company name")
    company_id: str | None = None
    location_id: int | None = None
    skill_id: int | None = None
    work_mode_id: int | None = None
    open_only: bool = Field(default=False, description="Hide jobs whose application deadline has passed")

    @field_validator("q", "company_id", "location_id", "skill_id", "work_mode_id", mode="before")
    @classmethod
    def empty_means_no_filter(cls, value):
        # A search form sends "location_id=" for "Any location"; treat that like leaving the filter out.
        if isinstance(value, str) and not value.strip():
            return None
        return value.strip() if isinstance(value, str) else value


class JobListQuery(JobFilters):
    """Everything GET /api/jobs reads from the URL: the filters plus which page to return.

    FastAPI only spreads a model into separate URL parameters when it is the route's only query
    parameter, so skip and limit live in here too instead of being parameters of their own.
    """

    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=settings.items_per_page, ge=1, le=100)


class PaginatedJobsResponse(BaseModel):
    jobs: list[JobResponse]
    total: int
    skip: int
    limit: int
    has_more: bool


# ---------- Lookup lists: locations, work modes, skills, education requirements, sources ----------


class LookupResponse(BaseModel):
    """One entry of a lookup list. Every list uses the same shape, whatever its table calls the columns."""

    id: int
    name: str


# Request bodies for adding or renaming an entry. Spaces around the name are trimmed;
# max_length matches each table's column size in models.py.
class LocationCreate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class WorkModeCreate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]


class SkillCreate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class EducationCreate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]


class SourceCreate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]


SkillType = Literal["required", "preferred"]


def reject_duplicates(ids: list[int], what: str) -> None:
    if len(ids) != len(set(ids)):
        raise ValueError(f"the same {what} is listed more than once")


class JobSkillItem(BaseModel):
    skill_id: int
    skill_type: SkillType = "required"


class JobEducationItem(BaseModel):
    education_id: int
    note: str | None = None


class JobDetails(BaseModel):
    """Everything attached to a job. PUT replaces the whole set, so send the full lists every time."""

    location_ids: list[int] = []
    work_mode_ids: list[int] = []
    source_ids: list[int] = []
    skills: list[JobSkillItem] = []
    education: list[JobEducationItem] = []

    @model_validator(mode="after")
    def check_no_duplicates(self) -> "JobDetails":
        reject_duplicates(self.location_ids, "location")
        reject_duplicates(self.work_mode_ids, "work mode")
        reject_duplicates(self.source_ids, "source")
        reject_duplicates([item.skill_id for item in self.skills], "skill")
        reject_duplicates([item.education_id for item in self.education], "education requirement")
        return self


class JobSkillResponse(BaseModel):
    id: int
    name: str
    skill_type: SkillType


class JobEducationResponse(BaseModel):
    id: int
    name: str
    note: str | None


class JobDetailsResponse(BaseModel):
    locations: list[LookupResponse]
    work_modes: list[LookupResponse]
    sources: list[LookupResponse]
    skills: list[JobSkillResponse]
    education: list[JobEducationResponse]


class CompanyLocations(BaseModel):
    """A company's locations. PUT replaces the whole list."""

    location_ids: list[int] = []

    @model_validator(mode="after")
    def check_no_duplicates(self) -> "CompanyLocations":
        reject_duplicates(self.location_ids, "location")
        return self


class ApplicationBase(BaseModel):
    job_id: str = Field(min_length=1, max_length=100)
    date_applied: date | None = None
    current_status: ApplicationStatus | None = None
    interview_rounds: int = Field(default=0, ge=0)
    notes: str | None = Field(default=None, max_length=5000)


class ApplicationCreate(ApplicationBase):
    pass


class QuickApplicationCreate(BaseModel):
    """The one-step "Add application" form: the company and job are found or created from these fields."""

    company_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    role: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    # Required: an existing job with the same link is reused instead of creating a duplicate.
    job_url: WebAddress = Field(min_length=1)
    current_status: ApplicationStatus = "Applied"
    date_applied: date | None = None
    interview_rounds: int = Field(default=0, ge=0)
    notes: str | None = Field(default=None, max_length=5000)

    # Optional job details (the form's "Job details" section). Left out, the job only has a role and link.
    job_posting_date: date | None = None  # today when left out
    application_deadline: date | None = None
    exp_min: Decimal | None = Field(default=None, ge=0)
    exp_max: Decimal | None = Field(default=None, ge=0)
    exp_text: str | None = None
    salary_text: str | None = None
    salary_min: Decimal | None = Field(default=None, ge=0)
    salary_max: Decimal | None = Field(default=None, ge=0)
    salary_currency: str | None = Field(default=None, min_length=3, max_length=3)
    salary_period: str | None = Field(default=None, max_length=20)
    JD: str | None = None

    # Optional company details (the form's "Company details" section).
    company_site: WebAddress | None = None
    company_description: str | None = None

    @model_validator(mode="after")
    def validate_ranges(self) -> "QuickApplicationCreate":
        check_job_ranges(self)
        return self


class ApplicationResponse(ApplicationBase):
    model_config = ConfigDict(from_attributes=True)

    application_id: int
    user_id: int
    # When the status last changed (from the status history). Filled in by GET /api/applications only;
    # the dashboard uses it to spot applications with no news for a while.
    last_status_change: datetime | None = None


class ApplicationReplace(BaseModel):
    job_id: str = Field(min_length=1, max_length=100)
    date_applied: date
    current_status: ApplicationStatus | None = None
    interview_rounds: int = Field(default=0, ge=0)
    notes: str | None = Field(default=None, max_length=5000)


class ApplicationUpdate(BaseModel):
    job_id: str = Field(default=None, min_length=1, max_length=100)
    date_applied: date = None
    current_status: ApplicationStatus | None = None
    interview_rounds: int = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=5000)


class StatusChangeResponse(BaseModel):
    """One entry in an application's history. from_status is None for the entry made when it was created."""

    model_config = ConfigDict(from_attributes=True)

    from_status: str | None
    to_status: str | None
    changed_at: datetime


class PaginatedApplicationsResponse(BaseModel):
    applications: list[ApplicationResponse]
    total: int
    skip: int
    limit: int
    has_more: bool


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


class ForgotPasswordRequest(BaseModel):
    email: EmailStr = Field(max_length=255)


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class MessageResponse(BaseModel):
    message: str


class Token(BaseModel):
    access_token: str
    token_type: str


class PasswordChangedResponse(MessageResponse, Token):
    """Changing the password makes old tokens invalid, so a fresh one is sent back to stay logged in."""
