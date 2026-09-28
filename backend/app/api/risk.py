from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app import models
from app.analytics.risk_engine import run_risk_scan, compute_property_risk

router = APIRouter(prefix="/api/risk", tags=["risk"])


@router.get("/properties")
def list_property_risk(
    db: Session = Depends(get_db),
    risk_category: Optional[str] = Query(None, description="Low, Medium, or High"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    """Runs the full risk scan (persisting risk_score/risk_category onto every
    Property row), then returns the results ranked highest-risk first."""
    scan = run_risk_scan(db)
    rows = scan["properties"]

    if risk_category:
        rows = [r for r in rows if r["risk_category"] == risk_category]

    total = len(rows)
    start = (page - 1) * page_size
    page_rows = rows[start:start + page_size]

    return {
        "total_properties": scan["total_properties"],
        "low_risk": scan["low_risk"],
        "medium_risk": scan["medium_risk"],
        "high_risk": scan["high_risk"],
        "total": total,
        "count": len(page_rows),
        "page": page,
        "page_size": page_size,
        "properties": page_rows,
    }


@router.get("/properties/{property_id}")
def get_property_risk(property_id: str, db: Session = Depends(get_db)):
    """Full factor-by-factor breakdown for one property — the detail view
    behind a risk score, for the 'why is this High risk' interview question."""
    prop = db.query(models.Property).filter(models.Property.id == property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail=f"Property '{property_id}' not found")

    result = compute_property_risk(prop, db)
    return {
        "property_id": prop.id,
        "property_name": prop.name,
        "risk_score": result.score,
        "risk_category": result.category,
        "reasons": result.reasons,
        "factors": [
            {
                "name": f.name,
                "value": f.value,
                "weight": f.weight,
                "contribution": round(f.contribution, 2),
                "reason": f.reason,
            }
            for f in result.factors
        ],
    }
