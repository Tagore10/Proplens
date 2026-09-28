"""
Data Quality Engine.

Runs a fixed set of rules against the current database, persists every
finding as a DataQualityIssue row (so the Data Quality page can list and
inspect affected records), and computes an overall score.

METHODOLOGY (documented so it's easy to explain in an interview):

    Start at 100.0.
    For each issue category, deduct:
        deduction = min(category_cap, issues_found * per_issue_weight)
    Final score = max(0, 100 - sum(all category deductions)), rounded to 1 decimal.

    Category        | per-issue weight | cap
    ----------------|-------------------|-----
    missing_value    | 0.5               | 15
    duplicate        | 2.0               | 10
    invalid_value    | 2.0               | 20
    date_issue       | 3.0               | 10
    outlier          | 1.0               | 10
    location_mismatch| 2.0               | 10

Caps exist so that one systemic problem (e.g. one bad import) can't single-
handedly crater the score to 0 — each category can drag the score down by
at most its cap, keeping the number meaningful and comparable over time.

Rules implemented (per spec):
    - missing values (properties missing city/state/area_sqft)
    - duplicate property IDs (structurally prevented by the primary key in the
      live table; always 0 here — real duplicate-ID detection happens on raw,
      not-yet-validated CSV rows during import, see Phase 6)
    - duplicate tenant records (same tenant_name appearing more than once)
    - invalid occupancy values (< 0 or > 100)
    - negative rent
    - negative property value / negative revenue
    - invalid date ranges (lease_end before lease_start)
    - outlier revenue (IQR method on property annual_revenue)
    - inconsistent city/state pairing (against a known-good lookup)

This module is re-run on every GET /api/data-quality call: it clears and
re-derives all DataQualityIssue rows fresh each time, so the report always
reflects the current state of the database.
"""
from sqlalchemy.orm import Session
from app import models

WEIGHTS = {
    "missing_value": {"per_issue": 0.5, "cap": 15},
    "duplicate": {"per_issue": 2.0, "cap": 10},
    "invalid_value": {"per_issue": 2.0, "cap": 20},
    "date_issue": {"per_issue": 3.0, "cap": 10},
    "outlier": {"per_issue": 1.0, "cap": 10},
    "location_mismatch": {"per_issue": 2.0, "cap": 10},
}

# Known-good city -> state pairings (matches the set used by the seed generator)
KNOWN_CITY_STATE = {
    "Hyderabad": "Telangana",
    "Bengaluru": "Karnataka",
    "Chennai": "Tamil Nadu",
    "Pune": "Maharashtra",
    "Mumbai": "Maharashtra",
    "Delhi": "Delhi",
    "Gurugram": "Haryana",
    "Noida": "Uttar Pradesh",
}


# ---------------------------------------------------------------------------
# Shared, pure validation predicates. These are the single source of truth
# for "what counts as invalid" — both the DB-wide scan below AND the CSV
# import validator (app/services/csv_import.py) call these same functions,
# so the two never define the same rule two different ways.
# ---------------------------------------------------------------------------

def is_invalid_occupancy(value) -> bool:
    return value is not None and (value < 0 or value > 100)


def is_negative(value) -> bool:
    return value is not None and value < 0


def is_invalid_date_range(start, end) -> bool:
    return bool(start and end and end < start)


def is_location_mismatched(city, state) -> bool:
    return bool(city and state and city in KNOWN_CITY_STATE and KNOWN_CITY_STATE[city] != state)


def _add(issues: list, issue_type: str, entity_type: str, entity_id, field, description, severity):
    issues.append(models.DataQualityIssue(
        issue_type=issue_type, entity_type=entity_type, entity_id=entity_id,
        field=field, description=description, severity=severity,
    ))


def _detect_missing_values(properties, issues):
    count = 0
    for p in properties:
        for field in ("city", "state", "area_sqft"):
            if getattr(p, field) is None:
                _add(issues, "missing_value", "property", p.id, field,
                     f"Property {p.id} is missing '{field}'", "medium")
                count += 1
    return count


def _detect_duplicate_property_ids(properties, issues):
    # Enforced by the DB primary key in this application — always 0.
    # Left here so the rule is explicit and documented rather than silently absent.
    return 0


def _detect_duplicate_tenants(tenants, issues):
    seen = {}
    for t in tenants:
        seen.setdefault(t.tenant_name, []).append(t)
    count = 0
    for name, group in seen.items():
        if len(group) > 1:
            for t in group[1:]:  # first occurrence is the "original", rest flagged
                _add(issues, "duplicate", "tenant", t.id, "tenant_name",
                     f"Tenant '{name}' duplicated (ID {t.id} duplicates {group[0].id})", "low")
                count += 1
    return count


def _detect_invalid_occupancy(properties, issues):
    count = 0
    for p in properties:
        if is_invalid_occupancy(p.occupancy_pct):
            _add(issues, "invalid_value", "property", p.id, "occupancy_pct",
                 f"Property {p.id} has an out-of-range occupancy value ({p.occupancy_pct}%)", "high")
            count += 1
    return count


