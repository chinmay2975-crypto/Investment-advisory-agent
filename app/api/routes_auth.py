from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Investor
from app.db.session import get_db
from app.rate_limit import login_attempt_tracker
from app.dependencies import get_current_investor
from app.schemas.auth import (
    AccessTokenResponse,
    ChangePasswordRequest,
    DeleteAccountRequest,
    ForgotPasswordRequest,
    RefreshRequest,
    ResetPasswordRequest,
    Token,
)
from app.services import account
from app.security import (
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_token,
    hash_password,
    password_version,
    verify_password,
)

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
    refresh_token = create_refresh_token(subject=str(investor.id), pwv=password_version(investor.hashed_password))
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
    if investor is None or decoded.get("pwv") != password_version(investor.hashed_password):
        raise invalid_refresh_exception  # unknown user, or the password changed since this token was issued

    return AccessTokenResponse(access_token=create_access_token(subject=str(investor.id)))


def _issue_tokens(investor: Investor) -> Token:
    return Token(
        access_token=create_access_token(subject=str(investor.id)),
        refresh_token=create_refresh_token(subject=str(investor.id), pwv=password_version(investor.hashed_password)),
        investor_id=investor.id,
    )


@router.post("/change-password", response_model=Token)
def change_password(
    payload: ChangePasswordRequest,
    investor: Investor = Depends(get_current_investor),
    db: Session = Depends(get_db),
):
    """Returns fresh tokens; refresh tokens issued before the change stop working."""
    if not verify_password(payload.current_password, investor.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="New password must be different from the current one")
    investor.hashed_password = hash_password(payload.new_password)
    db.commit()
    return _issue_tokens(investor)


@router.post("/forgot-password", status_code=202)
def forgot_password(payload: ForgotPasswordRequest, background: BackgroundTasks, db: Session = Depends(get_db)):
    """Always 202 when e-mail is configured, whether or not the address has an account,
    so the endpoint can't be used to discover who is registered."""
    if not account.email_enabled():
        raise HTTPException(status_code=503, detail="Password reset by e-mail is not configured on this server")
    investor = db.query(Investor).filter(func.lower(Investor.email) == payload.email.strip().lower()).first()
    if investor is not None:
        token = create_password_reset_token(str(investor.id), password_version(investor.hashed_password))
        background.add_task(account.send_password_reset_email, investor.email, token)
    return {"detail": "If that address has an account, a reset link is on its way."}


@router.post("/reset-password", response_model=Token)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    invalid = HTTPException(status_code=400, detail="This reset link is invalid or has expired")
    try:
        decoded = decode_token(payload.token)
        if decoded.get("type") != "reset":
            raise invalid
        investor = db.get(Investor, int(decoded["sub"]))
    except (JWTError, KeyError, ValueError):
        raise invalid
    if investor is None or decoded.get("pwv") != password_version(investor.hashed_password):
        raise invalid  # already used (password changed since) or account gone
    investor.hashed_password = hash_password(payload.new_password)
    db.commit()
    login_attempt_tracker.reset(investor.email.strip().lower())
    return _issue_tokens(investor)


@router.post("/delete-account", status_code=204)
def delete_account(
    payload: DeleteAccountRequest,
    investor: Investor = Depends(get_current_investor),
    db: Session = Depends(get_db),
):
    """Permanently deletes the account and all its goals, holdings, recommendations and history."""
    if not verify_password(payload.password, investor.hashed_password):
        raise HTTPException(status_code=400, detail="Password is incorrect")
    account.delete_investor_account(db, investor)
    return Response(status_code=204)


@router.get("/features")
def auth_features():
    """Lets the UI hide "Forgot password?" when the server can't send e-mail."""
    return {"password_reset_email": account.email_enabled()}
