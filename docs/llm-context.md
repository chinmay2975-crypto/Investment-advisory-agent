# InvestAd — Context for an LLM picking up this codebase

This is a handoff document, not a spec. It describes what actually exists in the
repository today, as opposed to `docs/tech-stack.md`, which is the *original design
doc* (still accurate for intent/architecture, but doesn't reflect implementation
status — treat it as background, not ground truth on what's done).

## What this is

A multi-agent investment advisory platform: an investor sets up a risk profile and
goals, the system generates LLM-backed portfolio recommendations grounded in real
market/macro/news data, lets the investor refine or compare scenarios of that
recommendation conversationally, and periodically self-evaluates past
recommendations against what actually happened in the market.

Originally scoped as a college project; has since been pointed at a real hosted
Postgres (Supabase) and had real auth added, so treat it as a small real system,
not a throwaway prototype.

## Tech stack (as actually used, not just as planned)

- **FastAPI** backend, **SQLAlchemy** + **Alembic** for Postgres, hosted on **Supabase**
  (not local Docker anymore — a `docker-compose.yml` for local Postgres exists but
  is unused in normal operation)
- **LangGraph** for every multi-step agent flow (see "Agent graphs" below) — used
  for real graph structure/parallelism, not as a buzzword; simple CRUD/math stays
  as plain FastAPI + service functions
- **Gemini** + **Groq**, behind a provider-agnostic `LLMRouter` with automatic
  cooldown/fallback (`app/llm/`) — every engine calls `router.generate(prompt, schema)`,
  never a provider SDK directly
- **ChromaDB**, file-persisted (`chroma_db/` — not durable across container
  restarts if this is ever deployed in a container; needs a volume or hosted
  vector DB if that matters)
- **yfinance**, **FRED API**, **NewsAPI** for real market/macro/news grounding
  (not mocked in production paths — tests mock these)
- **JWT auth** (`python-jose`) with access + refresh tokens, **bcrypt** via
  `passlib` for password hashing, a hand-rolled in-memory login rate limiter
  (no Redis)
- **ReportLab** for PDF export
- **APScheduler** for the self-assessment batch job, started via FastAPI's
  `lifespan` context
- **Streamlit** frontend (`frontend/streamlit_app.py`) — a single file, ~900
  lines. This was deliberately chosen over React for speed; it's had a real
  design pass (cards, chat UI for refinement, colored badges) so it's not just a
  raw test console anymore, but it's still one Streamlit script, not a proper SPA.
- **pytest**, 81 tests, all passing as of the last run. Fixtures in
  `tests/conftest.py` use an in-memory SQLite DB (via `get_db` dependency
  override) and a `FastAPI TestClient`, not the real Supabase DB.

## Directory layout

```
app/
  main.py              FastAPI app, router registration, APScheduler lifespan
  config.py            pydantic-settings, reads .env
  security.py          password hashing, JWT create/decode (access + refresh)
  dependencies.py      get_current_investor, require_self (route-level auth)
  rate_limit.py         in-memory login attempt tracker
  db/
    models.py          all SQLAlchemy models
    session.py          engine, SessionLocal, get_db, Base
  api/                 one routes_*.py file per resource, each an APIRouter
  schemas/             one file per resource, Pydantic request/response models
  services/            business logic that doesn't need a LangGraph (math,
                       allocation templates, market/macro/news fetchers,
                       portfolio analysis, tax calc, PDF export, deviation calc)
  agents/              LangGraph subgraphs — one package per multi-step flow:
    market_intelligence/   parallel fan-out over 6 category nodes -> ingest
    refinement/             classify_constraint -> refine_recommendation
    scenario/               3 parallel variant nodes (conservative/balanced/aggressive)
    self_assessment/        evaluate -> retrieve_similar -> reflect
  llm/                 LLMClient interface, GeminiClient, GroqClient, LLMRouter, factory
  jobs/                self_assessment_job.py (APScheduler target)
  data/                static JSON config: allocation_templates.json, tax_brackets.json
alembic/versions/       4 migrations (initial schema, +contribution_amount,
                        +refinement tables, +scenario_runs)
frontend/streamlit_app.py   the entire frontend, single file
tests/                  29 test files, 81 tests, conftest.py has the shared fixtures
docs/
  tech-stack.md         original design doc (Section 6 has the 11-step build order)
  llm-context.md        this file
```

## Data model (Postgres, via Supabase)

`investors`, `investor_profile`, `goals`, `holdings`, `recommendations`,
`recommendation_evaluations`, `refinement_sessions`, `refinement_messages`,
`scenario_runs`. Every FK relationship is exactly what you'd guess from the
names. `recommendations.status` is `pending` -> `approved` -> `confirmed`,
forward-only, enforced in `routes_recommendation.py`.

## Auth model

- `POST /auth/login` (OAuth2 password form) returns `{access_token, refresh_token,
  token_type, investor_id}`. Access tokens last 60 min, refresh tokens 7 days
  (both configurable). `POST /auth/refresh` exchanges a refresh token for a new
  access token.
- Every investor-scoped router has `dependencies=[Depends(require_self)]` at the
  **router** level (not per-route) — `require_self` reads the `{investor_id}`
  path param and 403s if it doesn't match the token's subject. This means one
  investor's token can never touch another investor's data, enforced centrally,
  not per-endpoint.
- `app/dependencies.py` has both `get_current_investor` (decodes + validates the
  JWT, checks `type == "access"` so a refresh token can't be used as an access
  token) and `require_self`.
- Login has a naive in-memory rate limiter (5 failed attempts / 15 min, keyed by
  email) in `app/rate_limit.py`. **It's per-process and resets on restart** — a
  known limitation if this ever runs multiple backend replicas.

## Agent graphs (LangGraph) — the pattern to follow if adding another

Every graph package has the same three files:
- `state.py` — a `TypedDict` describing the graph's state
- `nodes.py` — plain functions `(state) -> dict` that return partial state updates
- `graph.py` — wires nodes with `StateGraph`, compiles once at import time into a
  module-level singleton (e.g. `refinement_graph`)

Nodes call `get_router()` from `app.llm.factory` directly (not injected) when
they need an LLM call — this is deliberate, keeps nodes self-contained and easy
to test by monkeypatching `app.agents.<name>.nodes.get_router`.

## What's implemented (all 11 steps of the original build order, plus more)

1. FastAPI/Postgres skeleton — done, now on Supabase
2. Investor Profile + Goal Engine — done (`app/services/goal_math.py`,
   `goal_analysis.py`, `allocation.py`)
3. Market Intelligence + ChromaDB ingestion — done, real yfinance/FRED/NewsAPI
   calls, real persisted ChromaDB
4. AI Recommendation Engine — done, structured Pydantic output enforced at the
   LLM boundary (`app/schemas/recommendation.py::RecommendationOutput`)
5. Interactive Refinement — done, LangGraph subgraph, structured constraint
   accumulator (exclusions/tilts/other) replayed into every prompt so earlier
   turns' constraints aren't lost
6. Portfolio Analysis — done (`app/services/portfolio_analysis.py`); asset-class
   classification is a yfinance-category-string heuristic, not authoritative
7. Scenario Engine — done, 3-way parallel LangGraph fan-out
8. Approval + PDF export — done, ReportLab-generated Investment Target Sheet
9. Dashboard — done as a Streamlit page (not React), portfolio/goals/latest-rec
   overview with drill-down links to the other pages
10. Tax Analysis — done, deterministic short/long-term capital gains estimate;
    bracket numbers in `app/data/tax_brackets.json` are illustrative 2024 figures
11. Self-Assessment — done, **Reflexion-style actor/evaluator/reflection loop**:
    `evaluate` node computes realized-vs-expected return deviation (yfinance,
    benchmarked against a hardcoded 6% assumption — a known simplification),
    `retrieve_similar` queries a ChromaDB collection (`recommendation_reflections`)
    for semantically similar past evaluations as precedent, `reflect` produces a
    structured reflection via the LLM router. Logged to
    `recommendation_evaluations` and re-ingested into ChromaDB — this is the
    Reflexion "memory" loop, but per spec it never auto-modifies the
    Recommendation Engine, only produces a human-reviewable record. Runs via
    APScheduler (default: every 24h, evaluating recommendations >30 days old
    that haven't been evaluated), plus a manual trigger endpoint.

Real auth (JWT, was the biggest originally-flagged gap) and a redesigned
Streamlit frontend (card-based, chat-style refinement, not a raw form console)
were both added after the original 11 steps.

## Known gaps / rough edges (in rough priority order)

- **Nothing is deployed** — backend, frontend, and ChromaDB all still run as
  local processes against Supabase. No CORS config, no CI pipeline.
- **No password reset / email verification.**
- **APScheduler self-assessment job and the login rate limiter are both
  in-process, single-instance only** — would need rethinking (e.g. Redis, a
  proper job queue) if this ever runs more than one backend replica.
- **ChromaDB is a local file directory** (`chroma_db/`) — not durable in most
  container deployments without a mounted volume.
- Portfolio stock/bond classification, self-assessment's deviation benchmark,
  and the tax brackets are all acknowledged simplifications (see steps 6, 10,
  11 above) — fine for current scope, flagged in case correctness matters more
  later.
- `requirements.txt` isn't pinned to exact versions.
- Frontend is one large Streamlit file — no component boundaries, no tests for
  it beyond manual `streamlit.testing.v1.AppTest` smoke checks run ad hoc during
  development (not part of the pytest suite).

## Running it

Needs `.env` with: `DATABASE_URL` (Supabase Postgres, `postgresql+psycopg2://...`
— note any special characters in the password must be percent-encoded, e.g. `@`
-> `%40`), `GEMINI_API_KEY`, `GROQ_API_KEY`, `FRED_API_KEY`, `NEWSAPI_KEY`,
`CHROMA_PERSIST_DIR`, `JWT_SECRET` (must be a real random value, not the repo's
placeholder), `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`. See `app/config.py`
for the full list including defaults (refresh token expiry, rate limit
thresholds, self-assessment horizon/interval).

```bash
alembic upgrade head                         # apply migrations
uvicorn app.main:app --reload                # backend on :8000
streamlit run frontend/streamlit_app.py      # frontend on :8501
pytest                                       # 81 tests, uses in-memory SQLite, no external calls needed
```

`alembic/env.py` builds its engine directly from `settings.database_url` rather
than through `ConfigParser`'s `set_main_option`/`get_section` — this was a
deliberate fix, because `ConfigParser` does `%`-interpolation on values and a
URL-encoded password (containing `%40` etc.) breaks it otherwise. Don't revert
that without re-hitting the same bug.
