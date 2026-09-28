from pydantic import BaseModel
from typing import Optional


class MonthlyRevenuePoint(BaseModel):
    month: str
    revenue: float


class MonthlyOccupancyPoint(BaseModel):
    month: str
    avg_occupancy: float


class RevenueByCity(BaseModel):
    city: str
    revenue: float


class RevenueByType(BaseModel):
    property_type: str
    revenue: float


class OccupancyByType(BaseModel):
    property_type: str
    avg_occupancy: float


class PortfolioAnalytics(BaseModel):
    """GET /api/analytics/portfolio — the full portfolio-level rollup."""
    total_revenue: float
    total_operating_expenses: float
    net_operating_income: float
    noi_margin_pct: float
    operating_expense_ratio_pct: float
    average_occupancy: float
    revenue_growth_mom_pct: Optional[float] = None
    revenue_growth_3mo_pct: Optional[float] = None
    revenue_by_city: list[RevenueByCity]
    revenue_by_property_type: list[RevenueByType]
    occupancy_by_property_type: list[OccupancyByType]


class RevenueAnalytics(BaseModel):
    """GET /api/analytics/revenue — revenue-focused breakdown."""
    monthly_trend: list[MonthlyRevenuePoint]
    growth_month_over_month_pct: Optional[float] = None
    growth_trailing_3_month_pct: Optional[float] = None
    revenue_by_city: list[RevenueByCity]
    revenue_by_property_type: list[RevenueByType]


class OccupancyAnalytics(BaseModel):
    """GET /api/analytics/occupancy — occupancy-focused breakdown."""
    monthly_trend: list[MonthlyOccupancyPoint]
    average_occupancy: float
    occupancy_by_property_type: list[OccupancyByType]
