"""
CSV Import for properties (optionally with an embedded primary lease/tenant).

DESIGN: one CSV row = one property, with optional tenant/lease columns for
that property's primary lease. This lets a single import exercise the full
range of validation rules the spec asks for (duplicate property IDs,
duplicate tenants, invalid occupancy, negative financials, invalid lease
dates, city/state mismatches) in one coherent flow, and mirrors how a real
portfolio spreadsheet is usually structured — one row per asset.

REQUIRED COLUMNS: id, name
OPTIONAL COLUMNS: city, state, property_type, area_sqft, occupancy_pct,
  annual_revenue, operating_expenses, property_value, tenant_name,
  lease_start, lease_end, annual_rent

VALIDATION REUSE: the actual rule logic (what counts as invalid occupancy, a
negative value, a bad date range, or a city/state mismatch) is imported
directly from app.analytics.data_quality — the same functions the Data
Quality Engine runs against the live database. This file does not redefine
any of those thresholds; it only handles CSV-specific concerns (parsing,
required-field checks, and duplicate detection against both the file itself
and the existing database).

SAFETY: validation happens entirely before any database write. Only rows
that pass every check are attempted for insertion, and that insertion
happens inside a single transaction — if anything goes wrong during the
insert itself, the whole transaction is rolled back and the database is left
exactly as it was before the import.
"""
import csv
import io
import uuid
from datetime import datetime, date
from dataclasses import dataclass, field
from sqlalchemy.orm import Session
from app import models
from app.analytics.data_quality import (
    is_invalid_occupancy, is_negative, is_invalid_date_range, is_location_mismatched,
)

REQUIRED_COLUMNS = ["id", "name"]
NUMERIC_COLUMNS = ["area_sqft", "occupancy_pct", "annual_revenue", "operating_expenses",
                   "property_value", "annual_rent"]
DATE_COLUMNS = ["lease_start", "lease_end"]


@dataclass
class RowIssue:
    row_number: int
    field: str | None
    severity: str  # "reject" or "warning"
    message: str


@dataclass
class ParsedRow:
    row_number: int
    data: dict
    issues: list = field(default_factory=list)

    @property
    def rejected(self) -> bool:
        return any(i.severity == "reject" for i in self.issues)


def _parse_float(raw: str, field_name: str, row_number: int, issues: list) -> float | None:
    raw = (raw or "").strip()
    if raw == "":
        return None
    try:
        return float(raw)
    except ValueError:
        issues.append(RowIssue(row_number, field_name, "reject",
                                f"'{field_name}' is not a valid number: '{raw}'"))
        return None


def _parse_date(raw: str, field_name: str, row_number: int, issues: list) -> date | None:
    raw = (raw or "").strip()
    if raw == "":
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    issues.append(RowIssue(row_number, field_name, "reject",
                            f"'{field_name}' is not a recognized date (use YYYY-MM-DD): '{raw}'"))
    return None


def validate_structure(header: list) -> list[str]:
    """Returns a list of missing required columns (empty list = structurally OK)."""
    if header is None:
        return REQUIRED_COLUMNS
    normalized = [h.strip() for h in header]
    return [col for col in REQUIRED_COLUMNS if col not in normalized]


def parse_and_validate_rows(reader: csv.DictReader, db: Session) -> list[ParsedRow]:
    """Parses every row and runs all validation, but touches the database
    only for read-only existence checks (existing IDs/tenant names) — no
    writes happen here."""
    existing_property_ids = {pid for (pid,) in db.query(models.Property.id).all()}
    existing_tenant_names = {name for (name,) in db.query(models.Tenant.tenant_name).all() if name}

    seen_ids_in_file = set()
    seen_tenant_names_in_file = set()
    parsed_rows = []

    for row_number, raw_row in enumerate(reader, start=2):  # row 1 is the header
        issues = []
        row = {k: (v or "").strip() for k, v in raw_row.items()}

        property_id = row.get("id", "").strip()
        name = row.get("name", "").strip()

        if not property_id:
            issues.append(RowIssue(row_number, "id", "reject", "Missing required field 'id'"))
        if not name:
            issues.append(RowIssue(row_number, "name", "reject", "Missing required field 'name'"))

        # Duplicate property ID: within this file, or already in the database.
        if property_id:
            if property_id in seen_ids_in_file:
                issues.append(RowIssue(row_number, "id", "reject",
                                        f"Duplicate property ID within this file: '{property_id}'"))
            elif property_id in existing_property_ids:
                issues.append(RowIssue(row_number, "id", "reject",
                                        f"Property ID already exists in the database: '{property_id}'"))
            seen_ids_in_file.add(property_id)

        city = row.get("city") or None
        state = row.get("state") or None
        property_type = row.get("property_type") or None

        if not city:
            issues.append(RowIssue(row_number, "city", "warning", "Missing 'city'"))
        if not state:
            issues.append(RowIssue(row_number, "state", "warning", "Missing 'state'"))

        area_sqft = _parse_float(row.get("area_sqft", ""), "area_sqft", row_number, issues)
        occupancy_pct = _parse_float(row.get("occupancy_pct", ""), "occupancy_pct", row_number, issues)
        annual_revenue = _parse_float(row.get("annual_revenue", ""), "annual_revenue", row_number, issues)
        operating_expenses = _parse_float(row.get("operating_expenses", ""), "operating_expenses", row_number, issues)
        property_value = _parse_float(row.get("property_value", ""), "property_value", row_number, issues)

        if is_invalid_occupancy(occupancy_pct):
            issues.append(RowIssue(row_number, "occupancy_pct", "reject",
                                    f"Occupancy out of range (0-100): {occupancy_pct}"))
        if is_negative(annual_revenue):
            issues.append(RowIssue(row_number, "annual_revenue", "reject",
                                    f"Negative annual_revenue: {annual_revenue}"))
        if is_negative(property_value):
            issues.append(RowIssue(row_number, "property_value", "reject",
                                    f"Negative property_value: {property_value}"))
        if is_location_mismatched(city, state):
            issues.append(RowIssue(row_number, "state", "warning",
                                    f"City '{city}' is not usually paired with state '{state}'"))

        # Optional embedded lease/tenant
        tenant_name = row.get("tenant_name") or None
        lease_start = _parse_date(row.get("lease_start", ""), "lease_start", row_number, issues)
        lease_end = _parse_date(row.get("lease_end", ""), "lease_end", row_number, issues)
        annual_rent = _parse_float(row.get("annual_rent", ""), "annual_rent", row_number, issues)

        if tenant_name:
            if tenant_name in seen_tenant_names_in_file or tenant_name in existing_tenant_names:
                issues.append(RowIssue(row_number, "tenant_name", "reject",
                                        f"Duplicate tenant name: '{tenant_name}'"))
            seen_tenant_names_in_file.add(tenant_name)

        if is_negative(annual_rent):
            issues.append(RowIssue(row_number, "annual_rent", "reject", f"Negative annual_rent: {annual_rent}"))
        if is_invalid_date_range(lease_start, lease_end):
            issues.append(RowIssue(row_number, "lease_end", "reject",
                                    f"Lease ends ({lease_end}) before it starts ({lease_start})"))

        parsed_rows.append(ParsedRow(
            row_number=row_number,
            data={
                "id": property_id, "name": name, "city": city, "state": state,
                "property_type": property_type, "area_sqft": area_sqft,
                "occupancy_pct": occupancy_pct, "annual_revenue": annual_revenue,
                "operating_expenses": operating_expenses, "property_value": property_value,
                "tenant_name": tenant_name, "lease_start": lease_start, "lease_end": lease_end,
                "annual_rent": annual_rent,
            },
            issues=issues,
        ))

    return parsed_rows


