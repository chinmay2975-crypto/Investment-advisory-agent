# InvestAd — Tech Stack & Build Requirements

Reference doc for implementation. Product spec is in `InvestAd — Intelligent Investment Advisory Platform.docx`; this file translates that spec into concrete tech choices and setup requirements.

---

## 1. High-Level Architecture

Multi-agent system orchestrated with LangGraph, backed by FastAPI, Postgres, and a vector store for market/news grounding. Each "Engine" from the product spec maps to a LangGraph node or subgraph.

```
Investor → Goals → Market Intelligence → AI Analysis → Recommendation → Approval → Execution → Performance → Learning
```

---

## 2. Core Stack

| Layer | Choice | Notes |
|---|---|---|
| Agent orchestration | **LangGraph** | Each engine (Profile, Goal, Market Intelligence, Recommendation, Scenario, Tax, Approval, Performance/Learning) = a node or subgraph |
| LLM | **Gemini** and **Groq** (alternating) | Provider-agnostic interface with automatic fallback — see Section 7a |
| Backend API | **FastAPI** | Exposes Suggest / Refine / Optimize / Approve / Dashboard endpoints |
| Relational DB | **PostgreSQL** | Investor profiles, goals, holdings, recommendation history, self-assessment logs — needs joins across time (recommendation-at-T vs outcome-at-T+n) |
| Vector store / RAG | **ChromaDB** | Grounding for news/market context agents (consistent with existing finance-agent project) |
| Frontend | **React** (or **Streamlit** if timeline is tight) | Portfolio dashboard, scenario comparison, recommendation review/refinement chat |
| PDF generation | **WeasyPrint** or **ReportLab** | Investment Target Sheet export |
| Task scheduling | **APScheduler** or a simple cron job | Drives the periodic Self-Assessment batch job |
| Auth | **FastAPI + JWT** (e.g. `fastapi-users`) | Basic investor account/session handling |

---

## 3. Market & News Data Sources

Needed to ground the Market Intelligence Agents (Section 3 of spec). Pick free/low-cost tiers suitable for a college project:

- **Market prices/fundamentals**: `yfinance` (free, no key) or Alpha Vantage / Finnhub (free tier, API key required)
- **Macro/rates/inflation**: FRED API (Federal Reserve Economic Data — free, no cost)
- **News/geopolitical**: NewsAPI, or targeted scraping of Fed/Treasury press releases
- **Historical price data**: same source as live prices (yfinance covers most of this)

All of the above should be normalized and pulled into the RAG/ChromaDB layer as "contextual grounding" documents, timestamped, so the Recommendation Engine can cite what it used and when.

---

## 4. Engine-by-Engine Breakdown

### Investor Profile Engine
- Postgres tables: `investors`, `investor_profile` (risk cadence, horizon, preferences, restrictions)
- Default allocation templates per risk cadence (e.g. Conservative = 60:40 stock:bond), stored as configurable JSON, not hardcoded

### Goal Engine
- Postgres table: `goals` (investor_id, category, target_amount, current_amount, target_date, contribution_cadence, goal_risk_override)
- Simple financial math module (required return calculation, contribution-sufficiency check) — plain Python, no LLM needed here

### Market Intelligence Agents
- LangGraph subgraph: parallel agent nodes per data source (market behavior, rates, inflation, sector performance, geopolitical, news)
- Each agent writes normalized documents into ChromaDB with timestamp + source metadata

### Portfolio Analysis Engine
- Ingests existing holdings (manual entry or CSV upload for a college-project scope — no brokerage integration needed)
- Computes current allocation, sector exposure, risk profile, historical yield

### AI Recommendation Engine
- LangGraph node: takes profile + goal + grounded context (retrieved from ChromaDB) → LLM call
- Structured output (JSON) per recommendation: `what`, `why`, `expected_behavior`, `goal_probability`, `risks`
- Enforce output schema with Pydantic to keep "estimate vs. prediction vs. fact" distinction structurally separate, not just prose

### Interactive Refinement
- Conversational loop: user message ("remove NVIDIA", "more bonds") → re-invoke Recommendation Engine node with updated constraints, same goal/session state preserved in LangGraph state object

