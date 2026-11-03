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

### Hugging Face Spaces (recommended, free)

The app ends up at `https://<hf-username>-<space-name>.hf.space`. GitHub deploys it again after
every push to `main` that passes CI.

1. **Create the Space.** On huggingface.co, go to **New → Space**. Pick a name (for example
   `investad`), choose **Docker → Blank** as the SDK, and select the free CPU hardware.
2. **Add the secrets.** In the Space, go to **Settings → Variables and secrets** and add these as
   *secrets*:
   - `DATABASE_URL`: use Supabase's **Session pooler** URI, from **Connect → Session pooler**
     (`postgresql+psycopg2://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres`).
     Don't use the direct `db.<ref>.supabase.co` host, which is IPv6-only and unreachable from Spaces.
   - `JWT_SECRET`: any long random string.
   - `GEMINI_API_KEY` and `GROQ_API_KEY`.
   - Optional: `FRED_API_KEY`, `NEWSAPI_KEY`, `SMTP_*`.
   - `APP_BASE_URL`: the `.hf.space` URL.
3. **Create a token.** On Hugging Face, go to **Settings → Access Tokens** and create a token with
   **Write** access.
4. **Connect GitHub.** In the GitHub repository, go to **Settings → Secrets and variables →
   Actions** and add:
   - secret `HF_TOKEN`: the token from step 3;
   - variable `HF_SPACE`: for example `chinmay2975/investad`;
   - variable `APP_URL`: the `.hf.space` URL. This turns on the daily keep-alive ping, which stops
     the Space sleeping after 48 h idle and stops Supabase from pausing.
5. **Deploy.** Go to **Actions → deploy-hf → Run workflow**. The first build takes about 5 minutes,
   and you can watch it in the Space's **Logs** tab.

Notes:
- Open the `.hf.space` URL directly. On the huggingface.co Space page, the app runs inside an
  iframe, so log-in may not persist there.
- Free Spaces have no persistent disk, so ChromaDB memory resets whenever the Space restarts.
- If the logs show a connection timeout to the database, the URL is not the session pooler.

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
