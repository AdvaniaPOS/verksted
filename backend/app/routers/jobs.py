import logging
import os
import shutil
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from ..config import settings
from ..database import get_db
from ..models import (
    Customer, Job, JobComment, JobImage, JobLog, JobStatus, JobTimeEntry,
    Location, Notification, PartOrder, PrinterConfig, SusoftConfig, User,
)
from ..netprint import NetworkPrintError, send_raw
from ..printing import render_receipt, render_receipt_html, render_tag, render_tag_html
from ..schemas import (
    JobCommentCreate, JobCommentOut, JobCreate, JobDetail, JobOut, JobTimeEntryOut,
    JobTimeStart, JobTimeStop, JobUpdate, NotificationCreate, NotificationOut,
    PartOrderCreate, PartOrderOut, PartOrderUpdate, PartsSummary,
)
from ..security import get_current_user
from ..susoft import SusoftClient, SusoftError
from ..utils import generate_job_number, generate_pickup_code, generate_token

log = logging.getLogger("gvk.jobs")
router = APIRouter(prefix="/jobs", tags=["jobs"])


def _log(db: Session, job: Job, user: User, action: str, frm: Optional[str] = None, to: Optional[str] = None, note: Optional[str] = None) -> None:
    db.add(JobLog(job_id=job.id, user_id=user.id, action=action, from_value=frm, to_value=to, note=note))


def _decorate(db: Session, job: Job) -> Job:
    """Attach computed fields (total_minutes, open_time_entry_id, parts_summary)
    so that pydantic JobOut/JobDetail can pick them up from the ORM instance."""
    entries = job.time_entries or []
    total = 0
    open_id: Optional[int] = None
    for e in entries:
        if e.stopped_at is None:
            open_id = e.id
            delta = (datetime.utcnow() - e.started_at).total_seconds() / 60.0
        else:
            delta = (e.stopped_at - e.started_at).total_seconds() / 60.0
        total += int(max(0, delta))
    parts = job.parts or []
    summary = PartsSummary(
        total=len(parts),
        needed=sum(1 for p in parts if p.status == "needed"),
        ordered=sum(1 for p in parts if p.status == "ordered"),
        received=sum(1 for p in parts if p.status in ("received", "installed")),
    )
    setattr(job, "open_time_entry_id", open_id)
    setattr(job, "total_minutes", total)
    setattr(job, "parts_summary", summary)
    # attach user_name on nested comments / time entries (else schema gets None)
    for c in job.comments or []:
        setattr(c, "user_name", c.user.name if c.user else None)
    for e in entries:
        setattr(e, "user_name", e.user.name if e.user else None)
        if e.stopped_at:
            e.minutes = int(max(0, (e.stopped_at - e.started_at).total_seconds() / 60.0))
        else:
            e.minutes = int(max(0, (datetime.utcnow() - e.started_at).total_seconds() / 60.0))
    return job