### Scenario Engine
- Runs Recommendation Engine 3x with different risk parameters (Conservative/Balanced/Aggressive) → returns comparison set

### Tax Analysis Engine (optional module)
- Simple rules-based calculator (short-term vs long-term capital gains thresholds, estimated tax bracket input) — does not need an LLM, just deterministic logic

### Recommendation & Approval Engine
- Postgres table: `recommendations` (status: pending/approved/confirmed, full recommendation payload, generated_at)
- PDF export (Investment Target Sheet) via WeasyPrint/ReportLab from the recommendation payload

### Performance & Learning Engine (Self-Assessment)
- Scheduled job (APScheduler) — periodically compares `recommendations` at time T against actual market data at T+n
- Logs deviation, contributing factors, whether assumptions held
- Implemented as a **governed batch evaluation**, not a live self-modifying loop: Reflexion-style actor/evaluator/reflection pattern, but reflections are surfaced to a review table, not auto-applied to the LLM's logic

---

## 5. Data Model Summary (Postgres)

- `investors`
- `investor_profile`
- `goals`
- `holdings` (current portfolio)
- `recommendations` (proposed + historical, with status)
- `recommendation_evaluations` (self-assessment outcomes, linked to `recommendations`)

---

## 6. Suggested Build Order

1. FastAPI skeleton + Postgres schema + auth
2. Investor Profile Engine + Goal Engine (no LLM yet — pure CRUD + math)
3. Market Intelligence Agents → ChromaDB ingestion pipeline
4. AI Recommendation Engine (single LLM call, structured output) using grounded context
5. Interactive Refinement (conversation state via LangGraph)
6. Portfolio Analysis + Existing Portfolio Optimization
7. Scenario Engine (parallel variants of step 4)
8. Approval flow + PDF export
9. Dashboard (React/Streamlit)
10. Tax Analysis module (optional, deterministic)
11. Self-Assessment scheduled job + evaluation table

---

## 7a. LLM Provider Strategy — Gemini + Groq Alternation

Both a Gemini API key and a Groq API key will be used, with automatic switching based on rate limits/errors rather than committing to a single provider.

- **Provider interface**: a single `LLMClient` abstraction (e.g. `generate(prompt, schema) -> StructuredOutput`) with two concrete implementations: `GeminiClient`, `GroqClient`. Every engine (Recommendation, Scenario, Self-Assessment) calls the abstraction, never a provider SDK directly.
- **Selection/fallback logic**:
  - Maintain a simple state per provider: `available` / `cooling_down` (with a resume timestamp).
  - On a call: try the current primary provider; on a rate-limit error (HTTP 429) or transient server error (5xx), mark that provider `cooling_down` (respecting `Retry-After` header if present, else a fixed backoff), and immediately retry the same request on the other provider.
  - If both providers are `cooling_down`, queue/backoff and retry the primary after the shorter cooldown expires.
  - Track failure/success counts per provider so the system can prefer whichever has more remaining quota if that's exposed by the API, otherwise alternate round-robin by default to spread load across both keys.
- **Structured output consistency**: since Gemini and Groq (Groq typically serving Llama/Mixtral-class models) format structured/JSON output differently, keep the Pydantic schema validation at the `LLMClient` boundary — validate and coerce whichever provider responds before it reaches an engine, so engines never need to know which provider actually served the request.
- **Logging**: record which provider served each recommendation (useful for the Self-Assessment Engine — provider choice could itself be a factor worth tracking if quality diverges between the two).
- **Config**: both `GEMINI_API_KEY` and `GROQ_API_KEY` in environment/config; no default single-provider assumption anywhere in the codebase.

---

## 7. Notes / Constraints for Claude Code

- Keep LLM provider behind an interface, with Gemini and Groq alternating automatically on rate limits/errors (see Section 7a) — never hardcode a single provider.
- Recommendation outputs must be structured (Pydantic schema), not free-text, to preserve the fact/assumption/prediction distinction from the spec.
- Self-Assessment loop must be a controlled, logged, human-reviewable batch process — never an autonomous rewrite of recommendation logic.
- No live brokerage/trading integration required — "Confirm Investment" is a manual user action that just updates tracked state.
