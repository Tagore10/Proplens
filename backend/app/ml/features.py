"""
Feature engineering for revenue/occupancy forecasting.

Turns the raw property_metrics history into a supervised-learning table:
one row per (property, month), predicting that month's value from what was
known going into it — the prior month's value (lag), the calendar month
(captures the seasonal bump the seed data injects in Nov/Dec), and the
property's static attributes (type, city, current opex).

This is deliberately simple and explainable: no black-box feature store,
just five interpretable columns any interviewer can be walked through.
"""
import pandas as pd
from sqlalchemy.orm import Session
from app import models

FEATURE_COLUMNS = ["lag_value", "month_of_year", "property_type_code", "city_code", "operating_expense"]


def load_metrics_dataframe(db: Session, target_col: str) -> pd.DataFrame:
    """One row per (property, month) with the target, plus the property's
    static attributes joined in. target_col is 'revenue' or 'occupancy_pct'."""
    rows = (
        db.query(
            models.PropertyMetric.property_id,
            models.PropertyMetric.month,
            models.PropertyMetric.revenue,
            models.PropertyMetric.occupancy_pct,
            models.PropertyMetric.operating_expense,
            models.Property.property_type,
            models.Property.city,
        )
        .join(models.Property, models.Property.id == models.PropertyMetric.property_id)
        .all()
    )
    df = pd.DataFrame(rows, columns=["property_id", "month", "revenue", "occupancy_pct",
                                      "operating_expense", "property_type", "city"])
    df["month"] = pd.to_datetime(df["month"])
    df = df.sort_values(["property_id", "month"]).reset_index(drop=True)
    return df


def build_encoders(df: pd.DataFrame) -> dict:
    """Fixed category -> integer code mappings, saved alongside the model so
    forecast-time encoding always matches what the model was trained on."""
    city_categories = sorted(c for c in df["city"].dropna().unique())
    type_categories = sorted(t for t in df["property_type"].dropna().unique())
    return {
        "city": {name: i for i, name in enumerate(city_categories)},
        "property_type": {name: i for i, name in enumerate(type_categories)},
    }


def encode(value, mapping: dict) -> int:
    """Unknown/missing categories fall back to a dedicated 'unseen' bucket
    (one past the last known code) rather than raising."""
    if value is None or value not in mapping:
        return len(mapping)
    return mapping[value]


def build_supervised_frame(db: Session, target_col: str):
    """Returns (frame, encoders) where frame has FEATURE_COLUMNS + 'target' +
    'month' + 'property_id', ready for time-aware train/test splitting.

    Rows are dropped when the target itself is missing (can't supervise on a
    missing label) or when there's no usable prior-month value yet (a
    property's first month has no lag, and mid-series gaps are forward-filled
    from that property's own history before being used as a lag)."""
    raw = load_metrics_dataframe(db, target_col)
    encoders = build_encoders(raw)

    # Forward-fill within each property so a null mid-series reading doesn't
    # break the lag feature for the following month — but the TARGET column
    # stays unfilled; we only ever train on a real, observed value.
    raw["filled_value"] = raw.groupby("property_id")[target_col].ffill()
    raw["lag_value"] = raw.groupby("property_id")["filled_value"].shift(1)
    raw["month_of_year"] = raw["month"].dt.month
    raw["operating_expense_filled"] = raw.groupby("property_id")["operating_expense"].ffill()
    raw["property_type_code"] = raw["property_type"].map(lambda v: encode(v, encoders["property_type"]))
    raw["city_code"] = raw["city"].map(lambda v: encode(v, encoders["city"]))

    frame = raw[["property_id", "month", target_col, "lag_value", "month_of_year",
                 "property_type_code", "city_code", "operating_expense_filled"]].copy()
    frame = frame.rename(columns={target_col: "target", "operating_expense_filled": "operating_expense"})

    frame = frame.dropna(subset=["target", "lag_value"])
    return frame, encoders
