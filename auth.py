import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash
from sqlalchemy.ext.asyncio import AsyncSession

import models
from config import settings
from database import get_db


password_hash = PasswordHash.recommended()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/token")


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def generate_reset_token() -> str:
    return secrets.token_urlsafe(32)


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key.get_secret_value(), algorithm=settings.algorithm)


def create_user_access_token(user: models.User) -> str:
    return create_access_token(data={"sub": str(user.id), "ver": user.token_version})


def verify_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=[settings.algorithm],
            options={"require": ["exp", "sub", "ver"]},
        )
    except jwt.InvalidTokenError:
        return None


async def user_from_token(token: str | None, db: AsyncSession) -> models.User | None:
    payload = verify_access_token(token) if token else None
    if payload is None:
        return None
    user_id = payload["sub"]
    if not isinstance(user_id, str) or not user_id.isdigit():
        return None
    user = await db.get(models.User, int(user_id))
    if user is None or payload["ver"] != user.token_version:
        return None
    return user


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> models.User:
    user = await user_from_token(token, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUser = Annotated[models.User, Depends(get_current_user)]


LOGIN_COOKIE = "access_token"


def set_login_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        LOGIN_COOKIE,
        token,
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )


def clear_login_cookie(response: Response) -> None:
    response.delete_cookie(LOGIN_COOKIE, path="/", httponly=True, samesite="lax", secure=settings.cookie_secure)


class LoginRequired(Exception):
    def __init__(self, next_url: str):
        self.next_url = next_url


async def get_page_user(request: Request, db: Annotated[AsyncSession, Depends(get_db)]) -> models.User:
    user = await user_from_token(request.cookies.get(LOGIN_COOKIE), db)
    if user is None:
        query = f"?{request.url.query}" if request.url.query else ""
        raise LoginRequired(next_url=request.url.path + query)
    return user


PageUser = Annotated[models.User, Depends(get_page_user)]
