"""
Turns a trained model into an actual multi-month forecast.

APPROACH: iterative one-step-ahead forecasting. The model predicts one month
at a time from a lag feature; to project further out, each prediction becomes
the lag input for the next step. This is a standard, easily-explained
technique for lag-based regression forecasting — not a sequence model, just
"predict next month, then treat that prediction as if it were observed, and
predict the month after that."

LIMITATION, stated plainly: errors can compound over the horizon (a bad
month-2 prediction feeds into month 3, etc.), and operating_expense is held
constant at its last known value for the whole horizon since forecasting
expenses is out of scope here. This is a demonstration pipeline, not a
production forecasting system — see the disclaimer returned with every
forecast response.
"""
from datetime import date
from dateutil.relativedelta import relativedelta
import pandas as pd
from sqlalchemy.orm import Session
from app import models
from app.ml.features import encode, FEATURE_COLUMNS
from app.ml.train import load_or_train

TARGET_COLUMN_MAP = {"revenue": "revenue", "occupancy": "occupancy_pct"}


def _next_month(d: date) -> date:
    return (d.replace(day=1) + relativedelta(months=1))


def _last_known_state(db: Session, property_id: str, target_col: str):
    """Most recent metric row for this property with a usable value (forward
    filling through any trailing nulls), plus the property's static attrs."""
    prop = db.query(models.Property).filter(models.Property.id == property_id).first()
    if not prop:
        return None

    metrics = (
        db.query(models.PropertyMetric)
        .filter(models.PropertyMetric.property_id == property_id)
        .order_by(models.PropertyMetric.month)
        .all()
    )
    if not metrics:
        return None

    last_value = None
    last_opex = None
    last_month = None
    for m in metrics:
        val = getattr(m, target_col)
        if val is not None:
            last_value = val
        if m.operating_expense is not None:
            last_opex = m.operating_expense
        last_month = m.month

    if last_value is None:
        return None  # this property has never had a usable reading for this metric

    return {
        "last_month": last_month,
        "last_value": last_value,
        "last_opex": last_opex or 0.0,
        "property_type": prop.property_type,
        "city": prop.city,
    }


def forecast_property(db: Session, property_id: str, metric: str, horizon_months: int):
    """Returns (historical_points, forecast_points) for one property, or
    (None, None) if the property doesn't exist, and ([], []) if it exists
    but has no usable history for this metric."""
    target_col = TARGET_COLUMN_MAP[metric]
    prop = db.query(models.Property).filter(models.Property.id == property_id).first()
    if not prop:
        return None, None

    metrics = (
        db.query(models.PropertyMetric)
        .filter(models.PropertyMetric.property_id == property_id)
        .order_by(models.PropertyMetric.month)
        .all()
    )
    historical = [
        {"month": str(m.month), "value": getattr(m, target_col)}
        for m in metrics if getattr(m, target_col) is not None
    ]

    state = _last_known_state(db, property_id, target_col)
    if state is None:
        return historical, []

    bundle = load_or_train(db, target_col)
    if bundle["insufficient_data"] or bundle["model"] is None:
        return historical, []

    model, encoders = bundle["model"], bundle["encoders"]

    lag_value = state["last_value"]
    cursor_month = state["last_month"]
    forecast_points = []

    for _ in range(horizon_months):
        cursor_month = _next_month(cursor_month)
        features = pd.DataFrame([[
            lag_value,
            cursor_month.month,
            encode(state["property_type"], encoders["property_type"]),
            encode(state["city"], encoders["city"]),
            state["last_opex"],
        ]], columns=FEATURE_COLUMNS)
        prediction = float(model.predict(features)[0])
        if metric == "occupancy":
            prediction = max(0.0, min(100.0, prediction))  # occupancy can't leave [0,100]
        forecast_points.append({"month": str(cursor_month), "value": round(prediction, 2)})
        lag_value = prediction  # feed the prediction forward as next step's lag

    return historical, forecast_points


