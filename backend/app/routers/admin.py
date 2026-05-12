"""Admin router – per-tenant Susoft + Printer configuration."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..crypto import encrypt
from ..database import get_db
from ..models import PrinterConfig, SusoftConfig, User, UserRole
from ..netprint import NetworkPrintError, send_raw
from ..printing import INIT, LF, _enc
from ..schemas import (
    PrinterConfigIn,
    PrinterConfigOut,
    PrintTestResult,
    SusoftConfigIn,
    SusoftConfigOut,
    SusoftTestResult,
)
from ..security import get_current_user
from ..susoft import SusoftClient, SusoftError

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(user: User) -> None:
    if user.role != UserRole.admin:
        raise HTTPException(403, "Kun administrator har tilgang")


def _require_super_context(user: User) -> None:
    """Susoft-integrasjonen administreres av Susoft/Advania på vegne av tenant.
    Tilgang krever at innlogget bruker faktisk er super-admin som har impersonert
    seg inn på tenanten (JWT inneholder 'imp')."""
    if not getattr(user, "_impersonator_id", None):
        raise HTTPException(403, "Susoft-integrasjon administreres av Susoft-support")


def _get_susoft(db: Session, tenant_id: int) -> Optional[SusoftConfig]:
    return db.query(SusoftConfig).filter(SusoftConfig.tenant_id == tenant_id).one_or_none()


def _get_printer(db: Session, tenant_id: int) -> Optional[PrinterConfig]:
    return db.query(PrinterConfig).filter(PrinterConfig.tenant_id == tenant_id).one_or_none()


# ---------------- Susoft ----------------
@router.get("/susoft", response_model=SusoftConfigOut)
def get_susoft_config(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_admin(user)
    _require_super_context(user)
    cfg = _get_susoft(db, user.tenant_id)
    if not cfg:
        return SusoftConfigOut()
    return SusoftConfigOut(
        base_url=cfg.base_url,
        shop_url_key=cfg.shop_url_key,
        login=cfg.login,
        has_password=bool(cfg.password_enc),
        auto_create_order=cfg.auto_create_order,
        is_active=cfg.is_active,
        last_test_at=cfg.last_test_at,
        last_test_ok=cfg.last_test_ok,
        last_test_error=cfg.last_test_error,
    )


@router.put("/susoft", response_model=SusoftConfigOut)
def update_susoft_config(
    payload: SusoftConfigIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_admin(user)
    _require_super_context(user)
    cfg = _get_susoft(db, user.tenant_id)
    if not cfg:
        if not payload.password:
            raise HTTPException(400, "Passord kreves ved første konfigurasjon")
        cfg = SusoftConfig(
            tenant_id=user.tenant_id,
            base_url=(payload.base_url or "https://api.susoft.com:4443").rstrip("/"),
            shop_url_key=payload.shop_url_key,
            login=payload.login,
            password_enc=encrypt(payload.password),
            auto_create_order=payload.auto_create_order,
            is_active=payload.is_active,
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
    return SusoftConfigOut(
        base_url=cfg.base_url, shop_url_key=cfg.shop_url_key, login=cfg.login,
        has_password=bool(cfg.password_enc), auto_create_order=cfg.auto_create_order,
        is_active=cfg.is_active, last_test_at=cfg.last_test_at,
        last_test_ok=cfg.last_test_ok, last_test_error=cfg.last_test_error,
    )


@router.post("/susoft/test", response_model=SusoftTestResult)
def test_susoft(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_admin(user)
    _require_super_context(user)
    cfg = _get_susoft(db, user.tenant_id)
    if not cfg:
        raise HTTPException(400, "Susoft-konfigurasjon mangler")
    try:
        with SusoftClient(cfg) as client:
            info = client.shop_info() or {}
        cfg.last_test_at = datetime.utcnow()
        cfg.last_test_ok = True
        cfg.last_test_error = None
        db.commit()
        return SusoftTestResult(ok=True, message="Tilkobling OK", shop_name=info.get("shopName") or info.get("tenantName"))
    except SusoftError as e:
        cfg.last_test_at = datetime.utcnow()
        cfg.last_test_ok = False
        cfg.last_test_error = str(e)[:500]
        db.commit()
        return SusoftTestResult(ok=False, message=str(e))


# ---------------- Printer ----------------
@router.get("/printer", response_model=PrinterConfigOut)
def get_printer_config(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_admin(user)
    cfg = _get_printer(db, user.tenant_id)
    if not cfg:
        return PrinterConfigOut()
    return cfg


@router.put("/printer", response_model=PrinterConfigOut)
def update_printer_config(
    payload: PrinterConfigIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_admin(user)
    cfg = _get_printer(db, user.tenant_id)
    if not cfg:
        cfg = PrinterConfig(tenant_id=user.tenant_id, **payload.model_dump())
        db.add(cfg)
    else:
        for k, v in payload.model_dump().items():
            setattr(cfg, k, v)
    db.commit()
    db.refresh(cfg)
    return cfg


@router.post("/printer/test", response_model=PrintTestResult)
def test_printer(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_admin(user)
    cfg = _get_printer(db, user.tenant_id)
    if not cfg or not cfg.printer_host:
        raise HTTPException(400, "Skriverens IP/hostname er ikke satt")
    payload = (
        INIT
        + _enc("GVK -- testutskrift\n")
        + _enc(f"Skriver: {cfg.printer_host}:{cfg.printer_port}\n")
        + _enc("Hvis du leser dette, fungerer tilkoblingen.\n")
        + LF * 4
    )
    if cfg.cut_paper:
        from ..printing import CUT
        payload += CUT
    try:
        n = send_raw(cfg.printer_host, cfg.printer_port or 9100, payload, timeout=cfg.printer_timeout_s or 5)
        return PrintTestResult(ok=True, message="Testutskrift sendt", bytes_sent=n)
    except NetworkPrintError as e:
        return PrintTestResult(ok=False, message=str(e))
