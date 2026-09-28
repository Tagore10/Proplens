from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import asc, desc
from typing import Optional

from app.database import get_db
from app import models
from app.utils.lease_status import compute_lease_status, days_to_expiry
from app.schemas.property import LeaseListResponse, LeaseOut

router = APIRouter(prefix="/api/leases", tags=["leases"])


@router.get("", response_model=LeaseListResponse)
def list_leases(
    db: Session = Depends(get_db),
    property_id: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status", description="Active, Expiring Soon, or Expired"),
    sort_by: str = Query("lease_end", description="lease_end, lease_start, annual_rent"),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    query = db.query(models.Lease)
    if property_id:
        query = query.filter(models.Lease.property_id == property_id)

    sortable = {
        "lease_end": models.Lease.lease_end,
        "lease_start": models.Lease.lease_start,
        "annual_rent": models.Lease.annual_rent,
    }
    sort_col = sortable.get(sort_by, models.Lease.lease_end)
    query = query.order_by(desc(sort_col) if sort_dir == "desc" else asc(sort_col))

    all_rows = query.all()

    # Status is always computed at read-time (see utils/lease_status.py), so
    # filtering by status happens in Python after computing it.
    enriched = []
    for l in all_rows:
        status = compute_lease_status(l.lease_end) if l.lease_end else "Unknown"
        if status_filter and status != status_filter:
            continue
        prop_name = l.property.name if l.property else None
        enriched.append(LeaseOut(
            id=l.id, property_id=l.property_id, property_name=prop_name,
            tenant_id=l.tenant_id, tenant_name=l.tenant_name,
            lease_start=l.lease_start, lease_end=l.lease_end, annual_rent=l.annual_rent,
            renewal_status=l.renewal_status, lease_status=status,
            days_to_expiry=days_to_expiry(l.lease_end) if l.lease_end else None,
        ))

    total = len(enriched)
    start = (page - 1) * page_size
    page_rows = enriched[start:start + page_size]

    return LeaseListResponse(total=total, count=len(page_rows), page=page, page_size=page_size, leases=page_rows)
