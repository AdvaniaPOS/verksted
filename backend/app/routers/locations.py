from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Location, User
from ..schemas import LocationCreate, LocationOut
from ..security import get_current_user
from ..utils import generate_token

router = APIRouter(prefix="/locations", tags=["locations"])


@router.get("", response_model=List[LocationOut])
def list_locations(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return (
        db.query(Location)
        .filter(Location.tenant_id == user.tenant_id)
        .order_by(Location.parent_id.nulls_first(), Location.label)
        .all()
    )


@router.post("", response_model=LocationOut, status_code=201)
def create_location(
    payload: LocationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if payload.parent_id:
        parent = db.query(Location).filter(
            Location.id == payload.parent_id, Location.tenant_id == user.tenant_id
        ).first()
        if not parent:
            raise HTTPException(400, "Ugyldig parent_id")
    loc = Location(tenant_id=user.tenant_id, qr_token=generate_token(24), **payload.model_dump())
    db.add(loc)
    db.commit()
    db.refresh(loc)
    return loc


@router.delete("/{location_id}", status_code=204)
def delete_location(location_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    loc = db.query(Location).filter(Location.id == location_id, Location.tenant_id == user.tenant_id).first()
    if not loc:
        raise HTTPException(404, "Lokasjon ikke funnet")
    db.delete(loc)
    db.commit()
