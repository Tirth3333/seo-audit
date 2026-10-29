# Deployment

**Status: not deployed.** No live URL exists yet. The build environment had no hosting credentials and no Docker daemon, so the Dockerfile has not been built; the equivalent single-process setup (FastAPI serving `frontend/dist` from `backend/static`) was run and verified locally.

## Recommended: one Docker web service on Render (free)

Why: one service serves both the API and the UI (no CORS, one URL), the crawler needs a long-running Python process (not serverless), and Render's free plan supports this.

Free-plan caveats (from [Render's free tier docs](https://render.com/docs/free), checked Oct 2026):
- Spins down after 15 minutes without traffic; the first request afterwards takes about a minute.
- 750 free instance hours per workspace per month.
- **Ephemeral filesystem** — the SQLite audit history is lost on restart, redeploy or spin-down. Bundled sample reports are part of the image and persist.
- Render may suspend services generating unusually high outbound traffic — the provided `render.yaml` therefore lowers crawl limits (50 pages, depth 3, concurrency 3, 0.5 s delay).

### Steps

1. Push the repository to GitHub (see README).
2. In Render: **New → Blueprint**, select the repository. Render reads `render.yaml` and creates `rankwise-seo-audit` (Docker, free plan, health check `/api/health`).
   - Or **New → Web Service**, choose the repo, runtime **Docker**, plan **Free**, health check path `/api/health`.
3. Set environment variables (Blueprint pre-fills most):

| Variable | Value |
|---|---|
| `CORS_ORIGINS` | your service URL, e.g. `https://rankwise-seo-audit.onrender.com` (only needed if the UI is hosted elsewhere) |
| `MAX_PAGES_LIMIT` / `MAX_DEPTH_LIMIT` | `50` / `3` |
| `CONCURRENCY` / `CRAWL_DELAY_S` | `3` / `0.5` |
| `LLM_PROVIDER` | `none` (or `anthropic` / `openai`) |
| `LLM_API_KEY` | secret — only if AI summaries are wanted (paid API usage) |
| `ALLOW_PRIVATE_HOSTS` | **never set in production** |

4. Deploy, then verify:
   ```bash
   curl https://<your-service>.onrender.com/api/health      # {"status":"ok",...}
   ```
   Open the URL, load the sample report, then audit a site you are permitted to crawl and download the CSV/PDF.
5. Record the verified URL below and in the submission checklist.

### Build and start commands (what the Dockerfile does)

```bash
# build
cd frontend && npm ci && npm run build
cp -r frontend/dist backend/static
pip install -r backend/requirements.txt
# start (from backend/)
uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers
```

Local image test (requires Docker):
```bash
docker build -t rankwise-seo-audit .
docker run -p 8000:8000 rankwise-seo-audit      # http://localhost:8000
```

## Alternative: split frontend and backend

- **Backend** on Render (Docker or Python runtime; root `backend/`, build `pip install -r requirements.txt`, start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`). Set `CORS_ORIGINS` to the frontend origin.
- **Frontend** as a static site (Render Static Site, Netlify, Vercel, Cloudflare Pages): root `frontend/`, build `npm ci && npm run build`, publish `dist`, env `VITE_API_BASE_URL=https://<backend-host>`. Add an SPA rewrite of `/*` → `/index.html`.

## Costs

Free for the app itself. Optional costs: a paid Render instance (no spin-down, more RAM), a persistent disk or managed Postgres for durable history, and LLM API usage if AI summaries are enabled.

## Verified URLs

| Environment | URL | Verified |
|---|---|---|
| Production | _pending — not deployed_ | no |
| Local | http://localhost:8000 (single-process) | yes, in development sandbox only — not a public URL |
