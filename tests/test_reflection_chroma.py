import app.services.chroma_client as chroma_client_module


def test_ingest_and_query_reflections_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(chroma_client_module.settings, "chroma_persist_dir", str(tmp_path))
    monkeypatch.setattr(chroma_client_module, "_client", None)

    chroma_client_module.ingest_reflection(
        evaluation_id=1,
        recommendation_id=10,
        text="Recommendation: Shift to 70/30. Rationale: growth focus. Outcome: underperformed slightly.",
        metadata={"assumptions_held": False, "deviation_pct": -2.0, "evaluated_at": "2026-01-01T00:00:00+00:00"},
    )

    results = chroma_client_module.query_similar_reflections("growth focused equity tilt", n_results=1)
    assert len(results) == 1
    assert results[0]["metadata"]["recommendation_id"] == 10


def test_query_similar_reflections_returns_empty_when_no_data(tmp_path, monkeypatch):
    monkeypatch.setattr(chroma_client_module.settings, "chroma_persist_dir", str(tmp_path))
    monkeypatch.setattr(chroma_client_module, "_client", None)

    assert chroma_client_module.query_similar_reflections("anything") == []