def import_properties_csv(db: Session, file_bytes: bytes, filename: str) -> dict:
    """Full flow: decode -> parse -> validate -> transactionally insert valid
    rows. Returns a summary dict; never raises on bad input data (only on
    something going genuinely wrong, e.g. an unreadable file)."""
    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        return {
            "structural_error": "The file could not be read as UTF-8 text. "
                                 "Please upload a plain-text CSV file.",
        }

    reader = csv.DictReader(io.StringIO(text))
    missing_columns = validate_structure(reader.fieldnames)
    if missing_columns:
        return {
            "structural_error": f"Missing required column(s): {', '.join(missing_columns)}. "
                                 f"Required: {', '.join(REQUIRED_COLUMNS)}.",
        }

    parsed_rows = parse_and_validate_rows(reader, db)
    total_rows = len(parsed_rows)
    valid_rows = [r for r in parsed_rows if not r.rejected]
    rejected_rows = [r for r in parsed_rows if r.rejected]

    issue_counts: dict[str, int] = {}
    all_issues: list[RowIssue] = []
    for r in parsed_rows:
        all_issues.extend(r.issues)
    for issue in all_issues:
        key = "rejected" if issue.severity == "reject" else "warning"
        issue_counts[key] = issue_counts.get(key, 0) + 1

    imported_ids: list[str] = []
    import_error = None

    if valid_rows:
        try:
            for r in valid_rows:
                d = r.data
                prop = models.Property(
                    id=d["id"], name=d["name"], city=d["city"], state=d["state"],
                    property_type=d["property_type"], area_sqft=d["area_sqft"],
                    occupancy_pct=d["occupancy_pct"], annual_revenue=d["annual_revenue"],
                    operating_expenses=d["operating_expenses"], property_value=d["property_value"],
                    num_tenants=1 if d["tenant_name"] else 0,
                )
                db.add(prop)

                if d["tenant_name"]:
                    tenant_id = f"TEN-IMP-{uuid.uuid4().hex[:8].upper()}"
                    tenant = models.Tenant(id=tenant_id, property_id=d["id"], tenant_name=d["tenant_name"])
                    db.add(tenant)

                    if d["lease_start"] or d["lease_end"] or d["annual_rent"] is not None:
                        lease_id = f"LSE-IMP-{uuid.uuid4().hex[:8].upper()}"
                        lease = models.Lease(
                            id=lease_id, property_id=d["id"], tenant_id=tenant_id,
                            tenant_name=d["tenant_name"], lease_start=d["lease_start"],
                            lease_end=d["lease_end"], annual_rent=d["annual_rent"],
                        )
                        db.add(lease)

                imported_ids.append(d["id"])

            db.commit()
        except Exception as exc:  # noqa: BLE001 - deliberately broad: any DB failure must roll back
            db.rollback()
            import_error = str(exc)
            imported_ids = []

    return {
        "structural_error": None,
        "filename": filename,
        "total_rows": total_rows,
        "valid_rows": len(valid_rows) if import_error is None else 0,
        "rejected_rows": len(rejected_rows) if import_error is None else total_rows,
        "imported_property_ids": imported_ids,
        "issue_counts": issue_counts,
        "row_issues": [
            {"row_number": i.row_number, "field": i.field, "severity": i.severity, "message": i.message}
            for i in all_issues
        ],
        "import_error": import_error,
    }
