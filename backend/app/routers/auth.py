from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import _health
from ..database import get_db
from ..models import User
from ..schemas import LoginRequest, TokenResponse, UserOut
from ..security import create_access_token, get_current_user, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    # Honor X-Forwarded-For only when behind a trusted proxy in production deployments.
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    ip = _client_ip(request)
    email = (payload.email or "").lower().strip()
    keys = (f"ip:{ip}", f"email:{email}")
    for key in keys:
        locked = _health.login_check(key)
        if locked is not None:
            raise HTTPException(
                status_code=429,
                detail=f"For mange mislykkede forsøk. Prøv igjen om {int(locked // 60) + 1} min.",
            )

    user = db.query(User).filter(User.email == email, User.is_active.is_(True)).first()
    if not user or not verify_password(payload.password, user.password_hash):
        for key in keys:
            _health.login_record_failure(key)
        # Constant-time-ish: identical message regardless of whether user exists.
        raise HTTPException(status_code=401, detail="Feil e-post eller passord")

    for key in keys:
        _health.login_record_success(key)
    user.last_login_at = datetime.utcnow()
    db.commit()
    token = create_access_token(user)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
