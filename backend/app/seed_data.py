"""
Generates synthetic (fictional) commercial real-estate portfolio data.

Design goals:
- Realistic-looking patterns (not uniform random): some properties trend up,
  some decline, seasonal variation in monthly metrics, correlated occupancy/revenue.
- Deliberately injects known data-quality problems (missing values, duplicate IDs,
  invalid ranges, bad date order, outliers, inconsistent city/state) so the
  Data Quality engine has real things to detect. Injection counts are tracked
  so the "expected" issue counts can be documented/tested against.

Run directly: `python -m app.seed_data` (from backend/ with venv active)
"""
import random
from datetime import date, timedelta
from app.database import Base, engine, SessionLocal
from app.models import Property, Tenant, Lease, PropertyMetric

random.seed(42)

CITIES_STATES = [
    ("Hyderabad", "Telangana"),
    ("Bengaluru", "Karnataka"),
    ("Chennai", "Tamil Nadu"),
    ("Pune", "Maharashtra"),
    ("Mumbai", "Maharashtra"),
    ("Delhi", "Delhi"),
    ("Gurugram", "Haryana"),
    ("Noida", "Uttar Pradesh"),
]

PROPERTY_TYPES = ["Office", "Retail", "Industrial", "Logistics", "Mixed Use"]
INDUSTRIES = ["Technology", "Finance", "Retail", "Manufacturing", "Healthcare", "Logistics", "Media", "Consulting"]

NUM_PROPERTIES = 150
NUM_TENANTS = 220
NUM_LEASES = 300
MONTHS_HISTORY = 12


def money(base, spread_pct=0.15):
    return round(base * (1 + random.uniform(-spread_pct, spread_pct)), 2)


def make_properties():
    properties = []
    for i in range(1, NUM_PROPERTIES + 1):
        pid = f"PROP{i:04d}"
        city, state = random.choice(CITIES_STATES)
        ptype = random.choice(PROPERTY_TYPES)
        area = round(random.uniform(15000, 250000), 0)

        # Give each property a "performance archetype" so trends look real, not random
        archetype = random.choices(
            ["stable", "growing", "declining", "high_performer", "distressed"],
            weights=[40, 20, 15, 15, 10],
        )[0]

        base_occupancy = {
            "stable": random.uniform(75, 90),
            "growing": random.uniform(60, 78),
            "declining": random.uniform(70, 88),
            "high_performer": random.uniform(90, 99),
            "distressed": random.uniform(35, 60),
        }[archetype]

        annual_revenue = money(area * random.uniform(180, 420))
        operating_expenses = money(annual_revenue * random.uniform(0.25, 0.55))
        property_value = money(annual_revenue * random.uniform(8, 14))

        prop = {
            "id": pid,
            "name": f"{city} {ptype} Park {i}" if ptype != "Mixed Use" else f"{city} Commons {i}",
            "city": city,
            "state": state,
            "property_type": ptype,
            "area_sqft": area,
            "occupancy_pct": round(base_occupancy, 1),
            "annual_revenue": annual_revenue,
            "operating_expenses": operating_expenses,
            "property_value": property_value,
            "num_tenants": 0,  # filled in after tenants/leases assigned
            "_archetype": archetype,
        }
        properties.append(prop)
    return properties


def inject_property_issues(properties):
    """Mutates a subset of property dicts to introduce known data-quality problems."""
    n = len(properties)

    # Missing values: blank city/state or area for ~8 properties
    for p in random.sample(properties, 8):
        field = random.choice(["city", "state", "area_sqft"])
        p[field] = None

    # Invalid occupancy values (> 100 or negative) for 4 properties
    for p in random.sample(properties, 4):
        p["occupancy_pct"] = random.choice([round(random.uniform(101, 130), 1), round(random.uniform(-20, -1), 1)])

    # Negative property value / revenue for 3 properties
    for p in random.sample(properties, 3):
        field = random.choice(["property_value", "annual_revenue"])
        p[field] = -abs(p[field])

    # Inconsistent city/state pairing for 3 properties (city doesn't match its usual state)
    for p in random.sample(properties, 3):
        wrong_state = random.choice([s for c, s in CITIES_STATES if s != p["state"]])
        p["state"] = wrong_state

    # Outlier revenue (unrealistically high) for 4 properties
    for p in random.sample(properties, 4):
        p["annual_revenue"] = round(p["annual_revenue"] * random.uniform(6, 10), 2)

    # NOTE: a duplicate *property ID* cannot exist in the live table (it's the
    # primary key). Duplicate-ID detection is instead demonstrated via the
    # sample CSV import fixture in the CSV Import phase, where raw rows can
    # legitimately contain a repeated ID before validation runs.

    return properties


