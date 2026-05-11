from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from .config import settings
from .database import Base, SessionLocal, engine
from .models import Tenant, User, UserRole
from .security import hash_password


# Lightweight in-place migrations for SQLite (Base.metadata.create_all doesn't
# add new columns to existing tables). Add (table, column, ddl) entries here
# whenever a column is introduced after initial release.
_COLUMN_MIGRATIONS: list[tuple[str, str, str]] = [
    ("printer_configs", "printer_host", "VARCHAR(120)"),
    ("printer_configs", "printer_port", "INTEGER DEFAULT 9100"),
    ("printer_configs", "printer_timeout_s", "INTEGER DEFAULT 5"),
    # Material flow + verkstedfelter (lagt til i v2)
    ("jobs", "weight_in_g", "NUMERIC(10,3)"),
    ("jobs", "weight_out_g", "NUMERIC(10,3)"),
    ("jobs", "storage_location", "VARCHAR(120)"),
    ("jobs", "qc_checklist", "TEXT"),
    ("jobs", "internal_notes", "TEXT"),
    # v3 — utpris på deler + kvittering-flagg på tidsregistrering
    ("part_orders", "sale_price", "NUMERIC(12,2)"),
    ("job_time_entries", "show_on_receipt", "BOOLEAN DEFAULT 0 NOT NULL"),
    # v4 — tenant aktivering, plan og moduler
    ("tenants", "is_active", "BOOLEAN DEFAULT 1 NOT NULL"),
    ("tenants", "plan", "VARCHAR(32) DEFAULT 'standard' NOT NULL"),
    ("tenants", "module_workshop", "BOOLEAN DEFAULT 1 NOT NULL"),
    ("tenants", "module_shop", "BOOLEAN DEFAULT 0 NOT NULL"),
    # v5 — sikkerhet og audit
    ("users", "last_login_at", "DATETIME"),
]


def _apply_column_migrations() -> None:
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())
    with engine.begin() as conn:
        for table, col, ddl in _COLUMN_MIGRATIONS:
            if table not in existing_tables:
                continue
            cols = {c["name"] for c in insp.get_columns(table)}
            if col in cols:
                continue
            conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {col} {ddl}'))


def init_db() -> None:
    # Race-safe ved flere uvicorn-workers: hver worker forsøker å lage
    # tabellene samtidig. SQLAlchemy bruker som default checkfirst=True,
    # men sjekken og CREATE skjer ikke atomisk – derfor svelger vi
    # "already exists"-feilen som ufarlig.
    from sqlalchemy.exc import OperationalError, ProgrammingError
    try:
        Base.metadata.create_all(bind=engine)
    except (OperationalError, ProgrammingError) as e:
        msg = str(e).lower()
        if "already exists" not in msg:
            raise
    _apply_column_migrations()
    db: Session = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.slug == settings.SEED_TENANT_SLUG).first()
        if not tenant:
            tenant = Tenant(name=settings.SEED_TENANT_NAME, slug=settings.SEED_TENANT_SLUG)
            db.add(tenant)
            db.flush()

        admin = (
            db.query(User)
            .filter(User.email == settings.SEED_ADMIN_EMAIL, User.tenant_id == tenant.id)
            .first()
        )
        if not admin:
            admin = User(
                tenant_id=tenant.id,
                email=settings.SEED_ADMIN_EMAIL,
                name=settings.SEED_ADMIN_NAME,
                password_hash=hash_password(settings.SEED_ADMIN_PASSWORD),
                role=UserRole.admin,
                is_active=True,
            )
            db.add(admin)

        # Promoterér superadmin om e-posten matcher en eksisterende bruker.
        sa_email = (settings.SEED_SUPERADMIN_EMAIL or "").strip().lower()
        if sa_email:
            sa = db.query(User).filter(User.email == sa_email).first()
            if sa and sa.role != UserRole.superadmin:
                sa.role = UserRole.superadmin
        db.commit()
    finally:
        db.close()
