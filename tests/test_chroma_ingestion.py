from datetime import datetime, timezone

import app.services.chroma_client as chroma_client_module
from app.schemas.market_intelligence import GroundingDocument


def test_ingest_and_query_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(chroma_client_module.settings, "chroma_persist_dir", str(tmp_path))
    monkeypatch.setattr(chroma_client_module, "_client", None)

    docs = [
        GroundingDocument(
            id="rates:DFF:2026-01-01",
            text="Federal Funds Effective Rate was 5.33 as of 2026-01-01.",
            source="FRED",
            category="rates",
            as_of=datetime(2026, 1, 1, tzinfo=timezone.utc),
            metadata={"series_id": "DFF", "value": 5.33},
        ),
        GroundingDocument(
            id="news:https://example.com/a1",
            text="Markets rally on rate cut hopes. Stocks rose broadly.",
            source="Reuters",
            category="news",
            as_of=datetime(2026, 1, 1, 12, tzinfo=timezone.utc),
            metadata={"url": "https://example.com/a1"},
        ),
    ]

    count = chroma_client_module.ingest_documents(docs)
    assert count == 2

    collection = chroma_client_module.get_market_intelligence_collection()
    results = collection.query(query_texts=["interest rate"], n_results=1)

    assert results["metadatas"][0][0]["category"] == "rates"


def test_ingest_empty_list_returns_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(chroma_client_module.settings, "chroma_persist_dir", str(tmp_path))
    monkeypatch.setattr(chroma_client_module, "_client", None)

    assert chroma_client_module.ingest_documents([]) == 0
