from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String, primary_key=True, index=True)  # e.g. TEN0001
    property_id = Column(String, ForeignKey("properties.id"), nullable=True)
    tenant_name = Column(String, nullable=False)
    industry = Column(String, nullable=True)

    property = relationship("Property", back_populates="tenants")
    leases = relationship("Lease", back_populates="tenant")
