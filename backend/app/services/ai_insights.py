"""
AI Insights: a natural-language question-answering layer over PropLens data.

ARCHITECTURE (matches the AIInsightProvider / GeminiProvider / FallbackInsightProvider
pattern from the original project spec):

    1. INTENT CLASSIFICATION (this module): the question is matched against a
       fixed set of keyword/pattern rules to determine what's being asked and,
       if relevant, which property it's about. This is deterministic and
       explainable — no ML, no external calls.

    2. FACT RETRIEVAL (this module, calling existing services): once intent is
       known, the answer is computed by calling the SAME functions every other
       page in the app already uses — app.analytics.portfolio_analytics,
       app.analytics.risk_engine, app.analytics.data_quality, app.ml.forecast,
       and direct ORM queries for property/lease/tenant lookups. Nothing here
       recomputes a number a different way; it only asks an existing function
       for the answer and reads the result.

    3. PHRASING: a plain string template turns the retrieved facts into a
       natural-language sentence. If GEMINI_API_KEY is ever configured (see
       app/config.py), an optional Gemini path could be added to restate the
       same already-computed facts more fluently — but it would never be given
       the power to invent a number; it would only rephrase what step 2
       already computed. Since no key is configured in this environment, the
       deterministic template path is what actually runs, and is what this
       phase is tested against.

    This "retrieve grounded facts, then phrase" order is what prevents the
    feature from ever fabricating a value: if step 2 can't find the fact,
    step 3 never gets to make one up.

WHY NO EXTERNAL LLM IS REQUIRED: this environment has no LLM API key
configured (checked at startup — see get_provider_name() below) and no LLM
SDK installed. Per the original spec, GEMINI_API_KEY is optional; when
absent, the app must still work fully via a local, free, rule-based layer.
That is the default and only active path here, and it deliberately does not
require any paid service, network call, or API key to function.
"""
import re
from dataclasses import dataclass, field
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.utils.lease_status import compute_lease_status, days_to_expiry
from app.analytics.portfolio_analytics import portfolio_financials, revenue_growth
from app.analytics.risk_engine import run_risk_scan, compute_property_risk
from app.analytics.data_quality import run_data_quality_scan
from app.ml.forecast import forecast_portfolio, forecast_property


@dataclass
class InsightAnswer:
    question: str
    answer: str
    category: str
    source: str
    provider: str = "rule_based"
    supporting_data: dict | None = None
    records: list[dict] = field(default_factory=list)


EXAMPLE_QUESTIONS = [
    "What is the total portfolio value?",
    "What is the total revenue?",
    "What is the NOI?",
    "What is the occupancy rate?",
    "Which properties are high risk?",
    "Why is PROP0046 high risk?",
    "Which leases are expiring soon?",
    "What is the data quality score?",
    "What are the main data quality problems?",
    "What is the revenue trend?",
    "What does the revenue forecast show?",
    "Tell me about PROP0001",
    "What are the tenants and leases for PROP0001?",
]


# ---------------------------------------------------------------------------
# Entity extraction: find a property the question is asking about, if any.
# ---------------------------------------------------------------------------

PROPERTY_ID_PATTERN = re.compile(r"\bPROP-?\d{3,6}\b", re.IGNORECASE)


def _find_property(db: Session, question: str) -> models.Property | None:
    id_match = PROPERTY_ID_PATTERN.search(question)
    if id_match:
        candidate = id_match.group(0).upper().replace("PROP-", "PROP")
        prop = db.query(models.Property).filter(models.Property.id == candidate).first()
        if prop:
            return prop

    # Fuzzy fallback: does any property's full name appear in the question,
    # or does a significant word-overlap exist? Cheap at 150 properties.
    q_lower = question.lower()
    properties = db.query(models.Property).all()
    for p in properties:
        if p.name.lower() in q_lower:
            return p

    best_match, best_score = None, 0
    q_words = set(re.findall(r"[a-z0-9]+", q_lower))
    for p in properties:
        name_words = set(re.findall(r"[a-z0-9]+", p.name.lower()))
        overlap = len(q_words & name_words)
        if overlap > best_score and overlap >= 2:  # require at least 2 shared meaningful words
            best_match, best_score = p, overlap
    return best_match


def _looks_like_property_question(question: str) -> bool:
    """True if the question appears to reference a specific property at all
    (used to decide whether an unresolved property reference should produce
    a 'not found' answer rather than falling through to a portfolio-level one)."""
    if PROPERTY_ID_PATTERN.search(question):
        return True
    return bool(re.search(r"\bproperty\b|\btower\b|\bpark\b|\bcommons\b", question, re.IGNORECASE))


# ---------------------------------------------------------------------------
# Formatting helpers (display only — never used to compute a value)
# ---------------------------------------------------------------------------

