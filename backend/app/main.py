from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.api import dashboard, properties, leases, data_quality, risk, analytics, forecast, csv_import, ai_insights

# Tables are created on startup if they don't exist yet.
# (seed_data.py is run separately/manually to populate synthetic data.)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="PropLens API",
    description="Real Estate Data Intelligence & Portfolio Analytics Platform — synthetic demo data only.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router)
app.include_router(properties.router)
app.include_router(leases.router)
app.include_router(data_quality.router)
app.include_router(risk.router)
app.include_router(analytics.router)
app.include_router(forecast.router)
app.include_router(csv_import.router)
app.include_router(ai_insights.router)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "PropLens API"}
