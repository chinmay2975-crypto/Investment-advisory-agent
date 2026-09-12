from fastapi import APIRouter

from app.agents.market_intelligence.graph import market_intelligence_graph
from app.agents.market_intelligence.nodes import CATEGORY_KEYS
from app.services.chroma_client import get_market_intelligence_collection

router = APIRouter(prefix="/market-intelligence", tags=["market-intelligence"])


@router.post("/refresh")
def refresh():
    result = market_intelligence_graph.invoke({})
    by_category = {key: len(result.get(key, [])) for key in CATEGORY_KEYS}
    return {"documents_ingested": result.get("documents_ingested", 0), "by_category": by_category}


@router.get("/query")
def query(q: str, n_results: int = 5):
    collection = get_market_intelligence_collection()
    results = collection.query(query_texts=[q], n_results=n_results)

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    return {
        "results": [
            {"text": doc, "metadata": meta, "distance": dist}
            for doc, meta, dist in zip(documents, metadatas, distances)
        ]
    }
