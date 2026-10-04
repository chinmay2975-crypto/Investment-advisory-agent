from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Investor
from app.db.session import get_db
from app.rate_limit import login_attempt_tracker
from app.schemas.auth import AccessTokenResponse, RefreshRequest, Token
from app.security import create_access_token, create_refresh_token, decode_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    key = form_data.username.strip().lower()

    if login_attempt_tracker.is_locked_out(key):
        raise HTTPException(
            status_code=429,
            detail=(
                f"Too many failed login attempts. Try again in "
                f"{settings.login_rate_limit_window_minutes} minutes."
            ),
        )

    investor = db.query(Investor).filter(Investor.email == form_data.username).first()
    if investor is None or not verify_password(form_data.password, investor.hashed_password):
        login_attempt_tracker.record_failure(key)
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    login_attempt_tracker.reset(key)
    access_token = create_access_token(subject=str(investor.id))
    refresh_token = create_refresh_token(subject=str(investor.id))
    return Token(access_token=access_token, refresh_token=refresh_token, investor_id=investor.id)


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    invalid_refresh_exception = HTTPException(status_code=401, detail="Invalid or expired refresh token")

    try:
        decoded = decode_token(payload.refresh_token)
        if decoded.get("type") != "refresh":
            raise invalid_refresh_exception
        investor_id = int(decoded["sub"])
    except (JWTError, KeyError, ValueError):
        raise invalid_refresh_exception

    investor = db.get(Investor, investor_id)
    if investor is None:
        raise invalid_refresh_exception

    return AccessTokenResponse(access_token=create_access_token(subject=str(investor.id)))
