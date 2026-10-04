# InvestAd

Multi-agent investment advisory platform. See [docs/tech-stack.md](docs/tech-stack.md) for the full architecture and build order — this scaffold covers **Step 1** (FastAPI skeleton, Postgres schema, LLM provider abstraction).

## Prerequisites

- Python 3.11+
- Docker Desktop (for local Postgres)
- A Gemini API key — get one free at [aistudio.google.com](https://aistudio.google.com/app/apikey)
- A Groq API key — get one free at [console.groq.com](https://console.groq.com/keys)

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt

copy .env.example .env          # then fill in GEMINI_API_KEY, GROQ_API_KEY, JWT_SECRET

docker compose up -d            # starts Postgres on localhost:5432
alembic revision --autogenerate -m "initial schema"
alembic upgrade head

uvicorn app.main:app --reload   # FastAPI on http://localhost:8000
```

In a second terminal:

```bash
streamlit run frontend/streamlit_app.py   # Streamlit on http://localhost:8501
```

## Verify

- `http://localhost:8000/health` → `{"status": "ok"}`
- `http://localhost:8000/docs` → interactive API docs
- Streamlit dashboard page shows "FastAPI backend reachable"
- `pytest` → health check test passes

## Project layout

```
app/
  main.py          FastAPI entrypoint
  config.py        env/settings
  db/              SQLAlchemy models + session
  llm/             LLMClient interface, Gemini/Groq clients, fallback router
  schemas/         Pydantic request/response models
  api/             route handlers
  agents/          LangGraph nodes/subgraphs (future engines)
alembic/           DB migrations
frontend/          Streamlit app
tests/
docs/              reference docs (tech stack, product spec)
```

## Next steps

Steps 1-8 of the [build order](docs/tech-stack.md#6-suggested-build-order) are in place:

- FastAPI/Postgres skeleton, Investor Profile + Goal Engine
- Market Intelligence agents + ChromaDB ingestion
- AI Recommendation Engine
- Interactive Refinement (`POST /investors/{id}/recommendations/{id}/refine`, backed by a LangGraph subgraph in `app/agents/refinement/`)
- Portfolio Analysis (`app/api/routes_holdings.py` — manual entry, CSV upload, and `GET .../holdings/analysis` for allocation/sector exposure/risk profile via `app/services/portfolio_analysis.py`)
- Scenario Engine (`POST /investors/{id}/goals/{id}/scenarios/`, backed by a parallel LangGraph subgraph in `app/agents/scenario/` that runs Conservative/Balanced/Aggressive variants)
- Approval flow + PDF export (`POST .../recommendations/{id}/approve`, `.../confirm`, and `GET .../recommendations/{id}/export-pdf` for the Investment Target Sheet via `app/services/pdf_export.py`)

- Tax Analysis module (`POST .../holdings/tax-analysis` via `app/services/tax_calculator.py` — deterministic short/long-term capital gains estimate, no LLM)
- Self-Assessment (`app/agents/self_assessment/`) — a Reflexion-style actor/evaluator/reflection loop: `evaluate` computes realized-vs-expected return deviation (yfinance), `retrieve_similar` pulls semantically similar past evaluations from a new ChromaDB collection (`recommendation_reflections`), `reflect` produces a structured reflection via the LLM router, and the result is logged to `recommendation_evaluations` and re-ingested into ChromaDB as precedent for future evaluations — never fed back into the Recommendation Engine automatically. Runs via an APScheduler job (`app/jobs/self_assessment_job.py`, started on app startup, interval configurable via `self_assessment_interval_hours`) evaluating recommendations older than `self_assessment_horizon_days` (default 30) that haven't been evaluated yet; also triggerable manually via `POST .../recommendations/{id}/evaluations/`.

All 11 build-order steps now have at least a working implementation. Remaining polish: a real dashboard (step 9's Streamlit console is a dev test harness, not the target UI) and real JWT auth (currently any client can access any `investor_id`).
