"""SQLAlchemy ORM models for the job application tracker schema."""

from datetime import date
from decimal import Decimal

from sqlalchemy import CHAR, DECIMAL, CheckConstraint, Date, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Company(Base):
    __tablename__ = "company"

    company_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    company_site: Mapped[str | None] = mapped_column(Text, nullable=True)
    company_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    jobs: Mapped[list["Job"]] = relationship(back_populates="company")
    company_locations: Mapped[list["CompanyLocation"]] = relationship(back_populates="company")
    locations: Mapped[list["Location"]] = relationship(
        secondary="company_location", back_populates="companies", overlaps="company_locations,location"
    )


class Job(Base):
    __tablename__ = "job"
    __table_args__ = (
        CheckConstraint("application_deadline >= job_posting_date"),
        CheckConstraint("exp_min >= 0"),
        CheckConstraint("exp_max >= 0"),
        CheckConstraint("exp_max >= exp_min"),
        CheckConstraint("salary_min >= 0"),
        CheckConstraint("salary_max >= 0"),
        CheckConstraint("salary_max >= salary_min"),
        Index("ix_job_role", "role"),
        Index("ix_job_job_posting_date", "job_posting_date"),
        Index("ix_job_application_deadline", "application_deadline"),
        Index("ix_job_company_id", "company_id"),
    )

    job_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    role: Mapped[str] = mapped_column(String(255), nullable=False)
    JD: Mapped[str] = mapped_column(Text, nullable=False)
    job_url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    job_posting_date: Mapped[date] = mapped_column(Date, nullable=False)
    application_deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    exp_min: Mapped[Decimal | None] = mapped_column(DECIMAL(4, 1), nullable=True)
    exp_max: Mapped[Decimal | None] = mapped_column(DECIMAL(4, 1), nullable=True)
    exp_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    salary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    salary_min: Mapped[Decimal | None] = mapped_column(DECIMAL(15, 2), nullable=True)
    salary_max: Mapped[Decimal | None] = mapped_column(DECIMAL(15, 2), nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(CHAR(3), nullable=True)
    salary_period: Mapped[str | None] = mapped_column(String(20), nullable=True)
    company_id: Mapped[str] = mapped_column(String(100), ForeignKey("company.company_id"), nullable=False)

    company: Mapped["Company"] = relationship(back_populates="jobs")
    applications: Mapped[list["Application"]] = relationship(back_populates="job")
    job_locations: Mapped[list["JobLocation"]] = relationship(back_populates="job")
    locations: Mapped[list["Location"]] = relationship(
        secondary="job_location", back_populates="jobs", overlaps="job,job_locations,location"
    )
    job_work_modes: Mapped[list["JobWorkMode"]] = relationship(back_populates="job")
    work_modes: Mapped[list["WorkMode"]] = relationship(
        secondary="job_work_mode", back_populates="jobs", overlaps="job,job_work_modes,work_mode"
    )
    job_skills: Mapped[list["JobSkill"]] = relationship(back_populates="job")
    skills: Mapped[list["Skill"]] = relationship(
        secondary="job_skill", back_populates="jobs", overlaps="job,job_skills,skill"
    )
    job_educations: Mapped[list["JobEducation"]] = relationship(back_populates="job")
    education_requirements: Mapped[list["EducationRequirement"]] = relationship(
        secondary="job_education",
        back_populates="jobs",
        overlaps="education_requirement,job,job_educations",
    )
    job_sources: Mapped[list["JobSource"]] = relationship(back_populates="job")
    sources: Mapped[list["Source"]] = relationship(
        secondary="job_source", back_populates="jobs", overlaps="job,job_sources,source"
    )


class Application(Base):
    __tablename__ = "application"
    __table_args__ = (
        CheckConstraint(
            "current_status IN ('Applied', 'Screening', 'Interview', 'Rejected', "
            "'Offer', 'Accepted', 'Withdrawn')"
        ),
        UniqueConstraint("user_id", "job_id"),
        Index("ix_application_date_applied", "date_applied"),
    )

    application_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[str] = mapped_column(String(100), ForeignKey("job.job_id"), nullable=False)
    date_applied: Mapped[date] = mapped_column(Date, nullable=False, server_default=text("CURRENT_DATE"))
    current_status: Mapped[str | None] = mapped_column(
        String(30), nullable=True, server_default=text("'Applied'")
    )

    job: Mapped["Job"] = relationship(back_populates="applications")
    user: Mapped["User"] = relationship(back_populates="applications")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    image_file: Mapped[str | None] = mapped_column(String(200), nullable=True)

    applications: Mapped[list["Application"]] = relationship(back_populates="user", passive_deletes=True)

    @property
    def image_path(self) -> str | None:
        """URL of the profile picture, or None if the user hasn't uploaded one."""

        return f"/media/profile_pics/{self.image_file}" if self.image_file else None


class Location(Base):
    __tablename__ = "location"

    loc_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)

    job_locations: Mapped[list["JobLocation"]] = relationship(back_populates="location")
    jobs: Mapped[list["Job"]] = relationship(
        secondary="job_location", back_populates="locations", overlaps="job,job_locations,location"
    )
    company_locations: Mapped[list["CompanyLocation"]] = relationship(back_populates="location")
    companies: Mapped[list["Company"]] = relationship(
        secondary="company_location", back_populates="locations", overlaps="company,company_locations,location"
    )


