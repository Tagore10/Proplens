from sqlalchemy import Column, String, Float, Integer, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class Property(Base):
    __tablename__ = "properties"

    id = Column(String, primary_key=True, index=True)  # e.g. PROP0001
    name = Column(String, nullable=False)
    city = Column(String, nullable=True)  # nullable to allow synthetic missing-value issues
    state = Column(String, nullable=True)
    property_type = Column(String, nullable=True)  # Office, Retail, Industrial, Logistics, Mixed Use
    area_sqft = Column(Float, nullable=True)
    occupancy_pct = Column(Float, nullable=True)
    annual_revenue = Column(Float, nullable=True)
    operating_expenses = Column(Float, nullable=True)
    property_value = Column(Float, nullable=True)
    num_tenants = Column(Integer, default=0)

    # Computed/derived by the risk engine and persisted for fast dashboard reads
    risk_score = Column(Float, nullable=True)
    risk_category = Column(String, nullable=True)  # Low, Medium, High

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    tenants = relationship("Tenant", back_populates="property", cascade="all, delete-orphan")
    leases = relationship("Lease", back_populates="property", cascade="all, delete-orphan")
    metrics = relationship("PropertyMetric", back_populates="property", cascade="all, delete-orphan")