def _detect_negative_financials(properties, leases, issues):
    count = 0
    for p in properties:
        if is_negative(p.annual_revenue):
            _add(issues, "invalid_value", "property", p.id, "annual_revenue",
                 f"Property {p.id} has negative annual_revenue ({p.annual_revenue})", "high")
            count += 1
        if is_negative(p.property_value):
            _add(issues, "invalid_value", "property", p.id, "property_value",
                 f"Property {p.id} has negative property_value ({p.property_value})", "high")
            count += 1
    for l in leases:
        if is_negative(l.annual_rent):
            _add(issues, "invalid_value", "lease", l.id, "annual_rent",
                 f"Lease {l.id} has negative annual_rent ({l.annual_rent})", "high")
            count += 1
    return count


def _detect_invalid_date_ranges(leases, issues):
    count = 0
    for l in leases:
        if is_invalid_date_range(l.lease_start, l.lease_end):
            _add(issues, "date_issue", "lease", l.id, "lease_end",
                 f"Lease {l.id} ends ({l.lease_end}) before it starts ({l.lease_start})", "high")
            count += 1
    return count


def _detect_revenue_outliers(properties, issues):
    """IQR method on property annual_revenue (using absolute value so a
    negative-revenue record, already flagged separately, isn't double-scored)."""
    values = sorted(abs(p.annual_revenue) for p in properties if p.annual_revenue is not None)
    if len(values) < 4:
        return 0

    def percentile(data, pct):
        k = (len(data) - 1) * pct
        f, c = int(k), min(int(k) + 1, len(data) - 1)
        return data[f] + (data[c] - data[f]) * (k - f)

    q1, q3 = percentile(values, 0.25), percentile(values, 0.75)
    iqr = q3 - q1
    upper_bound = q3 + 1.5 * iqr
    lower_bound = q1 - 1.5 * iqr

    count = 0
    for p in properties:
        if p.annual_revenue is None:
            continue
        v = abs(p.annual_revenue)
        if v > upper_bound or v < lower_bound:
            _add(issues, "outlier", "property", p.id, "annual_revenue",
                 f"Property {p.id} annual_revenue ({p.annual_revenue}) is a statistical outlier "
                 f"(expected roughly {lower_bound:,.0f}–{upper_bound:,.0f})", "medium")
            count += 1
    return count


def _detect_location_mismatch(properties, issues):
    count = 0
    for p in properties:
        if is_location_mismatched(p.city, p.state):
            _add(issues, "location_mismatch", "property", p.id, "state",
                 f"Property {p.id}: city '{p.city}' is usually in "
                 f"'{KNOWN_CITY_STATE[p.city]}', but state is set to '{p.state}'", "low")
            count += 1
    return count


def run_data_quality_scan(db: Session) -> dict:
    """Clears previous findings, re-runs every rule, persists results, and
    returns the summary the API needs."""
    db.query(models.DataQualityIssue).delete()

    properties = db.query(models.Property).all()
    tenants = db.query(models.Tenant).all()
    leases = db.query(models.Lease).all()

    issues: list[models.DataQualityIssue] = []

    counts = {
        "missing_value": _detect_missing_values(properties, issues),
        "duplicate_property_id": _detect_duplicate_property_ids(properties, issues),
        "duplicate_tenant": _detect_duplicate_tenants(tenants, issues),
        "invalid_occupancy": _detect_invalid_occupancy(properties, issues),
        "negative_financials": _detect_negative_financials(properties, leases, issues),
        "date_issue": _detect_invalid_date_ranges(leases, issues),
        "outlier": _detect_revenue_outliers(properties, issues),
        "location_mismatch": _detect_location_mismatch(properties, issues),
    }

    for issue in issues:
        db.add(issue)
    db.commit()

    # Roll the granular counts up into the categories the scoring weights use
    category_counts = {
        "missing_value": counts["missing_value"],
        "duplicate": counts["duplicate_property_id"] + counts["duplicate_tenant"],
        "invalid_value": counts["invalid_occupancy"] + counts["negative_financials"],
        "date_issue": counts["date_issue"],
        "outlier": counts["outlier"],
        "location_mismatch": counts["location_mismatch"],
    }

    total_deduction = 0.0
    for category, count in category_counts.items():
        w = WEIGHTS[category]
        total_deduction += min(w["cap"], count * w["per_issue"])

    score = round(max(0.0, 100.0 - total_deduction), 1)

    return {
        "overall_score": score,
        "total_issues": len(issues),
        "missing_values": counts["missing_value"],
        "duplicates": counts["duplicate_property_id"] + counts["duplicate_tenant"],
        "invalid_values": counts["invalid_occupancy"] + counts["negative_financials"],
        "date_issues": counts["date_issue"],
        "outliers": counts["outlier"],
        "location_mismatches": counts["location_mismatch"],
        "breakdown": counts,
    }
