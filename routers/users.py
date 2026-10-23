from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import models
from database import get_db
from routers.helpers import commit_or_raise_conflict, ensure_email_available, ensure_username_available, get_user_or_404
from schemas import ApplicationResponse, UserCreate, UserResponse, UserUpdate


router = APIRouter()


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(user_data: UserCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    await ensure_username_available(user_data.username, db)
    await ensure_email_available(user_data.email, db)
    user = models.User(username=user_data.username, email=user_data.email.lower())
    db.add(user)
    await commit_or_raise_conflict(db)
    await db.refresh(user)
    return user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    return await get_user_or_404(user_id, db)


@router.get("/{user_id}/applications", response_model=list[ApplicationResponse])
async def get_user_applications(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    await get_user_or_404(user_id, db)
    result = await db.execute(
        select(models.Application)
        .where(models.Application.user_id == user_id)
        .order_by(models.Application.date_applied.desc())
    )
    return result.scalars().all()


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(user_id: int, user_data: UserUpdate, db: Annotated[AsyncSession, Depends(get_db)]):
    user = await get_user_or_404(user_id, db)
    values = user_data.model_dump(exclude_unset=True)
    if "username" in values:
        await ensure_username_available(values["username"], db, user.id)
    if "email" in values:
        await ensure_email_available(values["email"], db, user.id)
        values["email"] = values["email"].lower()
    for field, value in values.items():
        setattr(user, field, value)
    await commit_or_raise_conflict(db)
    await db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    user = await get_user_or_404(user_id, db)
    await db.delete(user)
    await commit_or_raise_conflict(db)
