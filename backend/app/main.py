from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from jose import JWTError, jwt
import os

from .config import settings
from .database import SessionLocal
from .models import Tenant, UserRole
from .routers import admin, auth, customers, dashboard, jobs, locations, parts, super_admin
from .seed import init_db

app = FastAPI(title="GVK – Gullsmed Verksted & Kundekontroll", version="0.1.0")

# --- CORS: in dev allow vite localhost; in prod use explicit allow-list ---
if settings.ENVIRONMENT.lower() == "production":
    cors_origins = settings.cors_origins_list
else:
    cors_origins = [
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:5174", "http://127.0.0.1:5174",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
    max_age=600,
)

# --- Trusted host (defense against Host header injection) ---
if settings.trusted_hosts_list:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts_list)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds standard hardening headers to every response."""
    async def dispatch(self, request: Request, call_next):
        try:
            response: Response = await call_next(request)
        except Exception:
            raise
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=(), payment=()",
        )
        # Only enable HSTS over actual HTTPS (avoid breaking local http dev).
        if request.url.scheme == "https":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=63072000; includeSubDomains; preload",
            )
        return response


app.add_middleware(SecurityHeadersMiddleware)


# --- Module gating ---
# Maps a URL prefix to the tenant module that must be enabled to access it.
_MODULE_PREFIXES: list[tuple[str, str]] = [
    ("/api/jobs", "module_workshop"),
    ("/api/parts", "module_workshop"),
    ("/api/locations", "module_workshop"),
    # ("/api/shop", "module_shop"),  # når POS-API kommer
]

_OPEN_PREFIXES = ("/api/auth", "/api/health", "/api/super", "/uploads", "/api/admin", "/api/dashboard", "/api/customers")


class TenantModuleMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith("/api/"):
            return await call_next(request)
        if path.startswith(_OPEN_PREFIXES):
            return await call_next(request)
        # Find which module (if any) gates this prefix
        gate = next((mod for prefix, mod in _MODULE_PREFIXES if path.startswith(prefix)), None)
        if not gate:
            return await call_next(request)
        # Decode token to find tenant — if no token, let auth dependency reject normally.
        auth_header = request.headers.get("authorization", "")
        if not auth_header.lower().startswith("bearer "):
            return await call_next(request)
        token = auth_header.split(" ", 1)[1].strip()
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            tid = int(payload.get("tid"))
            role = payload.get("role")
        except (JWTError, ValueError, TypeError):
            return await call_next(request)
        if role == UserRole.superadmin.value:
            return await call_next(request)
        db = SessionLocal()
        try:
            tenant = db.query(Tenant).filter(Tenant.id == tid).first()
            if tenant and not getattr(tenant, gate, True):
                return JSONResponse(
                    status_code=403,
                    content={"detail": f"Modul '{gate}' er ikke aktivert for denne tenant"},
                )
            if tenant and not tenant.is_active:
                return JSONResponse(status_code=403, content={"detail": "Tenant er deaktivert"})
        finally:
            db.close()
        return await call_next(request)


app.add_middleware(TenantModuleMiddleware)

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    # Kick a background sweep so dashboard is fresh as soon as superadmin opens it.
    try:
        from . import _health
        _health.refresh_all_async()
    except Exception:
        pass


@app.get("/api/health")
def health():
    return {"status": "ok", "env": settings.ENVIRONMENT}


app.include_router(auth.router, prefix="/api")
app.include_router(customers.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(parts.router, prefix="/api")
app.include_router(locations.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(super_admin.router, prefix="/api")
