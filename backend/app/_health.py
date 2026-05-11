"""In-memory health & rate-limit utilities.

For a production deployment with multiple workers this should move to Redis,
but for a single-uvicorn deployment a process-local cache is enough and avoids
hammering Susoft.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import SusoftConfig, Tenant
from .susoft import SusoftClient, SusoftError, _TOKEN_CACHE

log = logging.getLogger("gvk.health")

# How often to actively re-check Susoft when fetching dashboard.
SUSOFT_CHECK_INTERVAL_S = 60.0
# After a failure, retry quicker (auto-recovery)
SUSOFT_RETRY_INTERVAL_S = 20.0


@dataclass
class SusoftHealth:
    ok: Optional[bool] = None  # None = never checked / not configured
    error: Optional[str] = None
    checked_at: float = 0.0
    next_attempt_at: float = 0.0
    consecutive_failures: int = 0


_lock = threading.Lock()
_state: dict[int, SusoftHealth] = {}  # tenant_id -> SusoftHealth


def _check_one(db: Session, tenant_id: int) -> SusoftHealth:
    h = _state.setdefault(tenant_id, SusoftHealth())
    cfg = db.query(SusoftConfig).filter(SusoftConfig.tenant_id == tenant_id).one_or_none()
    if not cfg or not cfg.is_active:
        h.ok = None
        h.error = None
        h.checked_at = time.time()
        h.next_attempt_at = time.time() + SUSOFT_CHECK_INTERVAL_S
        return h
    try:
        with SusoftClient(cfg) as c:
            ok = c.health() or bool(c.shop_info())
        h.ok = bool(ok)
        h.error = None if ok else "Susoft svarte uten data"
        h.consecutive_failures = 0 if ok else h.consecutive_failures + 1
    except SusoftError as e:
        # auto-recovery: drop cached token to force re-auth on next attempt
        _TOKEN_CACHE.pop(tenant_id, None)
        h.ok = False
        h.error = str(e)[:300]
        h.consecutive_failures += 1
        log.warning("Susoft health failed for tenant %s: %s", tenant_id, h.error)
    except Exception as e:  # network / dns / unexpected
        _TOKEN_CACHE.pop(tenant_id, None)
        h.ok = False
        h.error = f"{type(e).__name__}: {str(e)[:200]}"
        h.consecutive_failures += 1
        log.warning("Susoft health crashed for tenant %s: %s", tenant_id, h.error)
    h.checked_at = time.time()
    interval = SUSOFT_RETRY_INTERVAL_S if h.ok is False else SUSOFT_CHECK_INTERVAL_S
    h.next_attempt_at = time.time() + interval
    # Persist last result
    if cfg is not None:
        from datetime import datetime
        cfg.last_test_at = datetime.utcnow()
        cfg.last_test_ok = h.ok
        cfg.last_test_error = h.error
        db.commit()
    return h


def get_health(tenant_id: int, *, force: bool = False) -> SusoftHealth:
    with _lock:
        h = _state.get(tenant_id)
        now = time.time()
        if not force and h and now < h.next_attempt_at:
            return h
        db = SessionLocal()
        try:
            return _check_one(db, tenant_id)
        finally:
            db.close()


def refresh_all_async() -> None:
    """Kick off a background sweep of all configured tenants."""
    def _run():
        db = SessionLocal()
        try:
            ids = [t.id for t in db.query(Tenant).filter(Tenant.is_active.is_(True)).all()]
        finally:
            db.close()
        for tid in ids:
            try:
                get_health(tid, force=True)
            except Exception:  # pragma: no cover
                log.exception("refresh_all failed for tenant %s", tid)
    threading.Thread(target=_run, daemon=True).start()


# ---- Login throttling ----
@dataclass
class _LoginBucket:
    failures: int = 0
    locked_until: float = 0.0
    last_failure: float = 0.0


_login_lock = threading.Lock()
_login_state: dict[str, _LoginBucket] = {}

LOGIN_MAX_FAILURES = 5
LOGIN_LOCKOUT_SECONDS = 15 * 60
LOGIN_FAILURE_WINDOW_S = 15 * 60


def login_check(key: str) -> Optional[float]:
    """Returns seconds-remaining if the key is currently locked, else None."""
    with _login_lock:
        b = _login_state.get(key)
        if not b:
            return None
        now = time.time()
        if b.locked_until > now:
            return b.locked_until - now
        # reset window if last failure was long ago
        if b.last_failure and now - b.last_failure > LOGIN_FAILURE_WINDOW_S:
            b.failures = 0
        return None


def login_record_failure(key: str) -> None:
    with _login_lock:
        b = _login_state.setdefault(key, _LoginBucket())
        now = time.time()
        if b.last_failure and now - b.last_failure > LOGIN_FAILURE_WINDOW_S:
            b.failures = 0
        b.failures += 1
        b.last_failure = now
        if b.failures >= LOGIN_MAX_FAILURES:
            b.locked_until = now + LOGIN_LOCKOUT_SECONDS


def login_record_success(key: str) -> None:
    with _login_lock:
        _login_state.pop(key, None)
