from sqlalchemy import Column, String, Float, Date, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Lease(Base):
    __tablename__ = "leases"

    id = Column(String, primary_key=True, index=True)  # e.g. LSE0001
    property_id = Column(String, ForeignKey("properties.id"), nullable=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=True)
    tenant_name = Column(String, nullable=True)  # denormalized for quick display / CSV import robustness

    lease_start = Column(Date, nullable=True)
    lease_end = Column(Date, nullable=True)
    annual_rent = Column(Float, nullable=True)
    renewal_status = Column(String, nullable=True)  # e.g. "Pending", "Renewed", "Not Renewing"

    # NOTE: lease_status ("Active" / "Expiring Soon" / "Expired") is NOT stored here.
    # It is always derived at read-time from lease_end vs. today (see services/lease_status.py)
    # so it can never go stale.

    property = relationship("Property", back_populates="leases")
    tenant = relationship("Tenant", back_populates="leases")
