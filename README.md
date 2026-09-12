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

Continue with build order steps 2+ in [docs/tech-stack.md](docs/tech-stack.md#6-suggested-build-order): Investor Profile + Goal Engine logic, then Market Intelligence agents and ChromaDB ingestion.