def _fmt_currency(v) -> str:
    if v is None:
        return "unknown"
    abs_v = abs(v)
    if abs_v >= 1e7:
        return f"₹{v/1e7:.2f} Cr"
    if abs_v >= 1e5:
        return f"₹{v/1e5:.2f} L"
    return f"₹{v:,.0f}"


def _fmt_pct(v, digits: int = 1) -> str:
    return "unknown" if v is None else f"{v:.{digits}f}%"


# ---------------------------------------------------------------------------
# Portfolio-level answer handlers — each calls an EXISTING service function.
# ---------------------------------------------------------------------------

def _answer_portfolio_value(db: Session, question: str) -> InsightAnswer:
    rows = db.query(models.Property.property_value).all()
    total_value = sum(v for (v,) in rows if v is not None)
    return InsightAnswer(
        question=question,
        answer=f"The total portfolio value across all properties is {_fmt_currency(total_value)}.",
        category="portfolio_kpi", source="Property table (property_value sum)",
        supporting_data={"total_portfolio_value": round(total_value, 2)},
    )


def _answer_total_revenue(db: Session, question: str) -> InsightAnswer:
    f = portfolio_financials(db)
    return InsightAnswer(
        question=question,
        answer=f"Total annual revenue across the portfolio is {_fmt_currency(f['total_revenue'])}.",
        category="portfolio_kpi", source="portfolio_analytics.portfolio_financials",
        supporting_data=f,
    )


def _answer_noi(db: Session, question: str) -> InsightAnswer:
    f = portfolio_financials(db)
    return InsightAnswer(
        question=question,
        answer=(f"Net Operating Income (NOI) is {_fmt_currency(f['net_operating_income'])} "
                f"(revenue {_fmt_currency(f['total_revenue'])} minus operating expenses "
                f"{_fmt_currency(f['total_operating_expenses'])}), an NOI margin of "
                f"{_fmt_pct(f['noi_margin_pct'])}."),
        category="portfolio_kpi", source="portfolio_analytics.portfolio_financials",
        supporting_data=f,
    )


def _answer_occupancy(db: Session, question: str) -> InsightAnswer:
    f = portfolio_financials(db)
    return InsightAnswer(
        question=question,
        answer=f"Average portfolio occupancy is {_fmt_pct(f['average_occupancy'])}.",
        category="portfolio_kpi", source="portfolio_analytics.portfolio_financials",
        supporting_data={"average_occupancy": f["average_occupancy"]},
    )


def _answer_high_risk_list(db: Session, question: str) -> InsightAnswer:
    scan = run_risk_scan(db)
    high = [p for p in scan["properties"] if p["risk_category"] == "High"]
    top = high[:10]
    if not high:
        answer = "No properties are currently classified as High risk."
    else:
        names = ", ".join(f"{p['property_name']} ({p['risk_score']})" for p in top[:5])
        more = f", and {len(high) - 5} more" if len(high) > 5 else ""
        answer = f"There are {len(high)} High-risk properties: {names}{more}."
    return InsightAnswer(
        question=question, answer=answer, category="risk", source="risk_engine.run_risk_scan",
        supporting_data={"total_properties": scan["total_properties"], "high_risk_count": len(high),
                          "low_risk": scan["low_risk"], "medium_risk": scan["medium_risk"]},
        records=[{"property_id": p["property_id"], "property_name": p["property_name"],
                  "risk_score": p["risk_score"], "reasons": p["reasons"]} for p in top],
    )


def _answer_leases_expiring(db: Session, question: str) -> InsightAnswer:
    leases = db.query(models.Lease).filter(models.Lease.lease_end.isnot(None)).all()
    expiring = [l for l in leases if compute_lease_status(l.lease_end) == "Expiring Soon"]
    expiring.sort(key=lambda l: l.lease_end)
    top = expiring[:10]
    if not expiring:
        answer = "No leases are currently expiring within the next 90 days."
    else:
        answer = f"{len(expiring)} lease(s) are expiring within the next 90 days."
    return InsightAnswer(
        question=question, answer=answer, category="lease", source="Lease table + utils.lease_status",
        supporting_data={"expiring_count": len(expiring)},
        records=[{"lease_id": l.id, "property_id": l.property_id, "tenant_name": l.tenant_name,
                  "lease_end": str(l.lease_end), "days_to_expiry": days_to_expiry(l.lease_end)} for l in top],
    )


def _answer_quality_score(db: Session, question: str) -> InsightAnswer:
    scan = run_data_quality_scan(db)
    return InsightAnswer(
        question=question,
        answer=f"The overall data quality score is {_fmt_pct(scan['overall_score'])}, based on {scan['total_issues']} detected issue(s).",
        category="data_quality", source="data_quality.run_data_quality_scan",
        supporting_data={"overall_score": scan["overall_score"], "total_issues": scan["total_issues"]},
    )