def _bulk_last_known_states(db: Session, target_col: str) -> dict:
    """Bulk-fetch every property's last known state in two queries instead of
    the N+1 pattern _last_known_state would cause if called per-property —
    this is what makes portfolio-wide forecasting fast enough for an API call."""
    properties = db.query(models.Property).all()
    prop_by_id = {p.id: p for p in properties}

    all_metrics = db.query(models.PropertyMetric).order_by(
        models.PropertyMetric.property_id, models.PropertyMetric.month
    ).all()

    states = {}
    for m in all_metrics:
        pid = m.property_id
        if pid not in prop_by_id:
            continue
        val = getattr(m, target_col)
        entry = states.setdefault(pid, {"last_value": None, "last_opex": None, "last_month": None})
        if val is not None:
            entry["last_value"] = val
        if m.operating_expense is not None:
            entry["last_opex"] = m.operating_expense
        entry["last_month"] = m.month

    result = {}
    for pid, entry in states.items():
        if entry["last_value"] is None:
            continue
        prop = prop_by_id[pid]
        result[pid] = {
            "last_month": entry["last_month"],
            "last_value": entry["last_value"],
            "last_opex": entry["last_opex"] or 0.0,
            "property_type": prop.property_type,
            "city": prop.city,
        }
    return result


def forecast_portfolio(db: Session, metric: str, horizon_months: int):
    """Aggregates every property's individual forecast: summed for revenue,
    averaged for occupancy. Historical side reuses the same monthly
    aggregation the Dashboard/Analytics pages already use, so the numbers
    agree everywhere.

    Predicts one horizon step at a time, but batches ALL properties into a
    single model.predict() call per step (instead of one call per property
    per step) — this is what keeps a 150-property, multi-month forecast to
    a handful of model calls instead of hundreds."""
    from app.analytics.portfolio_analytics import monthly_revenue_trend, monthly_occupancy_trend

    target_col = TARGET_COLUMN_MAP[metric]
    historical = monthly_revenue_trend(db) if metric == "revenue" else monthly_occupancy_trend(db)
    historical = [
        {"month": p["month"], "value": p["revenue" if metric == "revenue" else "avg_occupancy"]}
        for p in historical
    ]

    bundle = load_or_train(db, target_col)
    if bundle["insufficient_data"] or bundle["model"] is None:
        return historical, [], bundle

    model, encoders = bundle["model"], bundle["encoders"]
    states = _bulk_last_known_states(db, target_col)
    if not states:
        return historical, [], bundle

    property_ids = list(states.keys())
    lag_values = {pid: states[pid]["last_value"] for pid in property_ids}
    cursor_months = {pid: states[pid]["last_month"] for pid in property_ids}

    per_month_values = {}  # month_str -> list of per-property predicted values

    for _ in range(horizon_months):
        rows = []
        for pid in property_ids:
            cursor_months[pid] = _next_month(cursor_months[pid])
            rows.append([
                lag_values[pid],
                cursor_months[pid].month,
                encode(states[pid]["property_type"], encoders["property_type"]),
                encode(states[pid]["city"], encoders["city"]),
                states[pid]["last_opex"],
            ])

        batch = pd.DataFrame(rows, columns=FEATURE_COLUMNS)
        predictions = model.predict(batch)

        for pid, prediction in zip(property_ids, predictions):
            prediction = float(prediction)
            if metric == "occupancy":
                prediction = max(0.0, min(100.0, prediction))
            lag_values[pid] = prediction
            month_str = str(cursor_months[pid])
            per_month_values.setdefault(month_str, []).append(prediction)

    forecast = []
    for month_str in sorted(per_month_values.keys()):
        values = per_month_values[month_str]
        agg = sum(values) if metric == "revenue" else sum(values) / len(values)
        forecast.append({"month": month_str, "value": round(agg, 2)})

    return historical, forecast, bundle
