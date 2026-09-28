from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app import models
from app.ml.forecast import forecast_property, forecast_portfolio
from app.schemas.forecast import ForecastResponse, ModelPerformance

router = APIRouter(prefix="/api/forecast", tags=["forecast"])


def _build_response(metric: str, property_id: Optional[str], property_name: Optional[str],
                     horizon_months: int, historical: list, forecast: list, bundle: dict) -> ForecastResponse:
    metrics = bundle.get("metrics")
    note = None
    if bundle.get("insufficient_data"):
        note = "Not enough historical data to train a forecasting model yet."
    elif not forecast:
        note = "This property has no usable history for this metric, so no forecast could be generated."
    elif metrics is None:
        note = "Model trained on all available data; not enough history remained for a separate held-out evaluation."

    return ForecastResponse(
        metric=metric,
        property_id=property_id,
        property_name=property_name,
        horizon_months=horizon_months,
        historical=historical,
        forecast=forecast,
        model_performance=ModelPerformance(**metrics) if metrics else None,
        note=note,
    )


def _handle(db: Session, metric: str, property_id: Optional[str], horizon_months: int) -> ForecastResponse:
    if property_id:
        prop = db.query(models.Property).filter(models.Property.id == property_id).first()
        if not prop:
            raise HTTPException(status_code=404, detail=f"Property '{property_id}' not found")

        historical, forecast = forecast_property(db, property_id, metric, horizon_months)
        # forecast_property doesn't return the model bundle directly (it may train
        # internally); load it again here purely to report metrics — load_or_train
        # reads the just-persisted model from disk, so this doesn't retrain.
        from app.ml.forecast import TARGET_COLUMN_MAP
        from app.ml.train import load_or_train
        bundle = load_or_train(db, TARGET_COLUMN_MAP[metric])

        return _build_response(metric, property_id, prop.name, horizon_months, historical, forecast, bundle)

    historical, forecast, bundle = forecast_portfolio(db, metric, horizon_months)
    return _build_response(metric, None, None, horizon_months, historical, forecast, bundle)


@router.get("/revenue", response_model=ForecastResponse)
def get_revenue_forecast(
    db: Session = Depends(get_db),
    property_id: Optional[str] = Query(None, description="Omit for portfolio-wide forecast"),
    horizon_months: int = Query(3, ge=1, le=12),
):
    return _handle(db, "revenue", property_id, horizon_months)


@router.get("/occupancy", response_model=ForecastResponse)
def get_occupancy_forecast(
    db: Session = Depends(get_db),
    property_id: Optional[str] = Query(None, description="Omit for portfolio-wide forecast"),
    horizon_months: int = Query(3, ge=1, le=12),
):
    return _handle(db, "occupancy", property_id, horizon_months)
