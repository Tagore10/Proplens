from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app import models
from app.analytics.data_quality import run_data_quality_scan

router = APIRouter(prefix="/api/data-quality", tags=["data-quality"])


@router.get("")
def get_data_quality_report(db: Session = Depends(get_db)):
    """Overall data quality score + category counts. Re-runs the full scan
    against the current database on every call (see analytics/data_quality.py)."""
    return run_data_quality_scan(db)


@router.get("/issues")
def list_data_quality_issues(
    db: Session = Depends(get_db),
    issue_type: Optional[str] = Query(None, description="missing_value, duplicate, invalid_value, date_issue, outlier, location_mismatch"),
    entity_type: Optional[str] = Query(None, description="property, tenant, or lease"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Lets the Data Quality page let a user inspect the specific affected
    records behind the summary counts. Reads whatever the most recent scan
    persisted — call GET /api/data-quality first (or just before) to refresh."""
    query = db.query(models.DataQualityIssue)
    if issue_type:
        query = query.filter(models.DataQualityIssue.issue_type == issue_type)
    if entity_type:
        query = query.filter(models.DataQualityIssue.entity_type == entity_type)

    total = query.count()
    rows = (
        query.order_by(models.DataQualityIssue.severity.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "count": len(rows),
        "page": page,
        "page_size": page_size,
        "issues": [
            {
                "id": r.id,
                "issue_type": r.issue_type,
                "entity_type": r.entity_type,
                "entity_id": r.entity_id,
                "field": r.field,
                "description": r.description,
                "severity": r.severity,
            }
            for r in rows
        ],
    }
