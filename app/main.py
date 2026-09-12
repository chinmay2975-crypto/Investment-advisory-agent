from fastapi import FastAPI

from app.api import routes_investor, routes_goals, routes_recommendation

app = FastAPI(title="InvestAd API")

app.include_router(routes_investor.router)
app.include_router(routes_goals.router)
app.include_router(routes_recommendation.router)


@app.get("/health")
def health():
    return {"status": "ok"}
