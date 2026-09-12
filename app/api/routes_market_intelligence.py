from fastapi import APIRouter

from app.agents.market_intelligence.graph import market_intelligence_graph
from app.agents.market_intelligence.nodes import CATEGORY_KEYS
from app.services.chroma_client import query_context

router = APIRouter(prefix="/market-intelligence", tags=["market-intelligence"])


@router.post("/refresh")
def refresh():
    result = market_intelligence_graph.invoke({})
    by_category = {key: len(result.get(key, [])) for key in CATEGORY_KEYS}
    return {"documents_ingested": result.get("documents_ingested", 0), "by_category": by_category}


@router.get("/query")
def query(q: str, n_results: int = 5):
    return {"results": query_context(q, n_results)}
