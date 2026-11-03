"""Production entry point: one process serves the API under /api and the built React app at /.

The frontend calls /api/* in both development (Vite proxy strips the prefix) and production
(this mount strips it), so the same build works anywhere with no CORS and no extra config.
Run with: uvicorn app.serve:app --host 0.0.0.0 --port $PORT
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.main import app as api

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

# A mounted sub-app's lifespan never runs, so hand the API's (scheduler start/stop) to the root.
app = FastAPI(title="InvestAd", lifespan=api.router.lifespan_context, docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/api", api)

if FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        """Serve real files from dist/, and index.html for every client-side route."""
        candidate = (FRONTEND_DIST / path).resolve()
        if path and candidate.is_file() and FRONTEND_DIST in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
