"""
Portfolio Analytics.

Reusable, database-backed aggregation functions. Nothing here is hardcoded —
every function queries the current state of the DB. These are used by both
the /api/analytics/* endpoints (Phase 5) and the dashboard summary (Phase 2),
so the two never disagree with each other.

DEFINITIONS (documented per spec, kept deliberately simple):

    NOI (Net Operating Income) = Annual Revenue - Operating Expenses
    NOI Margin                 = NOI / Annual Revenue * 100
    Operating Expense Ratio    = Operating Expenses / Annual Revenue * 100
                                  (equivalently: 100 - NOI Margin)

    Revenue Growth (MoM)       = (this month's total revenue - last month's) / last month's * 100
    Revenue Growth (3-month)   = (avg of last 3 months - avg of the 3 months before that) / that avg * 100
                                  (same method as the per-property revenue-trend risk factor,
                                  applied at the portfolio level)

All financial totals use the properties' current annual_revenue /
operating_expenses columns (the same fields the Property Detail page's NOI
calculation uses), so a portfolio-level NOI is consistent with the sum of
each property's own NOI. Monthly trend figures instead use property_metrics,
since that's the only table with a month-by-month history.

Every function safely returns zero/empty results on an empty or all-None
dataset rather than raising a ZeroDivisionError or similar.
"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from app import models


def portfolio_financials(db: Session) -> dict:
    """Portfolio-wide revenue, opex, NOI, NOI margin, and opex ratio —
    all summed from each property's current annual figures."""
    total_revenue = db.query(func.sum(models.Property.annual_revenue)).scalar() or 0.0
    total_opex = db.query(func.sum(models.Property.operating_expenses)).scalar() or 0.0
    noi = total_revenue - total_opex

    noi_margin_pct = round((noi / total_revenue) * 100, 2) if total_revenue else 0.0
    opex_ratio_pct = round((total_opex / total_revenue) * 100, 2) if total_revenue else 0.0

    occ_values = [
        v for (v,) in db.query(models.Property.occupancy_pct)
        .filter(models.Property.occupancy_pct.isnot(None))
        .all()
    ]
    average_occupancy = round(sum(occ_values) / len(occ_values), 1) if occ_values else 0.0

    return {
        "total_revenue": round(total_revenue, 2),
        "total_operating_expenses": round(total_opex, 2),
        "net_operating_income": round(noi, 2),
        "noi_margin_pct": noi_margin_pct,
        "operating_expense_ratio_pct": opex_ratio_pct,
        "average_occupancy": average_occupancy,
    }


def monthly_revenue_trend(db: Session) -> list[dict]:
    """Portfolio-wide revenue summed by month, from property_metrics."""
    rows = (
        db.query(models.PropertyMetric.month, func.sum(models.PropertyMetric.revenue))
        .filter(models.PropertyMetric.revenue.isnot(None))
        .group_by(models.PropertyMetric.month)
        .order_by(models.PropertyMetric.month)
        .all()
    )
    return [{"month": str(m), "revenue": round(r or 0, 2)} for m, r in rows]


def monthly_occupancy_trend(db: Session) -> list[dict]:
    """Portfolio-wide average occupancy by month, from property_metrics."""
    rows = (
        db.query(models.PropertyMetric.month, func.avg(models.PropertyMetric.occupancy_pct))
        .filter(models.PropertyMetric.occupancy_pct.isnot(None))
        .group_by(models.PropertyMetric.month)
        .order_by(models.PropertyMetric.month)
        .all()
    )
    return [{"month": str(m), "avg_occupancy": round(o or 0, 1)} for m, o in rows]


def revenue_growth(db: Session) -> dict:
    """Month-over-month and trailing-3-month revenue growth, derived from
    monthly_revenue_trend(). Returns None for either figure when there isn't
    enough history to compute it (rather than a misleading 0%)."""
    trend = monthly_revenue_trend(db)

    mom_pct = None
    if len(trend) >= 2 and trend[-2]["revenue"]:
        mom_pct = round((trend[-1]["revenue"] - trend[-2]["revenue"]) / trend[-2]["revenue"] * 100, 2)

    three_month_pct = None
    if len(trend) >= 6:
        recent = [p["revenue"] for p in trend[-3:]]
        prior = [p["revenue"] for p in trend[-6:-3]]
        avg_recent = sum(recent) / len(recent)
        avg_prior = sum(prior) / len(prior)
        if avg_prior:
            three_month_pct = round((avg_recent - avg_prior) / avg_prior * 100, 2)

    return {"month_over_month_pct": mom_pct, "trailing_3_month_pct": three_month_pct, "monthly_trend": trend}


def revenue_by_city(db: Session) -> list[dict]:
    rows = (
        db.query(models.Property.city, func.sum(models.Property.annual_revenue))
        .group_by(models.Property.city)
        .all()
    )
    return [{"city": c or "Unknown", "revenue": round(r or 0, 2)} for c, r in rows]


def revenue_by_property_type(db: Session) -> list[dict]:
    rows = (
        db.query(models.Property.property_type, func.sum(models.Property.annual_revenue))
        .group_by(models.Property.property_type)
        .all()
    )
    return [{"property_type": t or "Unknown", "revenue": round(r or 0, 2)} for t, r in rows]


def occupancy_by_property_type(db: Session) -> list[dict]:
    rows = (
        db.query(models.Property.property_type, func.avg(models.Property.occupancy_pct))
        .filter(models.Property.occupancy_pct.isnot(None))
        .group_by(models.Property.property_type)
        .all()
    )
    return [{"property_type": t or "Unknown", "avg_occupancy": round(o or 0, 1)} for t, o in rows]


def property_type_distribution(db: Session) -> list[dict]:
    """Count of properties per type (not revenue) — used by the dashboard's
    'property type distribution' chart."""
    rows = (
        db.query(models.Property.property_type, func.count(models.Property.id))
        .group_by(models.Property.property_type)
        .all()
    )
    return [{"type": t or "Unknown", "count": c} for t, c in rows]
