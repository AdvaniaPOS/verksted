from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import User, UserRole

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user: User, *, impersonator_id: Optional[int] = None, minutes: Optional[int] = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user.id),
        "tid": user.tenant_id,
        "role": user.role.value,
        "exp": expire,
    }
    if impersonator_id is not None:
        payload["imp"] = impersonator_id
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    creds_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Ikke autentisert",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise creds_exc
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = int(payload.get("sub"))
    except (JWTError, ValueError, TypeError):
        raise creds_exc
    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        raise creds_exc
    # Stash impersonator on the user object (transient, not saved) so endpoints can read it.
    user.__dict__["_impersonator_id"] = payload.get("imp")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role not in (UserRole.admin, UserRole.superadmin):
        raise HTTPException(status_code=403, detail="Krever admin-rolle")
    return user


def require_superadmin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.superadmin:
        raise HTTPException(status_code=403, detail="Krever superadmin-rolle")
    return user