def make_tenants(properties):
    tenants = []
    adjectives = ['Aarav', 'Nova', 'Pinnacle', 'Bluewave', 'Orion', 'Summit', 'Vertex',
                  'Meridian', 'Sterling', 'Crestline', 'Ashoka', 'Zenith', 'Horizon',
                  'Lotus', 'Falcon', 'Northgate', 'Silverline', 'Redwood', 'Coral', 'Alpine']
    nouns = ['Technologies', 'Retail Group', 'Industries', 'Solutions', 'Holdings',
             'Partners', 'Enterprises', 'Systems', 'Logistics Co', 'Ventures', 'Labs']
    # 20 x 11 = 220 combinations, still not quite enough headroom for 223 tenants
    # on its own, so a numeric suffix is added to guarantee near-zero accidental
    # collisions — the ONLY duplicate tenant names should be the ones deliberately
    # injected below, which is what the Data Quality engine is meant to catch.
    for i in range(1, NUM_TENANTS + 1):
        tid = f"TEN{i:04d}"
        prop = random.choice(properties)
        tenants.append({
            "id": tid,
            "property_id": prop["id"],
            "tenant_name": f"{random.choice(adjectives)} {random.choice(nouns)} #{i:03d}",
            "industry": random.choice(INDUSTRIES),
        })

    # Duplicate tenant records: 3 exact-name duplicates under different tenant IDs
    for _ in range(3):
        src = random.choice(tenants)
        tenants.append({
            "id": f"TEN{len(tenants)+1:04d}",
            "property_id": src["property_id"],
            "tenant_name": src["tenant_name"],
            "industry": src["industry"],
        })

    return tenants


def make_leases(properties, tenants):
    leases = []
    today = date.today()
    for i in range(1, NUM_LEASES + 1):
        lid = f"LSE{i:04d}"
        tenant = random.choice(tenants)
        prop_id = tenant["property_id"]

        start_offset_days = random.randint(-1500, 200)  # some leases started years ago
        lease_start = today + timedelta(days=start_offset_days)
        term_days = random.choice([365, 730, 1095, 1825])  # 1-5 year terms
        lease_end = lease_start + timedelta(days=term_days)

        # Bias some leases to expire soon (within 90 days) for realistic risk signal.
        # Guarded so this never accidentally creates an end-before-start date for
        # a lease whose start is still in the future (start_offset_days can be up
        # to +200) — that would be an unintended data-quality bug, not a deliberate
        # "invalid date range" test case (those are injected explicitly below).
        if random.random() < 0.12:
            candidate = today + timedelta(days=random.randint(1, 90))
            if candidate > lease_start:
                lease_end = candidate
        if random.random() < 0.05:
            candidate = today - timedelta(days=random.randint(1, 200))  # already expired
            if candidate > lease_start:
                lease_end = candidate

        annual_rent = money(random.uniform(500000, 9000000))

        leases.append({
            "id": lid,
            "property_id": prop_id,
            "tenant_id": tenant["id"],
            "tenant_name": tenant["tenant_name"],
            "lease_start": lease_start,
            "lease_end": lease_end,
            "annual_rent": annual_rent,
            "renewal_status": random.choice(["Pending", "Renewed", "Not Renewing", "Under Negotiation"]),
        })

    # Invalid date range: lease_end before lease_start, for 2 leases
    for l in random.sample(leases, 2):
        l["lease_start"], l["lease_end"] = l["lease_end"], l["lease_start"]

    # Negative rent for 2 leases
    for l in random.sample(leases, 2):
        l["annual_rent"] = -abs(l["annual_rent"])

    return leases


