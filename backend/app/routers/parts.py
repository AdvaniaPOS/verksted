"""Cross-job procurement view: liste alle deler/bestillinger på tvers av jobber."""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import Customer, Job, PartOrder, User
from ..schemas import PartOrderOut
from ..security import get_current_user

router = APIRouter(prefix="/parts", tags=["parts"])


@router.get("", response_model=List[PartOrderOut])
def list_all_parts(
    status: Optional[str] = Query(None),
    supplier: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = (
        db.query(PartOrder)
        .options(joinedload(PartOrder.job).joinedload(Job.customer))
        .filter(PartOrder.tenant_id == user.tenant_id)
    )
    if status:
        query = query.filter(PartOrder.status == status)
    if supplier:
        like = f"%{supplier.strip()}%"
        query = query.filter(PartOrder.supplier.ilike(like))
    if q:
        like = f"%{q.strip()}%"
        query = query.outerjoin(Job, Job.id == PartOrder.job_id).outerjoin(
            Customer, Customer.id == Job.customer_id
        ).filter(
            (PartOrder.description.ilike(like))
            | (PartOrder.supplier_ref.ilike(like))
            | (PartOrder.supplier.ilike(like))
            | (Job.job_number.ilike(like))
            | (Customer.name.ilike(like))
        )
    rows = query.order_by(PartOrder.created_at.desc()).limit(500).all()
    return [
        {
            "id": p.id, "job_id": p.job_id, "description": p.description,
            "supplier": p.supplier, "supplier_ref": p.supplier_ref,
            "quantity": p.quantity, "cost_price": p.cost_price,
            "status": p.status, "ordered_at": p.ordered_at, "received_at": p.received_at,
            "note": p.note, "created_at": p.created_at, "updated_at": p.updated_at,
            "job_number": p.job.job_number if p.job else None,
            "customer_name": p.job.customer.name if (p.job and p.job.customer) else None,
        }
        for p in rows
    ]
