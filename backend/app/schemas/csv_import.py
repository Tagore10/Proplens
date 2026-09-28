from pydantic import BaseModel
from typing import Optional


class RowIssueOut(BaseModel):
    row_number: int
    field: Optional[str] = None
    severity: str  # "reject" or "warning"
    message: str


class ImportResult(BaseModel):
    filename: str
    status: str  # "success" | "partial" | "rejected" | "empty" | "error"
    total_rows: int
    valid_rows: int
    rejected_rows: int
    imported_property_ids: list[str]
    issue_counts: dict[str, int]
    row_issues: list[RowIssueOut]
    message: str
