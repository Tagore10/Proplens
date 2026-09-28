from sqlalchemy import Column, String, Float, Date, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class PropertyMetric(Base):
    """One row per property per month — powers trend charts and the forecasting model."""
    __tablename__ = "property_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    property_id = Column(String, ForeignKey("properties.id"), nullable=False)
    month = Column(Date, nullable=False)  # first day of the month, e.g. 2025-01-01

    revenue = Column(Float, nullable=True)
    occupancy_pct = Column(Float, nullable=True)
    operating_expense = Column(Float, nullable=True)

    property = relationship("Property", back_populates="metrics")
