# Running and deploying InvestAd

## Local (Windows)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start.ps1            # starts API :8000 + UI :5173, opens browser
powershell -ExecutionPolicy Bypass -File scripts\start.ps1 -AtLogon   # also start on every Windows logon
powershell -ExecutionPolicy Bypass -File scripts\stop.ps1
```

The processes are detached, so they keep running after the terminal closes. Logs go to `.logs\`.
Without `-AtLogon`, they stop when the PC restarts.

## Hosted: one service

`Dockerfile` builds the React app and serves it together with the API from one process
(`app/serve.py`). The UI is at `/` and the API is at `/api/*`. Because both share one origin,
nothing needs CORS configuration.

### Render (free tier)

1. In Supabase, go to **Connect → Session pooler** and copy the URI. Change the scheme to
   `postgresql+psycopg2://`.
2. In Render, go to **New → Blueprint** and select this repository. Render reads `render.yaml`.
3. Fill in the secrets: `DATABASE_URL`, `GEMINI_API_KEY`, `GROQ_API_KEY`, and optionally
   `FRED_API_KEY` and `NEWSAPI_KEY`. Render generates `JWT_SECRET` for you.
4. Deploy. On every start, the container runs `alembic upgrade head` first.

Limits of the free tier:

- The service sleeps after 15 idle minutes. The first request after that takes about 30–60 s.
- The disk is ephemeral, so ChromaDB (market news and reflection memory) is empty after every
  deploy. It refills as the app runs.
- To keep ChromaDB across deploys, use a paid instance and uncomment the `disk:` block in
  `render.yaml`.

### Fly.io (persistent ChromaDB volume)

```sh
fly launch --no-deploy            # uses fly.toml
fly volumes create chroma --size 1
fly secrets set DATABASE_URL=... JWT_SECRET=$(openssl rand -hex 32) GEMINI_API_KEY=... GROQ_API_KEY=...
fly deploy
```

### Keeping Supabase awake

A free Supabase project pauses after 7 days with no activity. The workflow
`.github/workflows/keep-alive.yml` runs every 3 days and calls `/api/health/deep`, which runs a
real query. To turn it on, go to the GitHub repository's **Settings → Secrets and variables →
Actions → Variables** and set `APP_URL` (for example `https://investad.onrender.com`).

### Splitting the UI onto Vercel/Netlify (optional)

1. Build the frontend with `VITE_API_BASE_URL=https://<api-host>/api`.
2. Run the API with `CORS_ORIGINS=https://<ui-host>`.
3. Add a SPA rewrite (all paths → `/index.html`).
