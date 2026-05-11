from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base


class UserRole(str, PyEnum):
    superadmin = "superadmin"
    admin = "admin"
    seller = "seller"
    goldsmith = "goldsmith"


class JobStatus(str, PyEnum):
    registered = "registered"
    in_transit = "in_transit"
    awaiting = "awaiting"
    in_progress = "in_progress"
    waiting_parts = "waiting_parts"
    done = "done"
    delivered = "delivered"
    cancelled = "cancelled"


class JobType(str, PyEnum):
    repair = "repair"
    design = "design"
    sale = "sale"
    other = "other"


class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    slug = Column(String(64), nullable=False, unique=True)
    susoft_tenant_id = Column(String(128))
    is_active = Column(Boolean, default=True, nullable=False)
    plan = Column(String(32), default="standard", nullable=False)
    module_workshop = Column(Boolean, default=True, nullable=False)
    module_shop = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_user_tenant_email"),)
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(255), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.seller)
    is_active = Column(Boolean, default=True)
    totp_secret = Column(String(64))
    last_login_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="users")


class AuditLog(Base):
    """Tamper-evident audit trail for sensitive actions (impersonation, etc.)."""
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    target_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    target_tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="SET NULL"))
    action = Column(String(64), nullable=False, index=True)
    ip = Column(String(64))
    detail = Column(Text)


class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    susoft_customer_id = Column(String(128), index=True)
    name = Column(String(200), nullable=False)
    phone = Column(String(40), index=True)
    email = Column(String(255), index=True)
    address = Column(String(255))
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    jobs = relationship("Job", back_populates="customer")


class Location(Base):
    """Physical storage location: Skap A -> Hylle 1 -> Boks 12 (hierarchical)."""
    __tablename__ = "locations"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_id = Column(Integer, ForeignKey("locations.id", ondelete="CASCADE"))
    code = Column(String(64), nullable=False)  # e.g. "A", "1", "12"
    label = Column(String(200), nullable=False)  # e.g. "Skap A", "Hylle 1"
    qr_token = Column(String(64), unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    parent = relationship("Location", remote_side=[id], backref="children")


class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    job_number = Column(String(32), nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="SET NULL"))
    assigned_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    location_id = Column(Integer, ForeignKey("locations.id", ondelete="SET NULL"))

    job_type = Column(Enum(JobType), nullable=False, default=JobType.repair)
    status = Column(Enum(JobStatus), nullable=False, default=JobStatus.registered, index=True)

    description = Column(Text)
    metal_type = Column(String(64))
    gemstones = Column(String(255))
    estimated_weight_g = Column(Numeric(10, 3))
    condition_notes = Column(Text)

    estimated_price = Column(Numeric(12, 2))
    estimated_completion = Column(DateTime)
    pickup_code = Column(String(16), index=True)
    qr_token = Column(String(64), unique=True, index=True)

    # Material flow / svinn-kontroll
    weight_in_g = Column(Numeric(10, 3))         # vekt ved innlevering
    weight_out_g = Column(Numeric(10, 3))        # vekt ved utlevering

    # Fysisk lagring i verkstedet (fri tekst, f.eks. "Skap A / Hylle 3 / Boks 12")
    storage_location = Column(String(120))

    # QC-sjekkliste (JSON-streng: list[{label, checked, by, at}])
    qc_checklist = Column(Text)

    # Intern notat – synlig kun internt, separat fra kundens "description"
    internal_notes = Column(Text)

    susoft_order_id = Column(String(128))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = relationship("Customer", back_populates="jobs")
    assigned_user = relationship("User")
    location = relationship("Location")
    images = relationship("JobImage", back_populates="job", cascade="all, delete-orphan")
    logs = relationship("JobLog", back_populates="job", cascade="all, delete-orphan", order_by="JobLog.created_at")
    comments = relationship("JobComment", back_populates="job", cascade="all, delete-orphan", order_by="JobComment.created_at")
    time_entries = relationship("JobTimeEntry", back_populates="job", cascade="all, delete-orphan", order_by="JobTimeEntry.started_at")
    parts = relationship("PartOrder", back_populates="job", cascade="all, delete-orphan", order_by="PartOrder.created_at")


