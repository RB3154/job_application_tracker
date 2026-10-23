from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import models
from auth import create_access_token, get_current_user, hash_password, verify_password
from database import get_db
from routers.helpers import commit_or_raise_conflict, ensure_email_available, ensure_username_available
from schemas import Token, UserCreate, UserResponse, UserUpdate


router = APIRouter()

# Checked against when the email is unknown, so a login takes the same time whether or not the account exists.
DUMMY_PASSWORD_HASH = hash_password("dummy-password-for-timing")


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(user_data: UserCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    await ensure_username_available(user_data.username, db)
    await ensure_email_available(user_data.email, db)
    user = models.User(
        username=user_data.username,
        email=user_data.email.lower(),
        password_hash=hash_password(user_data.password),
    )
    db.add(user)
    await commit_or_raise_conflict(db)
    await db.refresh(user)
    return user


@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # OAuth2PasswordRequestForm calls the field "username", but users log in with their email.
    result = await db.execute(select(models.User).where(func.lower(models.User.email) == form_data.username.lower()))
    user = result.scalar_one_or_none()
    password_hash = user.password_hash if user else DUMMY_PASSWORD_HASH
    if not verify_password(form_data.password, password_hash) or user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_access_token(user.id), token_type="bearer")


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: Annotated[models.User, Depends(get_current_user)]):
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_me(
    user_data: UserUpdate,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    values = user_data.model_dump(exclude_unset=True)
    if "username" in values:
        await ensure_username_available(values["username"], db, current_user.id)
    if "email" in values:
        await ensure_email_available(values["email"], db, current_user.id)
        values["email"] = values["email"].lower()
    for field, value in values.items():
        setattr(current_user, field, value)
    await commit_or_raise_conflict(db)
    await db.refresh(current_user)
    return current_user


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await db.delete(current_user)
    await commit_or_raise_conflict(db)