@router.get("", response_model=List[JobOut])
def list_jobs(
    status: Optional[JobStatus] = Query(None),
    q: Optional[str] = Query(None),
    customer_id: Optional[int] = Query(None),
    open_only: bool = Query(False),
    sort: str = Query("newest", pattern="^(newest|oldest|due)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = (
        db.query(Job)
        .filter(Job.tenant_id == user.tenant_id)
        .options(
            joinedload(Job.customer),
            joinedload(Job.location),
            joinedload(Job.images),
            joinedload(Job.time_entries),
            joinedload(Job.parts),
            joinedload(Job.comments),
        )
    )
    if status:
        query = query.filter(Job.status == status)
    if customer_id:
        query = query.filter(Job.customer_id == customer_id)
    if open_only:
        open_set = [JobStatus.registered, JobStatus.in_transit, JobStatus.awaiting,
                    JobStatus.in_progress, JobStatus.waiting_parts]
        query = query.filter(Job.status.in_(open_set))
    if q:
        like = f"%{q.strip()}%"
        query = query.outerjoin(Customer, Job.customer_id == Customer.id).filter(
            (Job.job_number.ilike(like))
            | (Job.description.ilike(like))
            | (Job.pickup_code.ilike(like))
            | (Customer.name.ilike(like))
            | (Customer.phone.ilike(like))
        )
    if sort == "oldest":
        query = query.order_by(Job.created_at.asc())
    elif sort == "due":
        query = query.order_by(Job.estimated_completion.asc().nullslast(), Job.created_at.desc())
    else:
        query = query.order_by(Job.created_at.desc())
    rows = query.limit(300).all()
    return [_decorate(db, j) for j in rows]


@router.post("", response_model=JobOut, status_code=201)
def create_job(payload: JobCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    seq = (db.query(func.count(Job.id)).filter(Job.tenant_id == user.tenant_id).scalar() or 0) + 1
    job = Job(
        tenant_id=user.tenant_id,
        job_number=generate_job_number(seq),
        pickup_code=generate_pickup_code(),
        qr_token=generate_token(24),
        **payload.model_dump(),
    )
    db.add(job)
    db.flush()
    _log(db, job, user, "created", to=job.status.value)
    db.commit()
    db.refresh(job)

    # Best-effort Susoft sync — never block the intake on integration errors.
    cfg = db.query(SusoftConfig).filter(SusoftConfig.tenant_id == user.tenant_id).one_or_none()
    if cfg and cfg.is_active and cfg.auto_create_order:
        try:
            _sync_to_susoft(db, job, user, cfg)
        except Exception as e:  # noqa: BLE001
            log.warning("Susoft sync failed for job %s: %s", job.job_number, e)
            _log(db, job, user, "susoft_error", note=str(e)[:500])
            db.commit()
    db.refresh(job)
    return _decorate(db, job)


def _sync_to_susoft(db: Session, job: Job, user: User, cfg: SusoftConfig) -> None:
    """Push customer (if needed) and create a parked workshop order in Susoft."""
    with SusoftClient(cfg) as client:
        susoft_customer_id: Optional[str] = None
        cust = job.customer
        if cust:
            if not cust.susoft_customer_id:
                # try to locate by external ref or contact info
                external_ref = f"GVK-{user.tenant_id}-{cust.id}"
                found = client.find_customer_by_external_id(external_ref)
                if not found and (cust.phone or cust.email):
                    matches = client.search_customers(phone=cust.phone, email=cust.email)
                    found = matches[0] if matches else None
                if not found:
                    parts = (cust.name or "").strip().split(" ", 1)
                    first = parts[0]
                    last = parts[1] if len(parts) > 1 else parts[0]
                    found = client.create_customer(
                        first_name=first, last_name=last,
                        phone=cust.phone, email=cust.email, address=cust.address,
                        external_id=external_ref,
                    )
                if found and found.get("id"):
                    cust.susoft_customer_id = str(found["id"])
                    db.add(cust)
            susoft_customer_id = cust.susoft_customer_id

        order = client.create_workshop_order(
            susoft_customer_id=susoft_customer_id,
            alternative_id=job.job_number,
            description=job.description or f"Verkstedjobb {job.job_number}",
            price=float(job.estimated_price) if job.estimated_price is not None else None,
            note=job.condition_notes,
        )
        order_no = order.get("orderNo") or order.get("uuid")
        if order_no is not None:
            job.susoft_order_id = str(order_no)
            db.add(job)
            _log(db, job, user, "susoft_order_created", to=str(order_no))
            db.commit()


@router.post("/{job_id}/susoft/sync", response_model=JobOut)
def resync_to_susoft(job_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    job = db.query(Job).options(joinedload(Job.customer)).filter(
        Job.id == job_id, Job.tenant_id == user.tenant_id).first()
    if not job:
        raise HTTPException(404, "Jobb ikke funnet")
    cfg = db.query(SusoftConfig).filter(SusoftConfig.tenant_id == user.tenant_id).one_or_none()
    if not cfg or not cfg.is_active:
        raise HTTPException(400, "Susoft er ikke aktivt for denne kunden")
    try:
        _sync_to_susoft(db, job, user, cfg)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Susoft sync feilet: {e}")
    db.refresh(job)
    return _decorate(db, job)


# ----------------- Printing -----------------
def _load_full_job(db: Session, job_id: int, tenant_id: int) -> Job:
    job = (
        db.query(Job)
        .options(joinedload(Job.customer), joinedload(Job.location), joinedload(Job.images))
        .filter(Job.id == job_id, Job.tenant_id == tenant_id)
        .first()
    )
    if not job:
        raise HTTPException(404, "Jobb ikke funnet")
    return job


def _printer_cfg(db: Session, tenant_id: int) -> Optional[PrinterConfig]:
    return db.query(PrinterConfig).filter(PrinterConfig.tenant_id == tenant_id).one_or_none()


@router.get("/{job_id}/print/receipt.escpos")
def print_receipt_escpos(job_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    job = _load_full_job(db, job_id, user.tenant_id)
    data = render_receipt(job, _printer_cfg(db, user.tenant_id))
    return Response(content=data, media_type="application/octet-stream",
                    headers={"Content-Disposition": f'attachment; filename="receipt-{job.job_number}.bin"'})


@router.get("/{job_id}/print/tag.escpos")
def print_tag_escpos(job_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    job = _load_full_job(db, job_id, user.tenant_id)
    data = render_tag(job, _printer_cfg(db, user.tenant_id))
    return Response(content=data, media_type="application/octet-stream",
                    headers={"Content-Disposition": f'attachment; filename="tag-{job.job_number}.bin"'})


@router.get("/{job_id}/print/receipt.html", response_class=HTMLResponse)
def print_receipt_html(job_id: int, auto: int = 1, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    job = _load_full_job(db, job_id, user.tenant_id)
    return HTMLResponse(render_receipt_html(job, _printer_cfg(db, user.tenant_id), auto_print=bool(auto)))


@router.get("/{job_id}/print/tag.html", response_class=HTMLResponse)
def print_tag_html(job_id: int, auto: int = 1, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    job = _load_full_job(db, job_id, user.tenant_id)
    return HTMLResponse(render_tag_html(job, _printer_cfg(db, user.tenant_id), auto_print=bool(auto)))


@router.post("/{job_id}/print/receipt/send")
def send_receipt_to_printer(job_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    job = _load_full_job(db, job_id, user.tenant_id)
    cfg = _printer_cfg(db, user.tenant_id)
    if not cfg or not cfg.printer_host:
        raise HTTPException(400, "Skriverens IP/hostname er ikke satt (Administrasjon \u2192 Skriver)")
    data = render_receipt(job, cfg)
    try:
        n = send_raw(cfg.printer_host, cfg.printer_port or 9100, data, timeout=cfg.printer_timeout_s or 5)
    except NetworkPrintError as e:
        raise HTTPException(502, str(e))
    _log(db, job, user, "receipt_printed", note=f"{cfg.printer_host}:{cfg.printer_port} ({n} B)")
    db.commit()
    return {"ok": True, "bytes_sent": n}


@router.post("/{job_id}/print/tag/send")
def send_tag_to_printer(job_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    job = _load_full_job(db, job_id, user.tenant_id)
    cfg = _printer_cfg(db, user.tenant_id)
    if not cfg or not cfg.printer_host:
        raise HTTPException(400, "Skriverens IP/hostname er ikke satt (Administrasjon \u2192 Skriver)")
    data = render_tag(job, cfg)
    try:
        n = send_raw(cfg.printer_host, cfg.printer_port or 9100, data, timeout=cfg.printer_timeout_s or 5)
    except NetworkPrintError as e:
        raise HTTPException(502, str(e))
    _log(db, job, user, "tag_printed", note=f"{cfg.printer_host}:{cfg.printer_port} ({n} B)")
    db.commit()
    return {"ok": True, "bytes_sent": n}


@router.get("/{job_id}", response_model=JobDetail)
def get_job(job_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    job = (
        db.query(Job)
        .options(
            joinedload(Job.customer),
            joinedload(Job.location),
            joinedload(Job.images),
            joinedload(Job.logs),
            joinedload(Job.comments).joinedload(JobComment.user),
            joinedload(Job.time_entries).joinedload(JobTimeEntry.user),
            joinedload(Job.parts),
        )
        .filter(Job.id == job_id, Job.tenant_id == user.tenant_id)
        .first()
    )
    if not job:
        raise HTTPException(404, "Jobb ikke funnet")
    return _decorate(db, job)


@router.patch("/{job_id}", response_model=JobOut)
def update_job(
    job_id: int,
    payload: JobUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = db.query(Job).filter(Job.id == job_id, Job.tenant_id == user.tenant_id).first()
    if not job:
        raise HTTPException(404, "Jobb ikke funnet")

    data = payload.model_dump(exclude_unset=True)

    if "status" in data and data["status"] != job.status:
        _log(db, job, user, "status_change", frm=job.status.value, to=data["status"].value)
        job.status = data.pop("status")
    if "customer_id" in data and data["customer_id"] != job.customer_id:
        if data["customer_id"] is not None:
            cust = db.query(Customer).filter(
                Customer.id == data["customer_id"], Customer.tenant_id == user.tenant_id
            ).first()
            if not cust:
                raise HTTPException(400, "Ugyldig customer_id")
        _log(db, job, user, "customer_change", frm=str(job.customer_id), to=str(data["customer_id"]))
        job.customer_id = data.pop("customer_id")
    if "location_id" in data and data["location_id"] != job.location_id:
        if data["location_id"] is not None:
            loc = db.query(Location).filter(
                Location.id == data["location_id"], Location.tenant_id == user.tenant_id
            ).first()
            if not loc:
                raise HTTPException(400, "Ugyldig location_id")
        _log(db, job, user, "location_change", frm=str(job.location_id), to=str(data["location_id"]))
        job.location_id = data.pop("location_id")

    for key, value in data.items():
        setattr(job, key, value)

    db.commit()
    db.refresh(job)
    return _decorate(db, job)


@router.post("/{job_id}/images", response_model=JobOut)
def upload_image(
    job_id: int,
    file: UploadFile = File(...),
    caption: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = db.query(Job).filter(Job.id == job_id, Job.tenant_id == user.tenant_id).first()
    if not job:
        raise HTTPException(404, "Jobb ikke funnet")
    if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(400, "Ugyldig filtype")

    tenant_dir = os.path.join(settings.UPLOAD_DIR, str(user.tenant_id), str(job_id))
    os.makedirs(tenant_dir, exist_ok=True)
    safe_name = f"{generate_token(12)}_{os.path.basename(file.filename or 'image')}"
    full_path = os.path.join(tenant_dir, safe_name)
    with open(full_path, "wb") as out:
        shutil.copyfileobj(file.file, out)

    rel_path = os.path.relpath(full_path, settings.UPLOAD_DIR)
    img = JobImage(job_id=job.id, file_path=rel_path, caption=caption)
    db.add(img)
    _log(db, job, user, "image_added", note=caption)
    db.commit()
    db.refresh(job)
    return _decorate(db, job)


@router.post("/{job_id}/scan", response_model=JobOut)
def scan_to_location(
    job_id: int,
    qr_token: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = db.query(Job).filter(Job.id == job_id, Job.tenant_id == user.tenant_id).first()
    if not job:
        raise HTTPException(404, "Jobb ikke funnet")
    loc = db.query(Location).filter(Location.qr_token == qr_token, Location.tenant_id == user.tenant_id).first()
    if not loc:
        raise HTTPException(404, "Ukjent lokasjon-QR")
    _log(db, job, user, "scanned_to_location", frm=str(job.location_id), to=str(loc.id))
    job.location_id = loc.id
    db.commit()
    db.refresh(job)
    return _decorate(db, job)


# ----------------- Image deletion -----------------
@router.delete("/{job_id}/images/{image_id}", status_code=204)
def delete_image(job_id: int, image_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    img = (
        db.query(JobImage)
        .join(Job, Job.id == JobImage.job_id)
        .filter(JobImage.id == image_id, Job.id == job_id, Job.tenant_id == user.tenant_id)
        .first()
    )
    if not img:
        raise HTTPException(404, "Bilde ikke funnet")
    full = os.path.join(settings.UPLOAD_DIR, img.file_path)
    try:
        if os.path.exists(full):
            os.remove(full)
    except OSError:
        pass
    db.delete(img)
    db.add(JobLog(job_id=job_id, user_id=user.id, action="image_deleted", to_value=str(image_id)))
    db.commit()
    return Response(status_code=204)


# ----------------- Notifications -----------------
_NOTIFY_TEMPLATES = {
    "ready": (
        "Smykket er klart for henting",
        "Hei {name}! Smykket ditt (jobb {jobnr}) er ferdig og klart for henting. Hentekode: {code}.",
    ),
    "delayed": (
        "Liten forsinkelse på jobb {jobnr}",
        "Hei {name}! Vi trenger litt mer tid på jobb {jobnr}. Vi tar kontakt når vi har et nytt estimat.",
    ),
    "quote": (
        "Tilbud på jobb {jobnr}",
        "Hei {name}! Tilbud på jobb {jobnr}: kr {price}. Svar på denne meldingen for å godkjenne.",
    ),
    "received": (
        "Vi har mottatt smykket",
        "Hei {name}! Vi har mottatt smykket ditt (jobb {jobnr}). Du hører fra oss når jobben er klar.",
    ),
}


def _resolve_template(job: Job, template: str, channel: str) -> tuple[str, str]:
    subject, body = _NOTIFY_TEMPLATES.get(template, ("", ""))
    name = (job.customer.name.split(" ", 1)[0] if job.customer else "kunde")
    ctx = {
        "name": name,
        "jobnr": job.job_number,
        "code": job.pickup_code or "",
        "price": (str(job.estimated_price) if job.estimated_price is not None else ""),
    }
    return subject.format(**ctx), body.format(**ctx)


@router.get("/{job_id}/notifications", response_model=List[NotificationOut])
def list_notifications(job_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    job = db.query(Job).filter(Job.id == job_id, Job.tenant_id == user.tenant_id).first()
    if not job:
        raise HTTPException(404, "Jobb ikke funnet")
    return (
        db.query(Notification)
        .filter(Notification.job_id == job_id, Notification.tenant_id == user.tenant_id)
        .order_by(Notification.created_at.desc())
        .all()
    )


@router.post("/{job_id}/notify", response_model=NotificationOut, status_code=201)
def send_notification(
    job_id: int,
    payload: NotificationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = (
        db.query(Job)
        .options(joinedload(Job.customer))
        .filter(Job.id == job_id, Job.tenant_id == user.tenant_id)
        .first()
    )
    if not job:
        raise HTTPException(404, "Jobb ikke funnet")
    if payload.channel not in ("sms", "email"):
        raise HTTPException(400, "channel må være 'sms' eller 'email'")

    recipient = payload.recipient
    if not recipient and job.customer:
        recipient = job.customer.phone if payload.channel == "sms" else job.customer.email
    if not recipient:
        raise HTTPException(400, "Mangler mottaker (telefon/e-post)")

    subject = payload.subject
    body = payload.body
    if payload.template and not body:
        s, b = _resolve_template(job, payload.template, payload.channel)
        subject = subject or s
        body = b
    if not body:
        raise HTTPException(400, "Mangler meldingstekst")

    n = Notification(
        tenant_id=user.tenant_id, job_id=job_id, user_id=user.id,
        channel=payload.channel, recipient=recipient,
        subject=subject, body=body,
        status="sent",  # stub: no provider yet -- record & treat as delivered
        sent_at=datetime.utcnow(),
    )
    db.add(n)
    _log(db, job, user, f"notify_{payload.channel}", to=recipient, note=body[:200])
    db.commit()
    db.refresh(n)
    return n


# ----------------- Comments -----------------
def _require_job(db: Session, job_id: int, tenant_id: int) -> Job:
    job = db.query(Job).filter(Job.id == job_id, Job.tenant_id == tenant_id).first()
    if not job:
        raise HTTPException(404, "Jobb ikke funnet")
    return job


def _comment_out(c: JobComment) -> dict:
    return {
        "id": c.id, "job_id": c.job_id, "user_id": c.user_id,
        "user_name": c.user.name if c.user else None,
        "body": c.body, "is_internal": c.is_internal, "created_at": c.created_at,
    }


@router.get("/{job_id}/comments", response_model=List[JobCommentOut])
def list_comments(job_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_job(db, job_id, user.tenant_id)
    rows = (
        db.query(JobComment)
        .options(joinedload(JobComment.user))
        .filter(JobComment.job_id == job_id, JobComment.tenant_id == user.tenant_id)
        .order_by(JobComment.created_at.asc())
        .all()
    )
    return [_comment_out(c) for c in rows]


@router.post("/{job_id}/comments", response_model=JobCommentOut, status_code=201)
def create_comment(
    job_id: int, payload: JobCommentCreate,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    job = _require_job(db, job_id, user.tenant_id)
    body = (payload.body or "").strip()
    if not body:
        raise HTTPException(400, "Tom kommentar")
    c = JobComment(
        tenant_id=user.tenant_id, job_id=job.id, user_id=user.id,
        body=body, is_internal=payload.is_internal,
    )
    db.add(c)
    _log(db, job, user, "comment_added", note=body[:200])
    db.commit()
    db.refresh(c)
    c.user  # trigger load
    return _comment_out(c)


@router.delete("/{job_id}/comments/{comment_id}", status_code=204)
def delete_comment(job_id: int, comment_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = (
        db.query(JobComment)
        .filter(JobComment.id == comment_id, JobComment.job_id == job_id, JobComment.tenant_id == user.tenant_id)
        .first()
    )
    if not c:
        raise HTTPException(404, "Kommentar ikke funnet")
    if c.user_id != user.id and user.role.value != "admin":
        raise HTTPException(403, "Kan kun slette egne kommentarer")
    db.delete(c)
    db.add(JobLog(job_id=job_id, user_id=user.id, action="comment_deleted", to_value=str(comment_id)))
    db.commit()
    return Response(status_code=204)


# ----------------- Time tracking -----------------
def _time_out(e: JobTimeEntry) -> dict:
    if e.stopped_at:
        minutes = int(max(0, (e.stopped_at - e.started_at).total_seconds() / 60.0))
    else:
        minutes = int(max(0, (datetime.utcnow() - e.started_at).total_seconds() / 60.0))
    return {
        "id": e.id, "job_id": e.job_id, "user_id": e.user_id,
        "user_name": e.user.name if e.user else None,
        "started_at": e.started_at, "stopped_at": e.stopped_at,
        "minutes": minutes, "note": e.note,
        "show_on_receipt": bool(e.show_on_receipt),
    }


@router.get("/{job_id}/time", response_model=List[JobTimeEntryOut])
def list_time(job_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_job(db, job_id, user.tenant_id)
    rows = (
        db.query(JobTimeEntry)
        .options(joinedload(JobTimeEntry.user))
        .filter(JobTimeEntry.job_id == job_id, JobTimeEntry.tenant_id == user.tenant_id)
        .order_by(JobTimeEntry.started_at.desc())
        .all()
    )
    return [_time_out(e) for e in rows]


@router.post("/{job_id}/time/start", response_model=JobTimeEntryOut, status_code=201)
def start_time(
    job_id: int, payload: JobTimeStart,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    job = _require_job(db, job_id, user.tenant_id)
    open_existing = (
        db.query(JobTimeEntry)
        .filter(
            JobTimeEntry.tenant_id == user.tenant_id,
            JobTimeEntry.user_id == user.id,
            JobTimeEntry.stopped_at.is_(None),
        )
        .first()
    )
    if open_existing:
        if open_existing.job_id == job.id:
            open_existing.user  # load
            return _time_out(open_existing)
        # stop the previous one auto
        open_existing.stopped_at = datetime.utcnow()
        open_existing.note = (open_existing.note or "") + " [auto-stopp ved bytte av jobb]"
    e = JobTimeEntry(
        tenant_id=user.tenant_id, job_id=job.id, user_id=user.id,
        started_at=datetime.utcnow(), note=payload.note,
    )
    db.add(e)
    if job.status not in (JobStatus.in_progress, JobStatus.done, JobStatus.delivered, JobStatus.cancelled):
        _log(db, job, user, "status_change", frm=job.status.value, to=JobStatus.in_progress.value, note="auto via tidsstart")
        job.status = JobStatus.in_progress
    _log(db, job, user, "time_start")
    db.commit()
    db.refresh(e)
    e.user
    return _time_out(e)


@router.post("/{job_id}/time/stop", response_model=JobTimeEntryOut)
def stop_time(
    job_id: int, payload: JobTimeStop,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    job = _require_job(db, job_id, user.tenant_id)
    e = (
        db.query(JobTimeEntry)
        .filter(
            JobTimeEntry.tenant_id == user.tenant_id,
            JobTimeEntry.job_id == job.id,
            JobTimeEntry.user_id == user.id,
            JobTimeEntry.stopped_at.is_(None),
        )
        .order_by(JobTimeEntry.started_at.desc())
        .first()
    )
    if not e:
        raise HTTPException(400, "Ingen aktiv arbeidsøkt på denne jobben")
    e.stopped_at = datetime.utcnow()
    if payload.note:
        e.note = (e.note + " | " + payload.note) if e.note else payload.note
    e.show_on_receipt = bool(payload.show_on_receipt)
    minutes = int(max(0, (e.stopped_at - e.started_at).total_seconds() / 60.0))
    _log(db, job, user, "time_stop", note=f"{minutes} min")
    # Speil notatet inn som en kommentar på jobben slik at det dukker opp i
    # kommentar-tråden. is_internal=False = "vises på kvittering" (kundevendt).
    if payload.note and payload.note.strip():
        db.add(JobComment(
            tenant_id=user.tenant_id,
            job_id=job.id,
            user_id=user.id,
            body=f"⏸ Stoppet arbeid ({minutes} min): {payload.note.strip()}",
            is_internal=not bool(payload.show_on_receipt),
        ))
    db.commit()
    db.refresh(e)
    e.user
    return _time_out(e)


# ----------------- Parts / procurement -----------------
def _part_out(p: PartOrder, with_context: bool = False) -> dict:
    out = {
        "id": p.id, "job_id": p.job_id, "description": p.description,
        "supplier": p.supplier, "supplier_ref": p.supplier_ref,
        "quantity": p.quantity, "cost_price": p.cost_price, "sale_price": p.sale_price,
        "status": p.status, "ordered_at": p.ordered_at, "received_at": p.received_at,
        "note": p.note, "created_at": p.created_at, "updated_at": p.updated_at,
    }
    if with_context:
        out["job_number"] = p.job.job_number if p.job else None
        out["customer_name"] = p.job.customer.name if (p.job and p.job.customer) else None
    return out


@router.get("/{job_id}/parts", response_model=List[PartOrderOut])
def list_parts(job_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_job(db, job_id, user.tenant_id)
    rows = (
        db.query(PartOrder)
        .filter(PartOrder.job_id == job_id, PartOrder.tenant_id == user.tenant_id)
        .order_by(PartOrder.created_at.desc())
        .all()
    )
    return [_part_out(p) for p in rows]


@router.post("/{job_id}/parts", response_model=PartOrderOut, status_code=201)
def create_part(
    job_id: int, payload: PartOrderCreate,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    job = _require_job(db, job_id, user.tenant_id)
    desc = (payload.description or "").strip()
    if not desc:
        raise HTTPException(400, "Mangler beskrivelse")
    p = PartOrder(
        tenant_id=user.tenant_id, job_id=job.id, user_id=user.id,
        description=desc, supplier=payload.supplier, supplier_ref=payload.supplier_ref,
        quantity=payload.quantity, cost_price=payload.cost_price, sale_price=payload.sale_price,
        note=payload.note, status="needed",
    )
    db.add(p)
    if job.status in (JobStatus.registered, JobStatus.in_progress, JobStatus.awaiting):
        _log(db, job, user, "status_change", frm=job.status.value, to=JobStatus.waiting_parts.value, note="auto via deler")
        job.status = JobStatus.waiting_parts
    _log(db, job, user, "part_added", note=desc[:200])
    db.commit()
    db.refresh(p)
    return _part_out(p)


@router.patch("/{job_id}/parts/{part_id}", response_model=PartOrderOut)
def update_part(
    job_id: int, part_id: int, payload: PartOrderUpdate,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    job = _require_job(db, job_id, user.tenant_id)
    p = (
        db.query(PartOrder)
        .filter(PartOrder.id == part_id, PartOrder.job_id == job.id, PartOrder.tenant_id == user.tenant_id)
        .first()
    )
    if not p:
        raise HTTPException(404, "Del ikke funnet")
    data = payload.model_dump(exclude_unset=True)
    new_status = data.get("status")
    if new_status and new_status not in {"needed", "ordered", "received", "installed", "cancelled"}:
        raise HTTPException(400, "Ugyldig status")
    if new_status and new_status != p.status:
        _log(db, job, user, "part_status", frm=p.status, to=new_status)
        if new_status == "ordered" and not p.ordered_at:
            p.ordered_at = datetime.utcnow()
        if new_status in ("received", "installed") and not p.received_at:
            p.received_at = datetime.utcnow()
    for k, v in data.items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)

    # If all parts received -> nudge job back from waiting_parts
    remaining = [x for x in (job.parts or []) if x.status in ("needed", "ordered")]
    if not remaining and job.status == JobStatus.waiting_parts:
        _log(db, job, user, "status_change", frm=job.status.value, to=JobStatus.in_progress.value, note="auto: alle deler mottatt")
        job.status = JobStatus.in_progress
        db.commit()
    return _part_out(p)


@router.delete("/{job_id}/parts/{part_id}", status_code=204)
def delete_part(job_id: int, part_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    p = (
        db.query(PartOrder)
        .filter(PartOrder.id == part_id, PartOrder.job_id == job_id, PartOrder.tenant_id == user.tenant_id)
        .first()
    )
    if not p:
        raise HTTPException(404, "Del ikke funnet")
    db.delete(p)
    db.add(JobLog(job_id=job_id, user_id=user.id, action="part_deleted", to_value=str(part_id)))
    db.commit()
    return Response(status_code=204)
