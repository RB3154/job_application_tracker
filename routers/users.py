from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, UploadFile, status
from fastapi.security import OAuth2PasswordRequestForm
from PIL import Image
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

import models
from auth import (
    CurrentUser,
    clear_login_cookie,
    create_user_access_token,
    generate_reset_token,
    hash_password,
    hash_reset_token,
    set_login_cookie,
    verify_password,
)
from config import settings
from database import get_db
from email_utils import send_password_reset_email
from image_utils import delete_profile_image, process_profile_image
from rate_limit import limiter
from routers.helpers import commit_or_raise_conflict, ensure_email_available, ensure_username_available
from schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    MessageResponse,
    PasswordChangedResponse,
    ResetPasswordRequest,
    Token,
    UserCreate,
    UserPrivate,
    UserUpdate,
)


router = APIRouter()

# Checked against when the email is unknown, so a login takes the same time whether or not the account exists.
DUMMY_PASSWORD_HASH = hash_password("dummy-password-for-timing")


@router.post("", response_model=UserPrivate, status_code=status.HTTP_201_CREATED)
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
# Slows down password guessing: each IP address gets 5 login attempts a minute.
@limiter.limit("5/minute")
async def login_for_access_token(
    request: Request,
    response: Response,
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
    access_token = create_user_access_token(user)
    # The same token as a cookie, so pages (not just API calls) know who is logged in.
    set_login_cookie(response, access_token)
    return Token(access_token=access_token, token_type="bearer")


@router.post("/session", status_code=status.HTTP_204_NO_CONTENT)
async def start_page_session(request: Request, response: Response, current_user: CurrentUser):
    """Copy a valid Bearer token into the login cookie.

    For browsers that logged in before pages needed the cookie: they have a token but no cookie.
    It needs the Authorization header, so another site can't trigger it.
    """

    set_login_cookie(response, request.headers["Authorization"].removeprefix("Bearer ").strip())


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response):
    """Remove the login cookie. The browser forgets its own copy of the token (localStorage) itself."""

    clear_login_cookie(response)


@router.post("/forgot-password", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED)
# Stops someone flooding an inbox with reset emails.
@limiter.limit("3/hour")
async def forgot_password(
    request: Request,
    request_data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # Housekeeping: remove every user's expired tokens, so links nobody clicked don't pile up forever.
    # Done for every request (known email or not), so the response time doesn't reveal who has an account.
    await db.execute(delete(models.PasswordResetToken).where(models.PasswordResetToken.expires_at < datetime.now(UTC)))
    await commit_or_raise_conflict(db)

    result = await db.execute(select(models.User).where(func.lower(models.User.email) == request_data.email.lower()))
    user = result.scalar_one_or_none()

    if user:
        # Only the newest link should work, so throw away any older tokens first.
        await db.execute(delete(models.PasswordResetToken).where(models.PasswordResetToken.user_id == user.id))

        token = generate_reset_token()
        db.add(
            models.PasswordResetToken(
                user_id=user.id,
                token_hash=hash_reset_token(token),
                expires_at=datetime.now(UTC) + timedelta(minutes=settings.reset_token_expire_minutes),
            )
        )
        await commit_or_raise_conflict(db)

        # Talking to the mail server is slow, so send the email after the response has gone out.
        background_tasks.add_task(send_password_reset_email, to_email=user.email, username=user.username, token=token)

    # Same answer whether or not the email exists, so nobody can use this to find out who has an account.
    return MessageResponse(
        message="If an account exists with this email, you will receive password reset instructions."
    )


@router.post("/reset-password", response_model=MessageResponse)
# Slows down guessing reset tokens.
@limiter.limit("5/minute")
async def reset_password(
    request: Request,
    request_data: ResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    invalid_token_error = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid or expired reset token",
    )

    result = await db.execute(
        select(models.PasswordResetToken).where(
            models.PasswordResetToken.token_hash == hash_reset_token(request_data.token)
        )
    )
    reset_token = result.scalar_one_or_none()
    if reset_token is None:
        raise invalid_token_error

    if reset_token.expires_at < datetime.now(UTC):
        await db.delete(reset_token)
        await commit_or_raise_conflict(db)
        raise invalid_token_error

    user = await db.get(models.User, reset_token.user_id)
    if user is None:
        raise invalid_token_error

    user.password_hash = hash_password(request_data.new_password)
    # Log out every device that was using the old password.
    user.token_version += 1
    # A token works only once: delete it (and any others) now that the password has changed.
    await db.execute(delete(models.PasswordResetToken).where(models.PasswordResetToken.user_id == user.id))
    await commit_or_raise_conflict(db)
    return MessageResponse(message="Password reset successfully. You can now log in with your new password.")


@router.get("/me", response_model=UserPrivate)
async def get_me(current_user: CurrentUser):
    return current_user


@router.patch("/me", response_model=UserPrivate)
async def update_me(
    user_data: UserUpdate,
    current_user: CurrentUser,
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


@router.patch("/me/password", response_model=PasswordChangedResponse)
async def change_my_password(
    password_data: ChangePasswordRequest,
    response: Response,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if not verify_password(password_data.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    current_user.password_hash = hash_password(password_data.new_password)
    # Log out other devices; this one stays logged in with the new token returned below.
    current_user.token_version += 1
    # Any reset link sent earlier shouldn't still work after the password changed.
    await db.execute(delete(models.PasswordResetToken).where(models.PasswordResetToken.user_id == current_user.id))
    await commit_or_raise_conflict(db)
    access_token = create_user_access_token(current_user)
    # The old cookie stopped working with the old token; replace it so pages keep working here.
    set_login_cookie(response, access_token)
    return PasswordChangedResponse(
        message="Password changed successfully", access_token=access_token, token_type="bearer"
    )


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    old_filename = current_user.image_file
    await db.delete(current_user)
    await commit_or_raise_conflict(db)
    delete_profile_image(old_filename)


@router.patch("/me/picture", response_model=UserPrivate)
async def upload_my_picture(
    file: UploadFile,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # Read one byte past the limit: enough to tell the file is too big without loading all of it into memory.
    content = await file.read(settings.max_upload_size_bytes + 1)
    if len(content) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size is {settings.max_upload_size_bytes // (1024 * 1024)}MB",
        )

    # Resizing an image is slow CPU work, so run it in a thread instead of blocking the event loop.
    try:
        new_filename = await run_in_threadpool(process_profile_image, content)
    except Image.DecompressionBombError as exception:
        # A small file that unpacks into a gigantic picture, which would use up the server's memory.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image dimensions are too large. Please upload a smaller image.",
        ) from exception
    except OSError as exception:
        # Not an image at all (UnidentifiedImageError is a kind of OSError), or a cut-off/corrupt image file.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image file. Please upload a valid image (JPEG, PNG, GIF, WebP).",
        ) from exception

    old_filename = current_user.image_file
    current_user.image_file = new_filename
    await commit_or_raise_conflict(db)
    await db.refresh(current_user)
    # Remove the old file only after the database points at the new one.
    delete_profile_image(old_filename)
    return current_user


@router.delete("/me/picture", response_model=UserPrivate)
async def delete_my_picture(current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    old_filename = current_user.image_file
    if old_filename is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No profile picture to delete")

    current_user.image_file = None
    await commit_or_raise_conflict(db)
    await db.refresh(current_user)
    delete_profile_image(old_filename)
    return current_user