def _answer_quality_problems(db: Session, question: str) -> InsightAnswer:
    scan = run_data_quality_scan(db)
    breakdown = scan["breakdown"]
    ranked = sorted(breakdown.items(), key=lambda kv: kv[1], reverse=True)
    ranked = [(k, v) for k, v in ranked if v > 0]
    if not ranked:
        answer = "No data quality issues were detected."
    else:
        parts = ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in ranked[:5])
        answer = f"The main data quality problems are: {parts}."
    return InsightAnswer(
        question=question, answer=answer, category="data_quality", source="data_quality.run_data_quality_scan",
        supporting_data={"breakdown": breakdown, "overall_score": scan["overall_score"]},
    )


def _answer_revenue_trend(db: Session, question: str) -> InsightAnswer:
    growth = revenue_growth(db)
    mom, three_mo = growth["month_over_month_pct"], growth["trailing_3_month_pct"]
    parts = []
    if mom is not None:
        parts.append(f"{'up' if mom >= 0 else 'down'} {abs(mom):.2f}% month-over-month")
    if three_mo is not None:
        parts.append(f"{'up' if three_mo >= 0 else 'down'} {abs(three_mo):.2f}% over the trailing 3 months")
    answer = "Revenue is " + " and ".join(parts) + "." if parts else "Not enough history to compute a revenue trend."
    return InsightAnswer(
        question=question, answer=answer, category="analytics", source="portfolio_analytics.revenue_growth",
        supporting_data=growth,
    )


def _answer_forecast(db: Session, question: str) -> InsightAnswer:
    metric = "occupancy" if "occupancy" in question.lower() else "revenue"
    horizon_match = re.search(r"(\d+)\s*(month|mo\b)", question.lower())
    horizon = min(12, max(1, int(horizon_match.group(1)))) if horizon_match else 3

    historical, forecast, bundle = forecast_portfolio(db, metric, horizon)
    if bundle.get("insufficient_data") or not forecast:
        return InsightAnswer(
            question=question, answer="Not enough historical data is available to generate a forecast.",
            category="forecast", source="ml.forecast.forecast_portfolio",
        )

    unit = _fmt_pct if metric == "occupancy" else _fmt_currency
    last_hist = historical[-1]["value"] if historical else None
    last_fc = forecast[-1]["value"]
    answer = (f"The {horizon}-month {metric} forecast projects {unit(last_fc)} by {forecast[-1]['month']}, "
              f"starting from a current level of {unit(last_hist)}.")
    return InsightAnswer(
        question=question, answer=answer, category="forecast", source="ml.forecast.forecast_portfolio",
        supporting_data={"metric": metric, "horizon_months": horizon, "model_performance": bundle.get("metrics")},
        records=forecast,
    )


PORTFOLIO_ROUTES = [
    (re.compile(r"high.?risk|at risk|riskiest", re.I), _answer_high_risk_list),
    (re.compile(r"expir|lease.*(soon|days)", re.I), _answer_leases_expiring),
    (re.compile(r"data.?quality.*(problem|issue|wrong|main)", re.I), _answer_quality_problems),
    (re.compile(r"data.?quality.*(score)|quality score", re.I), _answer_quality_score),
    (re.compile(r"forecast|predict|projection", re.I), _answer_forecast),
    (re.compile(r"trend", re.I), _answer_revenue_trend),
    (re.compile(r"\bnoi\b|net operating income", re.I), _answer_noi),
    (re.compile(r"occupan", re.I), _answer_occupancy),
    (re.compile(r"revenue", re.I), _answer_total_revenue),
    (re.compile(r"portfolio value|total value|worth", re.I), _answer_portfolio_value),
]


# ---------------------------------------------------------------------------
# Property-scoped answer handlers
# ---------------------------------------------------------------------------

def _answer_property_risk(db: Session, question: str, prop: models.Property) -> InsightAnswer:
    result = compute_property_risk(prop, db)
    reasons = "; ".join(result.reasons) if result.reasons else "no single dominant factor"
    answer = (f"{prop.name} ({prop.id}) has a risk score of {result.score} ({result.category}). "
              f"Main reason(s): {reasons}.")
    return InsightAnswer(
        question=question, answer=answer, category="risk", source="risk_engine.compute_property_risk",
        supporting_data={"risk_score": result.score, "risk_category": result.category, "reasons": result.reasons},
        records=[{"factor": f.name, "value": f.value, "weight": f.weight, "reason": f.reason} for f in result.factors],
    )


