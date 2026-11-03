import hashlib
from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return pwd_context.verify(password, hashed_password)


def password_version(hashed_password: str) -> str:
    """Short fingerprint of the stored hash. Tokens carrying it stop working once the password
    changes, which revokes refresh tokens and makes reset links single-use without a token table."""
    return hashlib.sha256(hashed_password.encode()).hexdigest()[:16]


def _create_token(subject: str, token_type: str, expires_delta: timedelta, pwv: str | None = None) -> str:
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode = {"sub": subject, "type": token_type, "exp": expire}
    if pwv:
        to_encode["pwv"] = pwv
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    return _create_token(
        subject,
        "access",
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(subject: str, expires_delta: timedelta | None = None, pwv: str | None = None) -> str:
    return _create_token(
        subject,
        "refresh",
        expires_delta or timedelta(days=settings.refresh_token_expire_days),
        pwv=pwv,
    )


def create_password_reset_token(subject: str, pwv: str) -> str:
    return _create_token(subject, "reset", timedelta(minutes=settings.password_reset_expire_minutes), pwv=pwv)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
