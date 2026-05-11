from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, func
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import Customer, Job, JobStatus, User
from ..schemas import CustomerCreate, CustomerDetail, CustomerOut, CustomerStats, JobOut
from ..security import get_current_user

router = APIRouter(prefix="/customers", tags=["customers"])

_OPEN_STATUSES = {
    JobStatus.registered, JobStatus.in_transit, JobStatus.awaiting,
    JobStatus.in_progress, JobStatus.waiting_parts,
}


@router.get("", response_model=List[CustomerOut])
def list_customers(
    q: Optional[str] = Query(None, description="Søk i navn/telefon/e-post"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Customer).filter(Customer.tenant_id == user.tenant_id)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(
            Customer.name.ilike(like),
            Customer.phone.ilike(like),
            Customer.email.ilike(like),
        ))
    return query.order_by(Customer.name).limit(100).all()


@router.post("", response_model=CustomerOut, status_code=201)
def create_customer(
    payload: CustomerCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    c = Customer(tenant_id=user.tenant_id, **payload.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _get_or_404(db: Session, customer_id: int, tenant_id: int) -> Customer:
    c = db.query(Customer).filter(Customer.id == customer_id, Customer.tenant_id == tenant_id).first()
    if not c:
        raise HTTPException(404, "Kunde ikke funnet")
    return c


@router.get("/{customer_id}", response_model=CustomerDetail)
def get_customer(customer_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = _get_or_404(db, customer_id, user.tenant_id)
    rows = db.query(Job.status, Job.created_at, Job.estimated_price).filter(
        Job.customer_id == c.id, Job.tenant_id == user.tenant_id
    ).all()
    job_count = len(rows)
    open_count = sum(1 for r in rows if r.status in _OPEN_STATUSES)
    last_visit = max((r.created_at for r in rows), default=None)
    total = float(sum((r.estimated_price or 0) for r in rows))
    return CustomerDetail(
        **CustomerOut.model_validate(c).model_dump(),
        stats=CustomerStats(
            job_count=job_count, open_count=open_count,
            last_visit=last_visit, total_estimated_price=total,
        ),
    )


@router.patch("/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: int,
    payload: CustomerCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    c = _get_or_404(db, customer_id, user.tenant_id)
    for k, v in payload.model_dump().items():
        setattr(c, k, v)
    db.commit()
    db.refresh(c)
    return c


@router.get("/{customer_id}/jobs", response_model=List[JobOut])
def list_customer_jobs(customer_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _get_or_404(db, customer_id, user.tenant_id)
    return (
        db.query(Job)
        .options(joinedload(Job.customer), joinedload(Job.location), joinedload(Job.images))
        .filter(Job.customer_id == customer_id, Job.tenant_id == user.tenant_id)
        .order_by(Job.created_at.desc())
        .all()
    )