class JobImage(Base):
    __tablename__ = "job_images"
    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    file_path = Column(String(512), nullable=False)
    caption = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="images")


class JobLog(Base):
    """Audit trail: who did what and when."""
    __tablename__ = "job_logs"
    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    action = Column(String(64), nullable=False)  # status_change, location_change, note, etc.
    from_value = Column(String(255))
    to_value = Column(String(255))
    note = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="logs")
    user = relationship("User")


class SusoftConfig(Base):
    """Per-tenant Susoft API credentials."""
    __tablename__ = "susoft_configs"
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    base_url = Column(String(255), nullable=False, default="https://api.susoft.com:4443")
    shop_url_key = Column(String(64), nullable=False)         # e.g. "jonb"
    login = Column(String(255), nullable=False)               # e.g. "jon@easify.no"
    password_enc = Column(Text, nullable=False)               # Fernet-encrypted
    auto_create_order = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    last_test_at = Column(DateTime)
    last_test_ok = Column(Boolean)
    last_test_error = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PrinterConfig(Base):
    """Per-tenant thermal printer + receipt customisation."""
    __tablename__ = "printer_configs"
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    paper_width_mm = Column(Integer, default=80)              # 58 or 80
    dots_per_line = Column(Integer, default=576)              # 576 for 80mm, 384 for 58mm
    header_line1 = Column(String(120))                        # Shop name
    header_line2 = Column(String(120))                        # Address line
    header_line3 = Column(String(120))                        # Phone / org no
    footer_line = Column(String(200), default="Takk for at du valgte oss!")
    print_qr_on_receipt = Column(Boolean, default=True)
    cut_paper = Column(Boolean, default=True)
    receipt_url_template = Column(String(255))                # e.g. https://gvk.example/p/{token}
    # Network printer (Epson TM-* with Ethernet / WiFi over raw TCP, default port 9100)
    printer_host = Column(String(120))                        # IP or hostname
    printer_port = Column(Integer, default=9100)
    printer_timeout_s = Column(Integer, default=5)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Notification(Base):
    """Customer-facing notifications (SMS / e-mail)."""
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    channel = Column(String(16), nullable=False)              # sms | email
    recipient = Column(String(255), nullable=False)
    subject = Column(String(255))
    body = Column(Text, nullable=False)
    status = Column(String(32), nullable=False, default="queued")  # queued | sent | failed
    error = Column(Text)
    sent_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class JobComment(Base):
    """Internal/customer-facing comments on a job (chat-style thread)."""
    __tablename__ = "job_comments"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    body = Column(Text, nullable=False)
    is_internal = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="comments")
    user = relationship("User")


class JobTimeEntry(Base):
    """Start/stopp arbeidsøkt på en jobb. Maks én åpen økt per (bruker, jobb)."""
    __tablename__ = "job_time_entries"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    stopped_at = Column(DateTime)
    note = Column(Text)
    show_on_receipt = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="time_entries")
    user = relationship("User")


class PartOrder(Base):
    """Bestilling av del / materiale knyttet til en jobb."""
    __tablename__ = "part_orders"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    description = Column(String(400), nullable=False)
    supplier = Column(String(120))
    supplier_ref = Column(String(120))         # bestillingsnr / artikkel hos leverandør
    quantity = Column(Numeric(10, 3), default=1)
    cost_price = Column(Numeric(12, 2))   # innkjøpspris (intern)
    sale_price = Column(Numeric(12, 2))   # utpris til kunde (vises på kvittering)
    status = Column(String(32), nullable=False, default="needed")
    # status: needed | ordered | received | installed | cancelled
    ordered_at = Column(DateTime)
    received_at = Column(DateTime)
    note = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    job = relationship("Job", back_populates="parts")
    user = relationship("User")
