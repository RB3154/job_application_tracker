"""Password hashing, JWT access tokens, password reset tokens, the login cookie and the current-user dependencies."""

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
    """Create a random, URL-safe token that is emailed to the user."""

    return secrets.token_urlsafe(32)


def hash_reset_token(token: str) -> str:
    """Hash a reset token for storing/looking up in the database.

    SHA-256 (not argon2) is fine here: the token is long and random, so it can't be guessed,
    and a fast hash lets us find the row with a simple WHERE token_hash = ... query.
    """

    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token from the given claims (e.g. {"sub": user id})."""

    to_encode = data.copy()
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key.get_secret_value(), algorithm=settings.algorithm)


def create_user_access_token(user: models.User) -> str:
    """Create a login token for the user, stamped with their current token_version."""

    return create_access_token(data={"sub": str(user.id), "ver": user.token_version})


def verify_access_token(token: str) -> dict | None:
    """Verify a JWT access token and return its claims (e.g. "sub" user id, "ver" token version) if valid."""

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
    """Return the user a token belongs to, or None if it is missing, invalid, expired or outdated."""

    payload = verify_access_token(token) if token else None
    if payload is None:
        return None
    user_id = payload["sub"]
    if not isinstance(user_id, str) or not user_id.isdigit():
        return None
    user = await db.get(models.User, int(user_id))
    # A different version means the password changed after this token was made, so it no longer counts.
    if user is None or payload["ver"] != user.token_version:
        return None
    return user


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> models.User:
    """API routes: return the user from the "Authorization: Bearer" token, or raise 401."""

    user = await user_from_token(token, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUser = Annotated[models.User, Depends(get_current_user)]


# ---------- Login cookie (for HTML pages) ----------
#
# The JavaScript keeps the token in localStorage and sends it to the API in the Authorization header.
# The browser doesn't send localStorage when it asks for a *page*, so login also stores the same token
# in a cookie. Only page routes read the cookie; API routes keep requiring the header, so another site
# can't make the browser call the API with the user's cookie (CSRF).

LOGIN_COOKIE = "access_token"


def set_login_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        LOGIN_COOKIE,
        token,
        max_age=settings.access_token_expire_minutes * 60,  # expires together with the token
        httponly=True,  # JavaScript can't read it, so an XSS bug can't steal it from the cookie
        samesite="lax",  # not sent when another site embeds or posts to this one
        secure=settings.cookie_secure,
        path="/",
    )


def clear_login_cookie(response: Response) -> None:
    response.delete_cookie(LOGIN_COOKIE, path="/", httponly=True, samesite="lax", secure=settings.cookie_secure)


class LoginRequired(Exception):
    """Raised by page routes when nobody is logged in; main.py turns it into a redirect to /login."""

    def __init__(self, next_url: str):
        self.next_url = next_url


async def get_page_user(request: Request, db: Annotated[AsyncSession, Depends(get_db)]) -> models.User:
    """Page routes: return the user from the login cookie, or send the browser to the login page."""

    user = await user_from_token(request.cookies.get(LOGIN_COOKIE), db)
    if user is None:
        query = f"?{request.url.query}" if request.url.query else ""
        raise LoginRequired(next_url=request.url.path + query)
    return user


PageUser = Annotated[models.User, Depends(get_page_user)]
