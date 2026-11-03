import chromadb

from app.config import settings
from app.schemas.market_intelligence import GroundingDocument

COLLECTION_NAME = "market_intelligence"
REFLECTION_COLLECTION_NAME = "recommendation_reflections"

_client = None


def get_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    return _client


def get_market_intelligence_collection():
    return get_client().get_or_create_collection(name=COLLECTION_NAME)


def get_reflection_collection():
    return get_client().get_or_create_collection(name=REFLECTION_COLLECTION_NAME)


def query_similar_reflections(query_text: str, n_results: int = 3) -> list[dict]:
    """Semantic retrieval of similar past self-assessment reflections, for Reflexion-style
    long-term memory: grounds each new reflection in how similar past recommendations played out.
    """
    collection = get_reflection_collection()
    count = collection.count()
    if count == 0:
        return []

    results = collection.query(query_texts=[query_text], n_results=min(n_results, count))
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    return [
        {"text": doc, "metadata": meta, "distance": dist}
        for doc, meta, dist in zip(documents, metadatas, distances)
    ]


def ingest_reflection(evaluation_id: int, recommendation_id: int, text: str, metadata: dict) -> None:
    collection = get_reflection_collection()
    collection.upsert(
        ids=[f"evaluation:{evaluation_id}"],
        documents=[text],
        metadatas=[{"recommendation_id": recommendation_id, **metadata}],
    )


def ingest_documents(docs: list[GroundingDocument]) -> int:
    if not docs:
        return 0

    collection = get_market_intelligence_collection()
    collection.upsert(
        ids=[d.id for d in docs],
        documents=[d.text for d in docs],
        metadatas=[
            {"source": d.source, "category": d.category, "as_of": d.as_of.isoformat(), **d.metadata}
            for d in docs
        ],
    )
    return len(docs)


def _run_query(collection, query_text: str, n_results: int, where: dict | None = None) -> list[dict]:
    if n_results <= 0:
        return []
    kwargs = {"query_texts": [query_text], "n_results": n_results}
    if where:
        kwargs["where"] = where
    results = collection.query(**kwargs)

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    return [
        {"text": doc, "metadata": meta, "distance": dist}
        for doc, meta, dist in zip(documents, metadatas, distances)
    ]


def query_context(query_text: str, n_results: int = 5, country: str | None = None) -> list[dict]:
    """With `country`, documents tagged with that country come first, topped up with
    untagged/global documents (e.g. news) so the context is never empty just because a
    market has little country-specific data ingested yet.
    """
    collection = get_market_intelligence_collection()
    if not country:
        return _run_query(collection, query_text, n_results)

    try:
        country_docs = _run_query(collection, query_text, n_results, where={"country": country})
    except Exception:  # e.g. no documents carry the metadata key yet
        country_docs = []
    seen = {doc["text"] for doc in country_docs}
    others = [
        doc
        for doc in _run_query(collection, query_text, n_results * 2)
        if doc["text"] not in seen and doc["metadata"].get("country") in (None, country)
    ]
    return (country_docs + others)[:n_results]
