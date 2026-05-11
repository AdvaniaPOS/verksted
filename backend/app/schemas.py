from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr

from .models import JobStatus, JobType, UserRole


# --- Auth ---
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


# --- Tenant / User ---
class TenantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    slug: str
    is_active: bool = True
    plan: str = "standard"
    module_workshop: bool = True
    module_shop: bool = False


class TenantCreate(BaseModel):
    name: str
    slug: str
    plan: str = "standard"
    module_workshop: bool = True
    module_shop: bool = False
    admin_email: EmailStr
    admin_name: str
    admin_password: str


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    plan: Optional[str] = None
    module_workshop: Optional[bool] = None
    module_shop: Optional[bool] = None


class TenantStatsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    slug: str
    is_active: bool
    plan: str
    module_workshop: bool
    module_shop: bool
    user_count: int = 0
    job_count: int = 0
    customer_count: int = 0
    created_at: datetime


class ImpersonateOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    name: str
    role: UserRole
    is_active: bool
    tenant: TenantOut


class UserCreate(BaseModel):
    email: EmailStr
    name: str
    password: str
    role: UserRole = UserRole.seller


# --- Customer ---
class CustomerBase(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    susoft_customer_id: Optional[str] = None


class CustomerCreate(CustomerBase):
    pass


class CustomerOut(CustomerBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class CustomerStats(BaseModel):
    job_count: int = 0
    open_count: int = 0
    last_visit: Optional[datetime] = None
    total_estimated_price: float = 0.0


class CustomerDetail(CustomerOut):
    stats: CustomerStats


# --- Location ---
class LocationBase(BaseModel):
    code: str
    label: str
    parent_id: Optional[int] = None


class LocationCreate(LocationBase):
    pass


class LocationOut(LocationBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    qr_token: Optional[str] = None


# --- Job ---
class JobBase(BaseModel):
    customer_id: Optional[int] = None
    job_type: JobType = JobType.repair
    description: Optional[str] = None
    metal_type: Optional[str] = None
    gemstones: Optional[str] = None
    estimated_weight_g: Optional[Decimal] = None
    condition_notes: Optional[str] = None
    estimated_price: Optional[Decimal] = None
    estimated_completion: Optional[datetime] = None
    location_id: Optional[int] = None
    assigned_user_id: Optional[int] = None
    weight_in_g: Optional[Decimal] = None
    weight_out_g: Optional[Decimal] = None
    storage_location: Optional[str] = None
    internal_notes: Optional[str] = None


class JobCreate(JobBase):
    pass


class JobUpdate(BaseModel):
    status: Optional[JobStatus] = None
    customer_id: Optional[int] = None
    location_id: Optional[int] = None
    assigned_user_id: Optional[int] = None
    job_type: Optional[JobType] = None
    description: Optional[str] = None
    metal_type: Optional[str] = None
    gemstones: Optional[str] = None
    estimated_weight_g: Optional[Decimal] = None
    estimated_price: Optional[Decimal] = None
    estimated_completion: Optional[datetime] = None
    condition_notes: Optional[str] = None
    weight_in_g: Optional[Decimal] = None
    weight_out_g: Optional[Decimal] = None
    storage_location: Optional[str] = None
    internal_notes: Optional[str] = None
    qc_checklist: Optional[str] = None  # JSON-streng


class JobLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    action: str
    from_value: Optional[str] = None
    to_value: Optional[str] = None
    note: Optional[str] = None
    created_at: datetime


class JobImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    file_path: str
    caption: Optional[str] = None
    created_at: datetime


class JobOut(JobBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    job_number: str
    status: JobStatus
    pickup_code: Optional[str] = None
    qr_token: Optional[str] = None
    qc_checklist: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    customer: Optional[CustomerOut] = None
    location: Optional[LocationOut] = None
    images: List[JobImageOut] = []
    open_time_entry_id: Optional[int] = None
    total_minutes: int = 0
    parts_summary: Optional["PartsSummary"] = None


class JobDetail(JobOut):
    logs: List[JobLogOut] = []
    comments: List["JobCommentOut"] = []
    time_entries: List["JobTimeEntryOut"] = []
    parts: List["PartOrderOut"] = []


# --- Susoft config ---
class SusoftConfigIn(BaseModel):
    base_url: Optional[str] = None
    shop_url_key: str
    login: str
    password: Optional[str] = None     # write-only; null = keep existing
    auto_create_order: bool = True
    is_active: bool = True


class SusoftConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    base_url: Optional[str] = None
    shop_url_key: Optional[str] = None
    login: Optional[str] = None
    has_password: bool = False
    auto_create_order: bool = True
    is_active: bool = True
    last_test_at: Optional[datetime] = None
    last_test_ok: Optional[bool] = None
    last_test_error: Optional[str] = None


class SusoftTestResult(BaseModel):
    ok: bool
    message: str
    shop_name: Optional[str] = None


class PrintTestResult(BaseModel):
    ok: bool
    message: str
    bytes_sent: int = 0


# --- Printer config ---
class PrinterConfigIn(BaseModel):
    paper_width_mm: int = 80
    dots_per_line: int = 576
    header_line1: Optional[str] = None
    header_line2: Optional[str] = None
    header_line3: Optional[str] = None
    footer_line: Optional[str] = None
    print_qr_on_receipt: bool = True
    cut_paper: bool = True
    receipt_url_template: Optional[str] = None
    printer_host: Optional[str] = None
    printer_port: int = 9100
    printer_timeout_s: int = 5


class PrinterConfigOut(PrinterConfigIn):
    model_config = ConfigDict(from_attributes=True)


# --- Notifications ---
class NotificationCreate(BaseModel):
    channel: str  # sms | email
    template: Optional[str] = None  # ready | delayed | quote | custom
    body: Optional[str] = None
    subject: Optional[str] = None
    recipient: Optional[str] = None  # override; else uses customer phone/email


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    job_id: int
    channel: str
    recipient: str
    subject: Optional[str] = None
    body: str
    status: str
    error: Optional[str] = None
    sent_at: Optional[datetime] = None
    created_at: datetime


# --- Job comments ---
class JobCommentCreate(BaseModel):
    body: str
    is_internal: bool = True


class JobCommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    job_id: int
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    body: str
    is_internal: bool
    created_at: datetime


# --- Time tracking ---
class JobTimeStart(BaseModel):
    note: Optional[str] = None


class JobTimeStop(BaseModel):
    note: Optional[str] = None
    show_on_receipt: bool = False


class JobTimeEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    job_id: int
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    started_at: datetime
    stopped_at: Optional[datetime] = None
    minutes: int = 0
    note: Optional[str] = None
    show_on_receipt: bool = False


# --- Parts / procurement ---
class PartOrderCreate(BaseModel):
    description: str
    supplier: Optional[str] = None
    supplier_ref: Optional[str] = None
    quantity: Optional[Decimal] = Decimal("1")
    cost_price: Optional[Decimal] = None
    sale_price: Optional[Decimal] = None
    note: Optional[str] = None


class PartOrderUpdate(BaseModel):
    description: Optional[str] = None
    supplier: Optional[str] = None
    supplier_ref: Optional[str] = None
    quantity: Optional[Decimal] = None
    cost_price: Optional[Decimal] = None
    sale_price: Optional[Decimal] = None
    status: Optional[str] = None  # needed | ordered | received | installed | cancelled
    note: Optional[str] = None


class PartOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    job_id: int
    description: str
    supplier: Optional[str] = None
    supplier_ref: Optional[str] = None
    quantity: Optional[Decimal] = None
    cost_price: Optional[Decimal] = None
    sale_price: Optional[Decimal] = None
    status: str
    ordered_at: Optional[datetime] = None
    received_at: Optional[datetime] = None
    note: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    # context for procurement view
    job_number: Optional[str] = None
    customer_name: Optional[str] = None


class PartsSummary(BaseModel):
    total: int = 0
    needed: int = 0
    ordered: int = 0
    received: int = 0


TokenResponse.model_rebuild()
JobOut.model_rebuild()
JobDetail.model_rebuild()
ImpersonateOut.model_rebuild()
