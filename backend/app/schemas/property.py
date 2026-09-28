from pydantic import BaseModel
from datetime import date
from typing import Optional


class PropertyOut(BaseModel):
    id: str
    name: str
    city: Optional[str] = None
    state: Optional[str] = None
    property_type: Optional[str] = None
    area_sqft: Optional[float] = None
    occupancy_pct: Optional[float] = None
    annual_revenue: Optional[float] = None
    operating_expenses: Optional[float] = None
    property_value: Optional[float] = None
    num_tenants: int = 0
    risk_score: Optional[float] = None
    risk_category: Optional[str] = None

    class Config:
        from_attributes = True


class PropertyListResponse(BaseModel):
    total: int
    count: int
    page: int
    page_size: int
    properties: list[PropertyOut]


class TenantOut(BaseModel):
    id: str
    tenant_name: str
    industry: Optional[str] = None

    class Config:
        from_attributes = True


class LeaseOut(BaseModel):
    id: str
    property_id: Optional[str] = None
    property_name: Optional[str] = None
    tenant_id: Optional[str] = None
    tenant_name: Optional[str] = None
    lease_start: Optional[date] = None
    lease_end: Optional[date] = None
    annual_rent: Optional[float] = None
    renewal_status: Optional[str] = None
    lease_status: str  # computed: Active / Expiring Soon / Expired / Unknown
    days_to_expiry: Optional[int] = None


class LeaseListResponse(BaseModel):
    total: int
    count: int
    page: int
    page_size: int
    leases: list[LeaseOut]


class MonthlyPoint(BaseModel):
    month: date
    revenue: Optional[float] = None
    occupancy_pct: Optional[float] = None
    operating_expense: Optional[float] = None


class PropertyDetail(PropertyOut):
    net_operating_income: Optional[float] = None
    tenants: list[TenantOut] = []
    leases: list[LeaseOut] = []
    history: list[MonthlyPoint] = []


class DashboardSummary(BaseModel):
    total_properties: int
    total_portfolio_value: float
    annual_revenue: float
    average_occupancy: float
    high_risk_properties: int
    leases_expiring_90_days: int
    data_quality_score: float

    revenue_by_month: list[dict]
    occupancy_trend: list[dict]
    property_type_distribution: list[dict]
    risk_distribution: list[dict]
    revenue_by_city: list[dict]
    lease_expirations_by_month: list[dict]
