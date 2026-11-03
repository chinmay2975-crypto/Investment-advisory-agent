from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    routes_advice,
    routes_auth,
    routes_countries,
    routes_goals,
    routes_holdings,
    routes_investor,
    routes_market_intelligence,
    routes_portfolio,
    routes_recommendation,
    routes_refinement,
    routes_scenario,
    routes_self_assessment,
    routes_tax,
)
from app.config import settings
from app.jobs.self_assessment_job import run_self_assessment_batch

scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not scheduler.running:
        scheduler.add_job(
            run_self_assessment_batch,
            "interval",
            hours=settings.self_assessment_interval_hours,
            id="self_assessment_batch",
            replace_existing=True,
        )
        scheduler.start()
    yield
    if scheduler.running:
        scheduler.shutdown(wait=False)


app = FastAPI(title="InvestAd API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_auth.router)
app.include_router(routes_countries.router)
app.include_router(routes_portfolio.router)
app.include_router(routes_advice.router)
app.include_router(routes_investor.router)
app.include_router(routes_goals.router)
app.include_router(routes_holdings.router)
app.include_router(routes_tax.router)
app.include_router(routes_recommendation.router)
app.include_router(routes_refinement.router)
app.include_router(routes_scenario.router)
app.include_router(routes_self_assessment.router)
app.include_router(routes_market_intelligence.router)


@app.get("/health")
def health():
    return {"status": "ok"}