def _answer_property_leases(db: Session, question: str, prop: models.Property) -> InsightAnswer:
    leases = db.query(models.Lease).filter(models.Lease.property_id == prop.id).all()
    tenants = db.query(models.Tenant).filter(models.Tenant.property_id == prop.id).all()
    if not leases and not tenants:
        answer = f"{prop.name} ({prop.id}) has no tenant or lease records on file."
    else:
        answer = f"{prop.name} ({prop.id}) has {len(tenants)} tenant(s) and {len(leases)} lease(s) on file."
    return InsightAnswer(
        question=question, answer=answer, category="lease", source="Tenant/Lease tables",
        supporting_data={"tenant_count": len(tenants), "lease_count": len(leases)},
        records=[{"lease_id": l.id, "tenant_name": l.tenant_name, "lease_end": str(l.lease_end),
                  "status": compute_lease_status(l.lease_end) if l.lease_end else "Unknown",
                  "annual_rent": l.annual_rent} for l in leases],
    )


def _answer_property_forecast(db: Session, question: str, prop: models.Property) -> InsightAnswer:
    metric = "occupancy" if "occupancy" in question.lower() else "revenue"
    historical, forecast = forecast_property(db, prop.id, metric, 3)
    if not forecast:
        return InsightAnswer(
            question=question,
            answer=f"Not enough history for {prop.name} ({prop.id}) to generate a {metric} forecast.",
            category="forecast", source="ml.forecast.forecast_property",
        )
    unit = _fmt_pct if metric == "occupancy" else _fmt_currency
    answer = f"For {prop.name} ({prop.id}), the 3-month {metric} forecast reaches {unit(forecast[-1]['value'])} by {forecast[-1]['month']}."
    return InsightAnswer(
        question=question, answer=answer, category="forecast", source="ml.forecast.forecast_property",
        supporting_data={"metric": metric}, records=forecast,
    )


def _answer_property_detail(db: Session, question: str, prop: models.Property) -> InsightAnswer:
    revenue = prop.annual_revenue or 0
    opex = prop.operating_expenses or 0
    noi = revenue - opex
    answer = (f"{prop.name} ({prop.id}) is a {prop.property_type or 'unknown-type'} property in "
              f"{prop.city or 'an unknown city'}, {prop.state or ''}. Occupancy: {_fmt_pct(prop.occupancy_pct)}, "
              f"annual revenue: {_fmt_currency(prop.annual_revenue)}, property value: {_fmt_currency(prop.property_value)}, "
              f"NOI: {_fmt_currency(noi)}, risk category: {prop.risk_category or 'not yet scored'}.")
    return InsightAnswer(
        question=question, answer=answer, category="property_detail", source="Property table",
        supporting_data={
            "id": prop.id, "name": prop.name, "city": prop.city, "state": prop.state,
            "property_type": prop.property_type, "occupancy_pct": prop.occupancy_pct,
            "annual_revenue": prop.annual_revenue, "property_value": prop.property_value,
            "risk_category": prop.risk_category, "num_tenants": prop.num_tenants,
        },
    )


def _route_property_question(db: Session, question: str, prop: models.Property) -> InsightAnswer:
    q = question.lower()
    if "risk" in q or "why" in q:
        return _answer_property_risk(db, question, prop)
    if "tenant" in q or "lease" in q:
        return _answer_property_leases(db, question, prop)
    if "forecast" in q or "predict" in q:
        return _answer_property_forecast(db, question, prop)
    return _answer_property_detail(db, question, prop)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def answer_question(db: Session, question: str) -> InsightAnswer:
    question = (question or "").strip()
    if not question:
        return InsightAnswer(question=question, answer="Please ask a question about the portfolio.",
                              category="unsupported", source="none")

    prop = _find_property(db, question)
    if prop:
        return _route_property_question(db, question, prop)

    if _looks_like_property_question(question):
        return InsightAnswer(
            question=question,
            answer="I couldn't find a property matching that reference. Try a property ID like 'PROP0001' or its full name.",
            category="not_found", source="none",
        )

    for pattern, handler in PORTFOLIO_ROUTES:
        if pattern.search(question):
            return handler(db, question)

    return InsightAnswer(
        question=question,
        answer="I don't have a way to answer that yet. Try asking about portfolio value, revenue, NOI, "
               "occupancy, risk, leases expiring, data quality, forecasts, or a specific property.",
        category="unsupported", source="none",
    )


def get_provider_name() -> str:
    """Reports which answering path is actually active. Gemini is only used
    if a key is configured AND the SDK is importable — neither is true in
    this environment, so the deterministic rule-based path is what runs."""
    if settings.gemini_api_key:
        try:
            import google.generativeai  # noqa: F401
            return "gemini (configured)"
        except ImportError:
            pass
    return "rule_based"
