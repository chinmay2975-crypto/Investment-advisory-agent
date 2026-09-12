from fastapi import FastAPI

from app.api import routes_investor, routes_goals, routes_recommendation, routes_market_intelligence

app = FastAPI(title="InvestAd API")

app.include_router(routes_investor.router)
app.include_router(routes_goals.router)
app.include_router(routes_recommendation.router)
app.include_router(routes_market_intelligence.router)


@app.get("/health")
def health():
    return {"status": "ok"}
