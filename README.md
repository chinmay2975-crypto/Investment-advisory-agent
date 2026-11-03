# InvestAd

Country-aware investment advisory agent: a FastAPI backend with LangGraph agents (including a
Reflexion-style self-assessment loop), Gemini + Groq LLMs alternating on rate limits/errors,
and a React frontend. Supports **India, the US and the UK**: the market is inferred from your
tickers (`.NS`/`.BO` India, `.L` UK, no suffix US) and you can override it.

> InvestAd provides general information for educational purposes, not licensed financial, tax
> or investment advice.

## Prerequisites

- Python 3.11+ and Node.js 20+
- A Postgres database (Supabase works; `docker compose up -d` gives a local one on port 5433)
- API keys: Gemini, Groq, FRED, NewsAPI (all have free tiers)

## Setup (PowerShell)

```powershell
# Backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env        # fill in DATABASE_URL, API keys, and a random JWT_SECRET
alembic upgrade head

# Frontend
cd frontend
npm install
cd ..
```

`DATABASE_URL` uses `postgresql+psycopg2://...`. Percent-encode special characters in the
password (e.g. `@` becomes `%40`).

## Run

Two terminals:

```powershell
# Terminal 1 - API on http://127.0.0.1:8000 (Swagger UI at /docs)
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

```powershell
# Terminal 2 - React app on http://localhost:5173
cd frontend
npm run dev
```

The Vite dev server proxies `/api/*` to the backend, so the browser never makes cross-origin
calls in development. CORS is still configured (`CORS_ORIGINS` in `.env`) for direct access.

## Test

```powershell
pytest                                # backend: no network, synthetic market data
cd frontend; npm run build            # frontend: typecheck + production build
```

After changing backend schemas, regenerate the typed API client (backend must be running):

```powershell
cd frontend; npm run gen:api
```

## Key endpoints (try them in Swagger UI at /docs)

| Endpoint | Purpose |
|---|---|
| `GET /countries` | Supported countries: currency, benchmark, risk-free proxy, tax summary, accounts, disclaimer |
| `POST /countries/infer` | Infer a portfolio's country from tickers, with confidence and mixed-country breakdown |
| `POST /portfolio/import` | Read holdings from almost any file or pasted text: CSV/TSV, Excel/ODS, JSON, PDF (incl. scans), Word, saved web pages, or a screenshot/photo. Columns are matched automatically and tickers are checked against market data. Nothing is saved until you review and save |
| `POST /portfolio/analyze` | Allocation by country/sector/asset class, returns, volatility, Sharpe, beta, max drawdown, HHI, currency exposure |
| `POST /advice/stream` | Server-Sent Events: the advice agent's stages, resolved country and suggestion sections as they are produced |

Authenticate in Swagger with the **Authorize** button: use your email as the username.

## Project layout

```
app/
  countries/   one config per country (strategy pattern) + offline country inference
  agents/      LangGraph graphs: advice, market_intelligence, refinement, scenario, self_assessment
  api/         FastAPI routers          services/  analysis, market data, tax, PDF, etc.
  llm/         Gemini/Groq clients behind a router with cooldown + fallback
frontend/      Vite + React + TypeScript, Tailwind + shadcn/ui, TanStack Query, Recharts
tests/         pytest suite
docs/          tech-stack.md (original design), llm-context.md (current state for AI assistants)
```

Adding a country: create `app/countries/<country>.py` with a `CountryConfig`, register it in
`app/countries/registry.py`, and it flows through inference, analysis, prompts and the UI.
