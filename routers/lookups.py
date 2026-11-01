from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

import models
from auth import CurrentUser
from database import get_db
from routers.helpers import commit_or_raise_conflict
from schemas import (
    EducationCreate,
    LocationCreate,
    LookupResponse,
    SkillCreate,
    SourceCreate,
    WorkModeCreate,
)


def create_lookup_router(
    model: type[models.Base],
    id_column: InstrumentedAttribute,
    name_column: InstrumentedAttribute,
    create_schema: type[BaseModel],
    item_name: str,
    used_by: list[InstrumentedAttribute],
) -> APIRouter:
    router = APIRouter()
    owner_column = model.user_id

    def to_response(item) -> LookupResponse:
        return LookupResponse(id=getattr(item, id_column.key), name=getattr(item, name_column.key))

    async def get_item_or_404(item_id: int, user_id: int, db: AsyncSession):
        item = await db.get(model, item_id)
        if item is None or item.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{item_name.capitalize()} not found")
        return item

    async def ensure_name_available(name: str, user_id: int, db: AsyncSession, current_id: int | None = None) -> None:
        result = await db.execute(
            select(id_column).where(func.lower(name_column) == name.lower(), owner_column == user_id)
        )
        existing_id = result.scalars().first()
        if existing_id is not None and existing_id != current_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"This {item_name} already exists")

    async def ensure_not_in_use(item_id: int, db: AsyncSession) -> None:
        for column in used_by:
            result = await db.execute(select(column).where(column == item_id).limit(1))
            if result.scalars().first() is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"This {item_name} is used by one of your jobs or companies; remove it there first",
                )

    @router.get("", response_model=list[LookupResponse])
    async def list_items(current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
        result = await db.execute(
            select(model).where(owner_column == current_user.id).order_by(func.lower(name_column))
        )
        return [to_response(item) for item in result.scalars().all()]

    @router.post("", response_model=LookupResponse, status_code=status.HTTP_201_CREATED)
    async def create_item(data: create_schema, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
        await ensure_name_available(data.name, current_user.id, db)
        item = model(**{name_column.key: data.name}, user_id=current_user.id)
        db.add(item)
        await commit_or_raise_conflict(db)
        await db.refresh(item)
        return to_response(item)

    @router.patch("/{item_id}", response_model=LookupResponse)
    async def rename_item(
        item_id: int, data: create_schema, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]
    ):
        item = await get_item_or_404(item_id, current_user.id, db)
        await ensure_name_available(data.name, current_user.id, db, item_id)
        setattr(item, name_column.key, data.name)
        await commit_or_raise_conflict(db)
        await db.refresh(item)
        return to_response(item)

    @router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_item(item_id: int, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
        item = await get_item_or_404(item_id, current_user.id, db)
        await ensure_not_in_use(item_id, db)
        await db.delete(item)
        await commit_or_raise_conflict(db)

    return router


locations_router = create_lookup_router(
    models.Location,
    models.Location.loc_id,
    models.Location.name,
    LocationCreate,
    "location",
    used_by=[models.JobLocation.loc_id, models.CompanyLocation.loc_id],
)
work_modes_router = create_lookup_router(
    models.WorkMode,
    models.WorkMode.work_mode_id,
    models.WorkMode.name,
    WorkModeCreate,
    "work mode",
    used_by=[models.JobWorkMode.work_mode_id],
)
skills_router = create_lookup_router(
    models.Skill,
    models.Skill.skill_id,
    models.Skill.skill_name,
    SkillCreate,
    "skill",
    used_by=[models.JobSkill.skill_id],
)
education_router = create_lookup_router(
    models.EducationRequirement,
    models.EducationRequirement.education_id,
    models.EducationRequirement.education_name,
    EducationCreate,
    "education requirement",
    used_by=[models.JobEducation.education_id],
)
sources_router = create_lookup_router(
    models.Source,
    models.Source.source_id,
    models.Source.source_name,
    SourceCreate,
    "source",
    used_by=[models.JobSource.source_id],
)