def make_metrics(properties):
    metrics = []
    today = date.today()
    for prop in properties:
        base_rev = abs(prop["annual_revenue"]) / 12 if prop["annual_revenue"] else random.uniform(500000, 3000000)
        base_occ = prop["occupancy_pct"] if prop["occupancy_pct"] and 0 <= prop["occupancy_pct"] <= 100 else 75
        archetype = prop["_archetype"]

        trend_per_month = {
            "stable": 0.0,
            "growing": random.uniform(0.5, 1.5),
            "declining": -random.uniform(0.5, 1.8),
            "high_performer": random.uniform(0.1, 0.6),
            "distressed": -random.uniform(1.0, 2.5),
        }[archetype]

        for m in range(MONTHS_HISTORY, 0, -1):
            month_date = (today.replace(day=1) - timedelta(days=30 * m)).replace(day=1)
            seasonal = 1 + 0.05 * random.uniform(-1, 1) + (0.06 if month_date.month in (11, 12) else 0)
            occ = max(5, min(100, base_occ + trend_per_month * (MONTHS_HISTORY - m) + random.uniform(-3, 3)))
            revenue = round(base_rev * seasonal * (occ / max(base_occ, 1)), 2)
            opex = round(revenue * random.uniform(0.28, 0.5), 2)

            metrics.append({
                "property_id": prop["id"],
                "month": month_date,
                "revenue": revenue,
                "occupancy_pct": round(occ, 1),
                "operating_expense": opex,
            })

    # Outlier revenue spike in a handful of monthly records
    sample = random.sample(metrics, 5)
    for m in sample:
        m["revenue"] = round(m["revenue"] * random.uniform(5, 8), 2)

    # Missing values: null out revenue or occupancy in a few monthly records
    for m in random.sample(metrics, 6):
        field = random.choice(["revenue", "occupancy_pct"])
        m[field] = None

    return metrics


def seed():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    properties = make_properties()
    properties = inject_property_issues(properties)
    tenants = make_tenants(properties)
    leases = make_leases(properties, tenants)
    metrics = make_metrics(properties)

    # num_tenants per property, computed from actual tenant assignments
    counts = {}
    for t in tenants:
        counts[t["property_id"]] = counts.get(t["property_id"], 0) + 1
    for p in properties:
        p["num_tenants"] = counts.get(p["id"], 0)

    db = SessionLocal()
    try:
        for p in properties:
            db.add(Property(
                id=p["id"], name=p["name"], city=p["city"], state=p["state"],
                property_type=p["property_type"], area_sqft=p["area_sqft"],
                occupancy_pct=p["occupancy_pct"], annual_revenue=p["annual_revenue"],
                operating_expenses=p["operating_expenses"], property_value=p["property_value"],
                num_tenants=p["num_tenants"],
            ))
        db.flush()

        for t in tenants:
            db.add(Tenant(id=t["id"], property_id=t["property_id"], tenant_name=t["tenant_name"], industry=t["industry"]))
        db.flush()

        for l in leases:
            db.add(Lease(
                id=l["id"], property_id=l["property_id"], tenant_id=l["tenant_id"],
                tenant_name=l["tenant_name"], lease_start=l["lease_start"], lease_end=l["lease_end"],
                annual_rent=l["annual_rent"], renewal_status=l["renewal_status"],
            ))

        for m in metrics:
            db.add(PropertyMetric(
                property_id=m["property_id"], month=m["month"], revenue=m["revenue"],
                occupancy_pct=m["occupancy_pct"], operating_expense=m["operating_expense"],
            ))

        db.commit()
        print(f"Seeded {len(properties)} properties, {len(tenants)} tenants, "
              f"{len(leases)} leases, {len(metrics)} monthly metric rows.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
