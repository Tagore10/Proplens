from sqlalchemy import Column, String, Integer, DateTime
from datetime import datetime, timezone
from app.database import Base


class DataQualityIssue(Base):
    """Persisted record of one detected data-quality issue, so the Data Quality
    page can list/inspect affected records without re-running detection every time."""
    __tablename__ = "data_quality_issues"

    id = Column(Integer, primary_key=True, autoincrement=True)
    issue_type = Column(String, nullable=False)  # e.g. "missing_value", "duplicate", "invalid_range", "outlier"
    entity_type = Column(String, nullable=False)  # "property", "tenant", "lease"
    entity_id = Column(String, nullable=True)
    field = Column(String, nullable=True)  # which column was affected, if applicable
    description = Column(String, nullable=False)
    severity = Column(String, nullable=False)  # "low", "medium", "high"
    detected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
