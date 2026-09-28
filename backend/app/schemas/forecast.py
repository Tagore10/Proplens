from pydantic import BaseModel
from typing import Optional


class ForecastPoint(BaseModel):
    month: str
    value: float


class ModelPerformance(BaseModel):
    mae: float
    rmse: float
    r2: float
    train_rows: int
    test_rows: int
    test_cutoff_month: str
    method: str
    feature_importance: dict[str, float]


class ForecastResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    metric: str  # "revenue" or "occupancy"
    property_id: Optional[str] = None
    property_name: Optional[str] = None
    horizon_months: int
    historical: list[ForecastPoint]
    forecast: list[ForecastPoint]
    model_performance: Optional[ModelPerformance] = None
    note: Optional[str] = None
    disclaimer: str = (
        "This is a demonstration model trained on synthetic data. Reported accuracy "
        "reflects fit to this fictional dataset and should not be interpreted as "
        "real-world forecasting accuracy."
    )
