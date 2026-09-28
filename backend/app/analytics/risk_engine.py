"""
Risk Engine — explainable, weighted property risk scoring.

This replaces the Phase 2 interim `property_risk_quick` placeholder with the
full system from the spec: five transparent, independently-computed factors,
each normalized to 0-100, combined by fixed weights. No black-box model —
every score can be fully explained by pointing at its five inputs.

    Factor                | Weight | What it measures
    -----------------------|--------|----------------------------------------
    Occupancy Risk         | 30%    | How full the property currently is
    Lease Expiry Risk      | 25%    | How soon (or overdue) its leases expire
    Revenue Trend Risk     | 20%    | Whether monthly revenue is declining
    Operating Expense Risk | 15%    | Opex as a share of revenue
    Data Quality Risk      | 10%    | Unresolved data-quality issues on this property

    Final score = 0.30*occupancy + 0.25*lease + 0.20*revenue_trend
                  + 0.15*opex + 0.10*data_quality

    0-39   -> Low
    40-69  -> Medium
    70-100 -> High

Each factor also produces a human-readable reason string when it's a
meaningful contributor, so a property's risk can be explained in one line
per factor (e.g. "Occupancy below 65%"), not just a bare number.
"""
from datetime import date
from dataclasses import dataclass, field
from sqlalchemy.orm import Session
from app import models
from app.utils.lease_status import compute_lease_status, days_to_expiry

WEIGHTS = {
    "occupancy": 0.30,
    "lease_expiry": 0.25,
    "revenue_trend": 0.20,
    "opex": 0.15,
    "data_quality": 0.10,
}


@dataclass
class RiskFactor:
    name: str
    value: float  # 0-100
    weight: float
    reason: str | None = None

    @property
    def contribution(self) -> float:
        return self.value * self.weight


@dataclass
class RiskResult:
    score: float
    category: str
    factors: list[RiskFactor] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


def _occupancy_risk(prop: models.Property) -> RiskFactor:
    occ = prop.occupancy_pct
    if occ is None:
        return RiskFactor("occupancy", 65.0, WEIGHTS["occupancy"], "Occupancy data is missing")
    if occ < 0 or occ > 100:
        return RiskFactor("occupancy", 100.0, WEIGHTS["occupancy"], "Occupancy value is invalid/out of range")
    if occ < 50:
        return RiskFactor("occupancy", 100.0, WEIGHTS["occupancy"], "Occupancy below 50%")
    if occ < 65:
        return RiskFactor("occupancy", 75.0, WEIGHTS["occupancy"], "Occupancy below 65%")
    if occ < 80:
        return RiskFactor("occupancy", 45.0, WEIGHTS["occupancy"], "Occupancy below 80%")
    if occ < 90:
        return RiskFactor("occupancy", 20.0, WEIGHTS["occupancy"], None)
    return RiskFactor("occupancy", 5.0, WEIGHTS["occupancy"], None)


def _lease_expiry_risk(prop: models.Property, db: Session) -> RiskFactor:
    leases = db.query(models.Lease).filter(models.Lease.property_id == prop.id).all()
    dated = [l for l in leases if l.lease_end is not None]

    if not dated:
        return RiskFactor("lease_expiry", 50.0, WEIGHTS["lease_expiry"], "No lease data on file for this property")

    expired = [l for l in dated if compute_lease_status(l.lease_end) == "Expired"]
    if expired:
        return RiskFactor("lease_expiry", 100.0, WEIGHTS["lease_expiry"],
                           f"{len(expired)} lease(s) have already expired")

    upcoming = [l for l in dated if l.lease_end >= date.today()]
    nearest_days = min(days_to_expiry(l.lease_end) for l in upcoming) if upcoming else None

    if nearest_days is None:
        return RiskFactor("lease_expiry", 30.0, WEIGHTS["lease_expiry"], None)
    if nearest_days <= 60:
        return RiskFactor("lease_expiry", 90.0, WEIGHTS["lease_expiry"], "Lease expires within 60 days")
    if nearest_days <= 90:
        return RiskFactor("lease_expiry", 70.0, WEIGHTS["lease_expiry"], "Lease expires within 90 days")
    if nearest_days <= 180:
        return RiskFactor("lease_expiry", 40.0, WEIGHTS["lease_expiry"], None)
    if nearest_days <= 365:
        return RiskFactor("lease_expiry", 20.0, WEIGHTS["lease_expiry"], None)
    return RiskFactor("lease_expiry", 5.0, WEIGHTS["lease_expiry"], None)