class WorkMode(Base):
    __tablename__ = "work_mode"

    work_mode_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)

    job_work_modes: Mapped[list["JobWorkMode"]] = relationship(back_populates="work_mode")
    jobs: Mapped[list["Job"]] = relationship(
        secondary="job_work_mode", back_populates="work_modes", overlaps="job,job_work_modes,work_mode"
    )


class Skill(Base):
    __tablename__ = "skill"

    skill_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    skill_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)

    job_skills: Mapped[list["JobSkill"]] = relationship(back_populates="skill")
    jobs: Mapped[list["Job"]] = relationship(
        secondary="job_skill", back_populates="skills", overlaps="job,job_skills,skill"
    )


class EducationRequirement(Base):
    __tablename__ = "education_requirement"

    education_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    education_name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)

    job_educations: Mapped[list["JobEducation"]] = relationship(back_populates="education_requirement")
    jobs: Mapped[list["Job"]] = relationship(
        secondary="job_education",
        back_populates="education_requirements",
        overlaps="education_requirement,job,job_educations",
    )


class Source(Base):
    __tablename__ = "source"

    source_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    source_name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)

    job_sources: Mapped[list["JobSource"]] = relationship(back_populates="source")
    jobs: Mapped[list["Job"]] = relationship(
        secondary="job_source", back_populates="sources", overlaps="job,job_sources,source"
    )


class JobLocation(Base):
    __tablename__ = "job_location"
    __table_args__ = (Index("ix_job_location_loc_id", "loc_id"),)

    job_id: Mapped[str] = mapped_column(String(100), ForeignKey("job.job_id"), primary_key=True)
    loc_id: Mapped[int] = mapped_column(ForeignKey("location.loc_id"), primary_key=True)

    job: Mapped["Job"] = relationship(back_populates="job_locations", overlaps="locations")
    location: Mapped["Location"] = relationship(back_populates="job_locations", overlaps="jobs")


class JobWorkMode(Base):
    __tablename__ = "job_work_mode"
    __table_args__ = (Index("ix_job_work_mode_work_mode_id", "work_mode_id"),)

    job_id: Mapped[str] = mapped_column(String(100), ForeignKey("job.job_id"), primary_key=True)
    work_mode_id: Mapped[int] = mapped_column(ForeignKey("work_mode.work_mode_id"), primary_key=True)

    job: Mapped["Job"] = relationship(back_populates="job_work_modes", overlaps="work_modes")
    work_mode: Mapped["WorkMode"] = relationship(back_populates="job_work_modes", overlaps="jobs")


class JobSkill(Base):
    __tablename__ = "job_skill"
    __table_args__ = (
        CheckConstraint("skill_type IN ('required', 'preferred')"),
        Index("ix_job_skill_skill_id", "skill_id"),
    )

    job_id: Mapped[str] = mapped_column(String(100), ForeignKey("job.job_id"), primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skill.skill_id"), primary_key=True)
    skill_type: Mapped[str | None] = mapped_column(
        String(20), nullable=True, server_default=text("'required'")
    )

    job: Mapped["Job"] = relationship(back_populates="job_skills", overlaps="skills")
    skill: Mapped["Skill"] = relationship(back_populates="job_skills", overlaps="jobs")


class JobEducation(Base):
    __tablename__ = "job_education"
    __table_args__ = (Index("ix_job_education_education_id", "education_id"),)

    job_id: Mapped[str] = mapped_column(String(100), ForeignKey("job.job_id"), primary_key=True)
    education_id: Mapped[int] = mapped_column(
        ForeignKey("education_requirement.education_id"), primary_key=True
    )
    ed_req_txt: Mapped[str | None] = mapped_column(Text, nullable=True)

    job: Mapped["Job"] = relationship(back_populates="job_educations", overlaps="education_requirements")
    education_requirement: Mapped["EducationRequirement"] = relationship(
        back_populates="job_educations", overlaps="jobs"
    )


class JobSource(Base):
    __tablename__ = "job_source"
    __table_args__ = (Index("ix_job_source_source_id", "source_id"),)

    job_id: Mapped[str] = mapped_column(String(100), ForeignKey("job.job_id"), primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("source.source_id"), primary_key=True)

    job: Mapped["Job"] = relationship(back_populates="job_sources", overlaps="sources")
    source: Mapped["Source"] = relationship(back_populates="job_sources", overlaps="jobs")


class CompanyLocation(Base):
    __tablename__ = "company_location"
    __table_args__ = (Index("ix_company_location_loc_id", "loc_id"),)

    company_id: Mapped[str] = mapped_column(String(100), ForeignKey("company.company_id"), primary_key=True)
    loc_id: Mapped[int] = mapped_column(ForeignKey("location.loc_id"), primary_key=True)

    company: Mapped["Company"] = relationship(back_populates="company_locations", overlaps="locations")
    location: Mapped["Location"] = relationship(back_populates="company_locations", overlaps="companies")
