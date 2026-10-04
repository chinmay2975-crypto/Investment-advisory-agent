from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.db.models import Investor
from app.db.session import get_db
from app.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_investor(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> Investor:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise credentials_exception
        investor_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise credentials_exception

    investor = db.get(Investor, investor_id)
    if investor is None:
        raise credentials_exception
    return investor


def require_self(investor_id: int, current_investor: Investor = Depends(get_current_investor)) -> Investor:
    """Route dependency ensuring the authenticated investor matches the {investor_id} in the path.

    Every investor-scoped router should depend on this so one investor's token can never be
    used to read or write another investor's data.
    """
    if current_investor.id != investor_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this investor's data")
    return current_investor