def _revenue_trend_risk(prop: models.Property, db: Session) -> RiskFactor:
    metrics = (
        db.query(models.PropertyMetric)
        .filter(models.PropertyMetric.property_id == prop.id)
        .filter(models.PropertyMetric.revenue.isnot(None))
        .order_by(models.PropertyMetric.month)
        .all()
    )
    if len(metrics) < 6:
        return RiskFactor("revenue_trend", 40.0, WEIGHTS["revenue_trend"],
                           "Not enough revenue history to assess trend" if len(metrics) < 3 else None)

    recent = metrics[-3:]
    prior = metrics[-6:-3]
    avg_recent = sum(m.revenue for m in recent) / len(recent)
    avg_prior = sum(m.revenue for m in prior) / len(prior)

    if avg_prior == 0:
        return RiskFactor("revenue_trend", 40.0, WEIGHTS["revenue_trend"], None)

    pct_change = (avg_recent - avg_prior) / avg_prior * 100

    if pct_change <= -15:
        return RiskFactor("revenue_trend", 100.0, WEIGHTS["revenue_trend"],
                           f"Revenue declined {abs(pct_change):.0f}% over the last 3 months")
    if pct_change <= -5:
        return RiskFactor("revenue_trend", 65.0, WEIGHTS["revenue_trend"],
                           f"Revenue declined {abs(pct_change):.0f}% over the last 3 months")
    if pct_change <= 5:
        return RiskFactor("revenue_trend", 30.0, WEIGHTS["revenue_trend"], None)
    if pct_change <= 15:
        return RiskFactor("revenue_trend", 15.0, WEIGHTS["revenue_trend"], None)
    return RiskFactor("revenue_trend", 5.0, WEIGHTS["revenue_trend"], None)


def _opex_risk(prop: models.Property) -> RiskFactor:
    revenue = prop.annual_revenue
    opex = prop.operating_expenses
    if revenue is None or opex is None or revenue <= 0:
        return RiskFactor("opex", 50.0, WEIGHTS["opex"], None)

    ratio = opex / revenue
    if ratio > 0.60:
        return RiskFactor("opex", 100.0, WEIGHTS["opex"], "Operating expenses exceed 60% of revenue")
    if ratio > 0.45:
        return RiskFactor("opex", 60.0, WEIGHTS["opex"], "Operating expenses exceed 45% of revenue")
    if ratio > 0.30:
        return RiskFactor("opex", 30.0, WEIGHTS["opex"], None)
    return RiskFactor("opex", 10.0, WEIGHTS["opex"], None)


def _data_quality_risk(prop: models.Property, db: Session) -> RiskFactor:
    issue_count = (
        db.query(models.DataQualityIssue)
        .filter(models.DataQualityIssue.entity_type == "property")
        .filter(models.DataQualityIssue.entity_id == prop.id)
        .count()
    )
    value = min(100.0, issue_count * 40.0)
    reason = None
    if issue_count > 0:
        reason = f"Property has {issue_count} unresolved data quality issue(s)"
    return RiskFactor("data_quality", value, WEIGHTS["data_quality"], reason)


def compute_property_risk(prop: models.Property, db: Session) -> RiskResult:
    """Pure computation — does not write to the database. Used for live reads
    in the Properties/Dashboard pages so numbers never depend on a manual scan."""
    factors = [
        _occupancy_risk(prop),
        _lease_expiry_risk(prop, db),
        _revenue_trend_risk(prop, db),
        _opex_risk(prop),
        _data_quality_risk(prop, db),
    ]

    score = round(sum(f.contribution for f in factors), 1)
    if score >= 70:
        category = "High"
    elif score >= 40:
        category = "Medium"
    else:
        category = "Low"

    # Reasons ranked by how much they actually contributed to the score,
    # so the top reason shown is genuinely the biggest driver, not just the
    # first factor that happened to trigger one.
    reasoned = [f for f in factors if f.reason]
    reasoned.sort(key=lambda f: f.contribution, reverse=True)
    reasons = [f.reason for f in reasoned[:3]]

    return RiskResult(score=score, category=category, factors=factors, reasons=reasons)


def run_risk_scan(db: Session) -> dict:
    """Computes risk for every property and persists risk_score/risk_category
    onto each Property row (per the original schema design). Returns a
    portfolio-level summary. Mirrors the Data Quality Engine's re-scan pattern."""
    properties = db.query(models.Property).all()
    counts = {"Low": 0, "Medium": 0, "High": 0}
    results = []

    for p in properties:
        result = compute_property_risk(p, db)
        p.risk_score = result.score
        p.risk_category = result.category
        counts[result.category] += 1
        results.append({
            "property_id": p.id,
            "property_name": p.name,
            "risk_score": result.score,
            "risk_category": result.category,
            "reasons": result.reasons,
            "factors": {f.name: {"value": f.value, "weight": f.weight} for f in result.factors},
        })

    db.commit()

    results.sort(key=lambda r: r["risk_score"], reverse=True)

    return {
        "total_properties": len(properties),
        "low_risk": counts["Low"],
        "medium_risk": counts["Medium"],
        "high_risk": counts["High"],
        "properties": results,
    }
