from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import asc, desc
from typing import Optional

from app.database import get_db
from app import models
from app.analytics.risk_engine import compute_property_risk
from app.utils.lease_status import compute_lease_status, days_to_expiry
from app.schemas.property import (
    PropertyListResponse, PropertyOut, PropertyDetail, TenantOut, LeaseOut, MonthlyPoint,
)

router = APIRouter(prefix="/api/properties", tags=["properties"])

SORTABLE_FIELDS = {
    "name": models.Property.name,
    "city": models.Property.city,
    "occupancy_pct": models.Property.occupancy_pct,
    "annual_revenue": models.Property.annual_revenue,
    "property_value": models.Property.property_value,
    "risk_score": models.Property.risk_score,  # note: sort applied after risk-engine scoring below
}


@router.get("", response_model=PropertyListResponse)
def list_properties(
    db: Session = Depends(get_db),
    search: Optional[str] = Query(None, description="Matches property name or city"),
    city: Optional[str] = None,
    property_type: Optional[str] = None,
    risk_category: Optional[str] = Query(None, description="Low, Medium, or High"),
    sort_by: str = Query("name", description="name, city, occupancy_pct, annual_revenue, property_value"),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    query = db.query(models.Property)

    if search:
        like = f"%{search}%"
        query = query.filter((models.Property.name.ilike(like)) | (models.Property.city.ilike(like)))
    if city:
        query = query.filter(models.Property.city == city)
    if property_type:
        query = query.filter(models.Property.property_type == property_type)

    # Sorting on stored columns happens in SQL; risk_category needs the full
    # risk engine run first (it isn't a plain column filter), so it's handled
    # after fetch, same pattern as before Phase 4.
    if risk_category:
        all_rows = query.all()
        scored = []
        for p in all_rows:
            result = compute_property_risk(p, db)
            if result.category == risk_category:
                scored.append((p, result.score, result.category))
        total = len(scored)
        start = (page - 1) * page_size
        page_rows = scored[start:start + page_size]
        results = []
        for p, score, category in page_rows:
            out = PropertyOut.model_validate(p)
            out.risk_score, out.risk_category = score, category
            results.append(out)
        return PropertyListResponse(total=total, count=len(results), page=page, page_size=page_size, properties=results)

    sort_col = SORTABLE_FIELDS.get(sort_by, models.Property.name)
    query = query.order_by(desc(sort_col) if sort_dir == "desc" else asc(sort_col))

    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()

    results = []
    for p in rows:
        result = compute_property_risk(p, db)
        out = PropertyOut.model_validate(p)
        out.risk_score, out.risk_category = result.score, result.category
        results.append(out)

    return PropertyListResponse(total=total, count=len(results), page=page, page_size=page_size, properties=results)


@router.get("/{property_id}", response_model=PropertyDetail)
def get_property(property_id: str, db: Session = Depends(get_db)):
    prop = db.query(models.Property).filter(models.Property.id == property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail=f"Property '{property_id}' not found")

    risk_result = compute_property_risk(prop, db)

    tenants = [TenantOut.model_validate(t) for t in prop.tenants]

    leases_out = []
    for l in prop.leases:
        leases_out.append(LeaseOut(
            id=l.id, property_id=l.property_id, property_name=prop.name,
            tenant_id=l.tenant_id, tenant_name=l.tenant_name,
            lease_start=l.lease_start, lease_end=l.lease_end, annual_rent=l.annual_rent,
            renewal_status=l.renewal_status,
            lease_status=compute_lease_status(l.lease_end) if l.lease_end else "Unknown",
            days_to_expiry=days_to_expiry(l.lease_end) if l.lease_end else None,
        ))

    history = sorted(prop.metrics, key=lambda m: m.month)
    history_out = [MonthlyPoint(month=m.month, revenue=m.revenue, occupancy_pct=m.occupancy_pct,
                                 operating_expense=m.operating_expense) for m in history]

    revenue = prop.annual_revenue or 0
    opex = prop.operating_expenses or 0
    noi = round(revenue - opex, 2)

    detail = PropertyDetail(
        **PropertyOut.model_validate(prop).model_dump(),
        net_operating_income=noi,
        tenants=tenants,
        leases=leases_out,
        history=history_out,
    )
    detail.risk_score, detail.risk_category = risk_result.score, risk_result.category
    return detail


@router.get("/meta/filters")
def get_filter_options(db: Session = Depends(get_db)):
    """Distinct values for building dropdown filters on the frontend."""
    cities = [c[0] for c in db.query(models.Property.city).distinct() if c[0]]
    types = [t[0] for t in db.query(models.Property.property_type).distinct() if t[0]]
    return {"cities": sorted(cities), "property_types": sorted(types), "risk_categories": ["Low", "Medium", "High"]}
