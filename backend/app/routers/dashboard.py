from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Customer, Job, JobStatus, User
from ..security import get_current_user

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    base = db.query(Job).filter(Job.tenant_id == user.tenant_id)
    counts = {s.value: 0 for s in JobStatus}
    rows = (
        db.query(Job.status, func.count(Job.id))
        .filter(Job.tenant_id == user.tenant_id)
        .group_by(Job.status)
        .all()
    )
    for status, count in rows:
        counts[status.value] = count
    total_jobs = base.count()
    total_customers = (
        db.query(func.count(Customer.id)).filter(Customer.tenant_id == user.tenant_id).scalar()
    )
    return {
        "total_jobs": total_jobs,
        "total_customers": total_customers,
        "by_status": counts,
    }
