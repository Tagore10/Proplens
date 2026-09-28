"""
Trains and evaluates the forecasting models.

METHODOLOGY (documented for the interview-prep doc):

    Algorithm: RandomForestRegressor (scikit-learn). Chosen because it
    handles the nonlinear, archetype-driven patterns in the synthetic data
    (stable/growing/declining/high-performer/distressed properties) without
    needing manual feature interactions, while still being explainable via
    feature_importances_ — no black box.

    Split: TIME-AWARE, not random. The dataset spans ~11 usable months per
    property. The most recent TEST_MONTHS months (across every property) are
    held out as the test set; the model trains only on earlier months. This
    mirrors how the model would actually be used — predicting the future
    from the past — and avoids the inflated accuracy a random split would
    give by leaking nearby months into training.

    After evaluation, the model is refit on ALL available data (train + test)
    for the version that actually gets used to forecast — standard practice:
    evaluate on a genuine holdout, then use every available data point for
    the deployed model. The reported MAE/RMSE/R2 come from the holdout
    evaluation, not the refit model, so they're an honest estimate.

DISCLAIMER: this is a demonstration model trained on synthetic data. Its
reported accuracy describes how well it fits this fictional dataset — it is
not a claim about real-world forecasting accuracy.

HONEST CAVEAT on feature importance: `operating_expense` typically ranks as
a near-equally strong predictor as the lag feature. This is expected, not a
bug — in the seed data, each property's monthly opex is generated as a
random 28-50% fraction of that month's revenue, so it's informationally
close to a disguised version of the target. In a real dataset, expenses and
revenue wouldn't be mechanically linked like this; a production model would
need to check for and account for that kind of leakage.
"""
import joblib
from pathlib import Path
from datetime import datetime, timezone
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sqlalchemy.orm import Session

from app.ml.features import build_supervised_frame, FEATURE_COLUMNS

MODEL_DIR = Path(__file__).resolve().parents[3] / "ml"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

TEST_MONTHS = 2
MIN_TRAIN_ROWS = 20
MIN_TEST_ROWS = 5


def _model_path(target_col: str) -> Path:
    return MODEL_DIR / f"{target_col}_forecast_model.joblib"


def time_aware_split(frame, test_months: int = TEST_MONTHS):
    months = sorted(frame["month"].unique())
    if len(months) <= test_months:
        # Not enough distinct months for a meaningful holdout — use the very
        # last month as a minimal test set rather than failing outright.
        cutoff = months[-1]
    else:
        cutoff = months[-test_months]
    train = frame[frame["month"] < cutoff]
    test = frame[frame["month"] >= cutoff]
    return train, test, str(cutoff.date())


def train_and_evaluate(db: Session, target_col: str) -> dict:
    frame, encoders = build_supervised_frame(db, target_col)

    if len(frame) < MIN_TRAIN_ROWS + MIN_TEST_ROWS:
        # Not enough history anywhere to train responsibly — surface this
        # honestly instead of fabricating a model or a score.
        return {
            "model": None,
            "encoders": encoders,
            "metrics": None,
            "insufficient_data": True,
            "trained_at": datetime.now(timezone.utc).isoformat(),
        }

    train_df, test_df, cutoff = time_aware_split(frame)

    if len(train_df) < MIN_TRAIN_ROWS or len(test_df) < MIN_TEST_ROWS:
        train_df, test_df = frame, frame.iloc[0:0]  # degrade gracefully: train on everything, skip eval

    model = RandomForestRegressor(n_estimators=200, max_depth=8, min_samples_leaf=3, random_state=42)
    model.fit(train_df[FEATURE_COLUMNS], train_df["target"])

    metrics = None
    if len(test_df) >= MIN_TEST_ROWS:
        preds = model.predict(test_df[FEATURE_COLUMNS])
        mae = mean_absolute_error(test_df["target"], preds)
        rmse = mean_squared_error(test_df["target"], preds) ** 0.5
        r2 = r2_score(test_df["target"], preds)
        metrics = {
            "mae": round(float(mae), 2),
            "rmse": round(float(rmse), 2),
            "r2": round(float(r2), 4),
            "train_rows": int(len(train_df)),
            "test_rows": int(len(test_df)),
            "test_cutoff_month": cutoff,
            "method": "RandomForestRegressor, time-aware split (most recent "
                      f"{TEST_MONTHS} month(s) held out), evaluated before final refit",
            "feature_importance": {
                col: round(float(imp), 4)
                for col, imp in zip(FEATURE_COLUMNS, model.feature_importances_)
            },
        }

    # Refit on everything for the model that actually gets used to forecast.
    final_model = RandomForestRegressor(n_estimators=200, max_depth=8, min_samples_leaf=3, random_state=42)
    final_model.fit(frame[FEATURE_COLUMNS], frame["target"])

    bundle = {
        "model": final_model,
        "encoders": encoders,
        "metrics": metrics,
        "insufficient_data": False,
        "feature_columns": FEATURE_COLUMNS,
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }

    joblib.dump(bundle, _model_path(target_col))
    return bundle


def load_or_train(db: Session, target_col: str, force_retrain: bool = False) -> dict:
    path = _model_path(target_col)
    if not force_retrain and path.exists():
        return joblib.load(path)
    return train_and_evaluate(db, target_col)
