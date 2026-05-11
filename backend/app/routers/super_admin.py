"""Superadmin router – manage tenants across the platform.

Inspirert av BikeDesk: én plattform med flere tenants, og hver tenant kan
ha verksted- og/eller butikk-modul aktiv. Superadmin (rolle = superadmin)
kan opprette, redigere og deaktivere tenants, sette Susoft-config per tenant
samt 'impersonate' en tenant-admin for feilsøking.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import _health
from ..crypto import encrypt
from ..database import get_db
from ..models import (
    AuditLog, Customer, Job, PrinterConfig, SusoftConfig, Tenant, User, UserRole,
)
from ..schemas import (
    ImpersonateOut, SusoftConfigIn, SusoftConfigOut, TenantCreate,
    TenantStatsOut, TenantUpdate, UserCreate, UserOut,
)
from ..security import (
    create_access_token, get_current_user, hash_password, require_superadmin,
)

router = APIRouter(prefix="/super", tags=["super"])


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _tenant_stats(db: Session, t: Tenant) -> dict:
    return {
        "id": t.id, "name": t.name, "slug": t.slug,
        "is_active": t.is_active, "plan": t.plan,
        "module_workshop": t.module_workshop, "module_shop": t.module_shop,
        "user_count": db.query(User).filter(User.tenant_id == t.id).count(),
        "job_count": db.query(Job).filter(Job.tenant_id == t.id).count(),
        "customer_count": db.query(Customer).filter(Customer.tenant_id == t.id).count(),
        "created_at": t.created_at or datetime.utcnow(),
    }


# ---------- Tenants ----------
@router.get("/tenants", response_model=List[TenantStatsOut])
def list_tenants(
    db: Session = Depends(get_db), _: User = Depends(require_superadmin),
):
    rows = db.query(Tenant).order_by(Tenant.created_at.desc()).all()
    return [_tenant_stats(db, t) for t in rows]


@router.get("/dashboard")
def super_dashboard(
    db: Session = Depends(get_db), _: User = Depends(require_superadmin),
):
    """Live status board: én rad per tenant med online/Susoft-status.

    Susoft-status er cached i ~60s (raskere retry ved feil) for å unngå at
    dashboardet fyrer av et REST-kall til Susoft per tenant ved hver refresh.
    """
    rows = db.query(Tenant).order_by(Tenant.name.asc()).all()
    out = []
    for t in rows:
        cfg = db.query(SusoftConfig).filter(SusoftConfig.tenant_id == t.id).one_or_none()
        h = _health.get_health(t.id)
        last_login = (
            db.query(User.last_login_at)
            .filter(User.tenant_id == t.id, User.last_login_at.isnot(None))
            .order_by(User.last_login_at.desc())
            .first()
        )
        out.append({
            "id": t.id,
            "name": t.name,
            "slug": t.slug,
            "is_active": t.is_active,
            "plan": t.plan,
            "module_workshop": t.module_workshop,
            "module_shop": t.module_shop,
            "user_count": db.query(User).filter(User.tenant_id == t.id).count(),
            "job_count": db.query(Job).filter(Job.tenant_id == t.id).count(),
            "customer_count": db.query(Customer).filter(Customer.tenant_id == t.id).count(),
            "last_login_at": last_login[0].isoformat() if last_login and last_login[0] else None,
            "susoft_configured": bool(cfg and cfg.is_active),
            "susoft_ok": h.ok,  # True | False | None (ikke konfigurert)
            "susoft_error": h.error,
            "susoft_checked_at": datetime.utcfromtimestamp(h.checked_at).isoformat() if h.checked_at else None,
            "susoft_consecutive_failures": h.consecutive_failures,
            "created_at": (t.created_at or datetime.utcnow()).isoformat(),
        })
    return out


@router.post("/tenants", response_model=TenantStatsOut, status_code=201)
def create_tenant(
    payload: TenantCreate,
    db: Session = Depends(get_db), _: User = Depends(require_superadmin),
):
    slug = payload.slug.strip().lower()
    if not slug:
        raise HTTPException(400, "Slug kreves")
    if db.query(Tenant).filter(Tenant.slug == slug).first():
        raise HTTPException(409, f"Slug '{slug}' er allerede i bruk")
    t = Tenant(
        name=payload.name.strip(),
        slug=slug,
        plan=payload.plan,
        module_workshop=payload.module_workshop,
        module_shop=payload.module_shop,
    )
    db.add(t)
    db.flush()
    admin = User(
        tenant_id=t.id,
        email=payload.admin_email.lower(),
        name=payload.admin_name.strip(),
        password_hash=hash_password(payload.admin_password),
        role=UserRole.admin,
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(t)
    return _tenant_stats(db, t)


@router.get("/tenants/{tenant_id}", response_model=TenantStatsOut)
def get_tenant(
    tenant_id: int,
    db: Session = Depends(get_db), _: User = Depends(require_superadmin),
):
    t = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not t:
        raise HTTPException(404, "Tenant ikke funnet")
    return _tenant_stats(db, t)


@router.patch("/tenants/{tenant_id}", response_model=TenantStatsOut)
def update_tenant(
    tenant_id: int, payload: TenantUpdate,
    db: Session = Depends(get_db), _: User = Depends(require_superadmin),
):
    t = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not t:
        raise HTTPException(404, "Tenant ikke funnet")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(t, k, v)
    db.commit()
    db.refresh(t)
    return _tenant_stats(db, t)


# ---------- Users in a tenant ----------
@router.get("/tenants/{tenant_id}/users", response_model=List[UserOut])
def list_tenant_users(
    tenant_id: int,
    db: Session = Depends(get_db), _: User = Depends(require_superadmin),
):
    rows = db.query(User).filter(User.tenant_id == tenant_id).order_by(User.created_at.desc()).all()
    return rows


@router.post("/tenants/{tenant_id}/users", response_model=UserOut, status_code=201)
def create_tenant_user(
    tenant_id: int, payload: UserCreate,
    db: Session = Depends(get_db), _: User = Depends(require_superadmin),
):
    t = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not t:
        raise HTTPException(404, "Tenant ikke funnet")
    if db.query(User).filter(User.tenant_id == t.id, User.email == payload.email.lower()).first():
        raise HTTPException(409, "E-post finnes allerede i denne tenanten")
    u = User(
        tenant_id=t.id, email=payload.email.lower(), name=payload.name.strip(),
        password_hash=hash_password(payload.password), role=payload.role, is_active=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


# ---------- Impersonate ----------
@router.post("/tenants/{tenant_id}/impersonate", response_model=ImpersonateOut)
def impersonate(
    tenant_id: int, request: Request,
    db: Session = Depends(get_db), me: User = Depends(require_superadmin),
):
    """Issue a short-lived (60 min) token as the first admin of the given tenant.

    Returns the original superadmin user as `user.tenant` etc, but the new token
    is scoped to the tenant admin so all standard endpoints behave as that user.
    """
    target = (
        db.query(User)
        .filter(User.tenant_id == tenant_id, User.role == UserRole.admin, User.is_active.is_(True))
        .order_by(User.created_at.asc())
        .first()
    )
    if not target:
        raise HTTPException(404, "Fant ingen aktiv admin for denne tenanten")
    token = create_access_token(target, impersonator_id=me.id, minutes=60)
    db.add(AuditLog(
        actor_user_id=me.id, target_user_id=target.id, target_tenant_id=tenant_id,
        action="impersonate.start", ip=_client_ip(request),
        detail=f"superadmin {me.email} → {target.email}",
    ))
    db.commit()
    return ImpersonateOut(access_token=token, user=UserOut.model_validate(target))


# ---------- Susoft per tenant ----------
@router.get("/tenants/{tenant_id}/susoft", response_model=SusoftConfigOut)
def get_tenant_susoft(
    tenant_id: int,
    db: Session = Depends(get_db), _: User = Depends(require_superadmin),
):
    cfg = db.query(SusoftConfig).filter(SusoftConfig.tenant_id == tenant_id).one_or_none()
    if not cfg:
        return SusoftConfigOut()
    return SusoftConfigOut(
        base_url=cfg.base_url, shop_url_key=cfg.shop_url_key, login=cfg.login,
        has_password=bool(cfg.password_enc), auto_create_order=cfg.auto_create_order,
        is_active=cfg.is_active, last_test_at=cfg.last_test_at,
        last_test_ok=cfg.last_test_ok, last_test_error=cfg.last_test_error,
    )


@router.put("/tenants/{tenant_id}/susoft", response_model=SusoftConfigOut)
def set_tenant_susoft(
    tenant_id: int, payload: SusoftConfigIn,
    db: Session = Depends(get_db), _: User = Depends(require_superadmin),
):
    if not db.query(Tenant).filter(Tenant.id == tenant_id).first():
        raise HTTPException(404, "Tenant ikke funnet")
    cfg = db.query(SusoftConfig).filter(SusoftConfig.tenant_id == tenant_id).one_or_none()
    if not cfg:
        if not payload.password:
            raise HTTPException(400, "Passord kreves ved første konfigurasjon")
        cfg = SusoftConfig(
            tenant_id=tenant_id,
            base_url=(payload.base_url or "https://api.susoft.com:4443").rstrip("/"),
            shop_url_key=payload.shop_url_key, login=payload.login,
            password_enc=encrypt(payload.password),
            auto_create_order=payload.auto_create_order, is_active=payload.is_active,
        )
        db.add(cfg)
    else:
        cfg.base_url = (payload.base_url or cfg.base_url or "https://api.susoft.com:4443").rstrip("/")
        cfg.shop_url_key = payload.shop_url_key
        cfg.login = payload.login
        if payload.password:
            cfg.password_enc = encrypt(payload.password)
        cfg.auto_create_order = payload.auto_create_order
        cfg.is_active = payload.is_active
    db.commit()
    db.refresh(cfg)
    # Force fresh health check next time
    _health.get_health(tenant_id, force=True)
    return SusoftConfigOut(
        base_url=cfg.base_url, shop_url_key=cfg.shop_url_key, login=cfg.login,
        has_password=bool(cfg.password_enc), auto_create_order=cfg.auto_create_order,
        is_active=cfg.is_active, last_test_at=cfg.last_test_at,
        last_test_ok=cfg.last_test_ok, last_test_error=cfg.last_test_error,
    )


@router.post("/tenants/{tenant_id}/susoft/test")
def test_tenant_susoft(
    tenant_id: int,
    _: User = Depends(require_superadmin),
):
    """Tving en frisk Susoft-test (omgår cache). Brukes av dashboardet."""
    h = _health.get_health(tenant_id, force=True)
    return {
        "ok": h.ok,
        "error": h.error,
        "checked_at": datetime.utcfromtimestamp(h.checked_at).isoformat() if h.checked_at else None,
        "consecutive_failures": h.consecutive_failures,
    }


# ---------- Audit log ----------
@router.get("/audit")
def list_audit(
    limit: int = 200,
    db: Session = Depends(get_db), _: User = Depends(require_superadmin),
):
    rows = (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(min(limit, 1000))
        .all()
    )
    return [
        {
            "id": r.id, "created_at": r.created_at.isoformat() if r.created_at else None,
            "actor_user_id": r.actor_user_id, "target_user_id": r.target_user_id,
            "target_tenant_id": r.target_tenant_id, "action": r.action,
            "ip": r.ip, "detail": r.detail,
        } for r in rows
    ]
