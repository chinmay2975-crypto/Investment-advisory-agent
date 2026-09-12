import chromadb

from app.config import settings
from app.schemas.market_intelligence import GroundingDocument

COLLECTION_NAME = "market_intelligence"

_client = None


def get_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    return _client


def get_market_intelligence_collection():
    return get_client().get_or_create_collection(name=COLLECTION_NAME)


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
