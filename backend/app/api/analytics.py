from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.analytics import portfolio_analytics as pa
from app.schemas.analytics import PortfolioAnalytics, RevenueAnalytics, OccupancyAnalytics

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/portfolio", response_model=PortfolioAnalytics)
def get_portfolio_analytics(db: Session = Depends(get_db)):
    """Full portfolio-level rollup: financials (NOI, NOI margin, opex ratio),
    occupancy, revenue growth, and the three breakdown dimensions."""
    financials = pa.portfolio_financials(db)
    growth = pa.revenue_growth(db)

    return PortfolioAnalytics(
        total_revenue=financials["total_revenue"],
        total_operating_expenses=financials["total_operating_expenses"],
        net_operating_income=financials["net_operating_income"],
        noi_margin_pct=financials["noi_margin_pct"],
        operating_expense_ratio_pct=financials["operating_expense_ratio_pct"],
        average_occupancy=financials["average_occupancy"],
        revenue_growth_mom_pct=growth["month_over_month_pct"],
        revenue_growth_3mo_pct=growth["trailing_3_month_pct"],
        revenue_by_city=pa.revenue_by_city(db),
        revenue_by_property_type=pa.revenue_by_property_type(db),
        occupancy_by_property_type=pa.occupancy_by_property_type(db),
    )


@router.get("/revenue", response_model=RevenueAnalytics)
def get_revenue_analytics(db: Session = Depends(get_db)):
    """Revenue-focused view: monthly trend, growth rates, and breakdowns by
    city and property type."""
    growth = pa.revenue_growth(db)

    return RevenueAnalytics(
        monthly_trend=growth["monthly_trend"],
        growth_month_over_month_pct=growth["month_over_month_pct"],
        growth_trailing_3_month_pct=growth["trailing_3_month_pct"],
        revenue_by_city=pa.revenue_by_city(db),
        revenue_by_property_type=pa.revenue_by_property_type(db),
    )


@router.get("/occupancy", response_model=OccupancyAnalytics)
def get_occupancy_analytics(db: Session = Depends(get_db)):
    """Occupancy-focused view: monthly trend, portfolio average, and
    breakdown by property type."""
    financials = pa.portfolio_financials(db)

    return OccupancyAnalytics(
        monthly_trend=pa.monthly_occupancy_trend(db),
        average_occupancy=financials["average_occupancy"],
        occupancy_by_property_type=pa.occupancy_by_property_type(db),
    )
