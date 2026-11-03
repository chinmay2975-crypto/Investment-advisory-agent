from fastapi.testclient import TestClient

from app import serve


def test_api_is_mounted_under_api_prefix():
    with TestClient(serve.app) as client:
        assert client.get("/api/health").json() == {"status": "ok"}


def test_client_side_routes_fall_back_to_index_html(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("<!doctype html><title>InvestAd</title>")
    (tmp_path / "favicon.svg").write_text("<svg/>")
    monkeypatch.setattr(serve, "FRONTEND_DIST", tmp_path)
    with TestClient(serve.app) as client:
        if not any(getattr(r, "path", "") == "/{path:path}" for r in serve.app.routes):
            return  # dist/ absent when the module was imported (e.g. CI before a frontend build)
        assert "InvestAd" in client.get("/goals/3").text
        assert client.get("/favicon.svg").text == "<svg/>"
        assert "InvestAd" in client.get("/../../etc/passwd").text  # never escapes dist/
