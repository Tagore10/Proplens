from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, timedelta

from app.database import get_db
from app import models
from app.analytics.risk_engine import compute_property_risk
from app.analytics.data_quality import run_data_quality_scan
from app.analytics import portfolio_analytics as pa
from app.schemas.property import DashboardSummary

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(db: Session = Depends(get_db)):
    properties = db.query(models.Property).all()
    total_properties = len(properties)

    total_portfolio_value = sum(p.property_value or 0 for p in properties)
    annual_revenue = sum(p.annual_revenue or 0 for p in properties)
    occ_values = [p.occupancy_pct for p in properties if p.occupancy_pct is not None]
    average_occupancy = round(sum(occ_values) / len(occ_values), 1) if occ_values else 0.0

    # Risk: full weighted risk engine, computed per property (see analytics/risk_engine.py)
    risk_counts = {"Low": 0, "Medium": 0, "High": 0}
    for p in properties:
        result = compute_property_risk(p, db)
        risk_counts[result.category] = risk_counts.get(result.category, 0) + 1
    high_risk_properties = risk_counts["High"]

    horizon = date.today() + timedelta(days=90)
    leases_expiring_90_days = (
        db.query(func.count(models.Lease.id))
        .filter(models.Lease.lease_end.isnot(None))
        .filter(models.Lease.lease_end >= date.today())
        .filter(models.Lease.lease_end <= horizon)
        .scalar()
    ) or 0

    data_quality_score = run_data_quality_scan(db)["overall_score"]

    # --- Chart 1: revenue by month (aggregated across all properties) ---
    revenue_by_month = pa.monthly_revenue_trend(db)

    # --- Chart 2: occupancy trend (portfolio average by month) ---
    occupancy_trend = pa.monthly_occupancy_trend(db)

    # --- Chart 3: property type distribution ---
    property_type_distribution = pa.property_type_distribution(db)

    # --- Chart 4: risk distribution ---
    risk_distribution = [{"category": k, "count": v} for k, v in risk_counts.items()]

    # --- Chart 5: revenue by city ---
    revenue_by_city = pa.revenue_by_city(db)

    # --- Chart 6: lease expirations by month (next 12 months) ---
    today = date.today()
    expirations_by_month = []
    for i in range(12):
        month_start = (today.replace(day=1) + timedelta(days=32 * i)).replace(day=1)
        next_month = (month_start + timedelta(days=32)).replace(day=1)
        count = (
            db.query(func.count(models.Lease.id))
            .filter(models.Lease.lease_end >= month_start)
            .filter(models.Lease.lease_end < next_month)
            .scalar()
        ) or 0
        expirations_by_month.append({"month": month_start.strftime("%Y-%m"), "expiring_leases": count})

    return DashboardSummary(
        total_properties=total_properties,
        total_portfolio_value=round(total_portfolio_value, 2),
        annual_revenue=round(annual_revenue, 2),
        average_occupancy=average_occupancy,
        high_risk_properties=high_risk_properties,
        leases_expiring_90_days=leases_expiring_90_days,
        data_quality_score=data_quality_score,
        revenue_by_month=revenue_by_month,
        occupancy_trend=occupancy_trend,
        property_type_distribution=property_type_distribution,
        risk_distribution=risk_distribution,
        revenue_by_city=revenue_by_city,
        lease_expirations_by_month=expirations_by_month,
    )
