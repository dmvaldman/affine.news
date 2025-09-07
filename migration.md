## Migration Plan: App Engine → Vercel + Neon + GitHub Actions

This document outlines how to migrate the existing Flask + Cloud Tasks/Translate + Cloud SQL (Postgres) App Engine project to a modern stack:

- Vercel (frontend + lightweight API routes)
- Neon (managed Postgres)
- GitHub Actions (scheduled crawls using the existing `newspaper`-based crawler)


### 1) Current Architecture Overview

- Flask app in `main.py` renders `templates/index.html` and exposes API routes: `/crawl`, `/crawl/<uuid>`, `/translate`, `/translate/<uuid>`, `/query`, `/stats`.
- Background work: `/crawl` enqueues per-paper tasks via Google Cloud Tasks pointing back to `/crawl/<uuid>`. `/translate` does similar for translations.
- DB: Postgres via `psycopg2` connection in `server/db/db.py`. In PROD connects through Cloud SQL instance socket. Tables created in `server/db/initialize.py` and used via lightweight models in `server/db/models/*`.
- Crawling: `server/models/Crawler.py` powered by vendored `server/lib/newspaper`.
- Translation: `server/services/translate.py` uses Google Cloud Translation API with a local service account JSON.
- Frontend: Static HTML/JS/CSS served by Flask, assets in `static/` and `templates/index.html` calling `/query` and `/stats`.


### 2) Target Architecture Overview

- Frontend: Static site built with Vite (no React). The existing `templates/index.html` and `static/*` move into a Vite project and build to `/dist` for Vercel.
- API: Lightweight serverless endpoints via Vercel Functions (Node.js or Python). Endpoints replacing Flask routes:
  - `GET /api/query`
  - `GET /api/stats`
  - `POST /api/crawl` (kicks off GitHub Actions dispatch or writes a job record)
  - Optionally remove per-UUID endpoints; GitHub Actions will iterate over papers.
- DB: Neon Postgres. Use `psycopg2-binary` or `asyncpg`/`pg` from Node.js. Replace Cloud SQL socket with standard Postgres URL.
- Background jobs: GitHub Actions scheduled workflow (cron) running a Python job that imports the existing crawl code and writes to Neon using environment secrets.
- Translation: Either keep Google Cloud Translate using an API key (not service account JSON) or switch to another translation provider. For now, keep GCP Translate but through API key credentials stored as GitHub Secret and Vercel Secret.
 - Translation: Use Google Cloud Translate via API key initially (no service account file). Add a thin provider abstraction so we can later switch to another service (e.g., DeepL, Azure, OpenAI) without touching callers.


### 3) Environment Variables and Secrets

Replace `.env` values currently used by Flask/Python with Vercel/Actions secrets:

- `ENV` (use `PROD`/`DEV` only if needed; prefer feature flags)
- `DB_USER`, `DB_PASS`, `DB_NAME` (or a single `DATABASE_URL` for Neon: `postgres://user:pass@host:port/db`)
- `GOOGLE_PROJECT` (if needed by translate)
- `GOOGLE_TRANSLATE_API_KEY` (recommended vs service account JSON)

Secrets storage:
- Vercel Project → Settings → Environment Variables
- GitHub → Settings → Secrets and variables → Actions


### 4) Database Migration to Neon

Schema lives in `server/db/initialize.py`. Steps:
1. Create a Neon project and database.
2. Create a read/write role and generate `DATABASE_URL`.
3. Recreate tables on Neon (convert `initialize.py` into SQL or a Python migration script). Example table set: `paper`, `category_set`, `crawl`, `article`.
4. Data migration:
   - If data exists in Cloud SQL, `pg_dump` the App Engine Postgres and `psql` import into Neon.
   - If starting fresh, seed via `newspaper_store.json` using `initialize.py` adjusted to connect to Neon.
5. Update application DB code to read `DATABASE_URL` and connect over the public Neon endpoint.

Notes:
- Replace `server/db/db.py` to parse `DATABASE_URL` (preferred) or use discrete vars. For Vercel Node APIs, use a Node Postgres client; for GitHub Actions crawler, keep Python `psycopg2-binary`.


### 5) Frontend Migration to Vercel (Vite)

- Create a Vite project (vanilla JS or TS) in `web/`.
- Move `templates/index.html` to `web/index.html` and copy assets from `static/` to `web/public/` (e.g., `web/public/js`, `web/public/css`).
- Update asset paths to root-based (`/js/datamaps.js`, `/css/app.css`) or relative to `public/` as needed.
- Update any AJAX calls in your JS (currently `static/js/app.js`) to hit `/api/query` and `/api/stats`.
- Deploy on Vercel with framework preset “Vite” and output directory `web/dist`.

Project layout options on Vercel:
- Single project at repo root: put Vite at repo root and `api/` functions at repo root.
- Monorepo (recommended here): set Vercel “Root Directory” to `web/` for the frontend project; create a second Vercel project with root at the repo root (or `api/`) for API functions.


### 6) API Re-implementation on Vercel

Endpoints to port:
- `GET /api/query` → Use the SQL in `server/services/query.py`. Return JSON grouped by ISO.
- `GET /api/stats` → Use the SQL in `server/services/stats.py`. Return `{ iso: [{date, iso, total, rolling}, ...] }`.

Implementation choices:
- Vercel Node.js Functions (`api/query.ts`, `api/stats.ts`) using the `pg` library.
- Or Vercel Python Functions (`api/query.py`, `api/stats.py`) using `psycopg2-binary`.

Env needed: `DATABASE_URL`.


### 7) Scheduled Crawls via GitHub Actions

Create a workflow `.github/workflows/crawl.yml`:
- Trigger: cron (e.g., `0 */6 * * *`) and manual dispatch.
- Job steps:
  - Check out repo
  - Set up Python 3.11
  - Install Python dependencies (subset: `psycopg2-binary`, `requests`, `lxml`, `beautifulsoup4`, vendored `server/lib/newspaper` requirements)
  - Export `DATABASE_URL` and any provider keys
  - Run a script `python server/scripts/run_crawl.py --max-articles=30`

Implement `server/scripts/run_crawl.py` that:
- Connects to Neon using `DATABASE_URL`
- Loads papers (`Papers().load()`)
- Iterates and crawls using `Crawler` logic (`crawl_paper_by_uuid`)
- Commits batched inserts

Translation:
 - Optionally run after crawling as a separate scheduled job, or integrate into crawl job.
 - Replace service account JSON usage with API key based auth. Recommended envs:
   - `TRANSLATE_PROVIDER=google`
   - `GOOGLE_TRANSLATE_API_KEY=<secret>`
 - Implement a small provider interface (e.g., `server/services/translator.py`) with `translate_title(text, source_lang, target_lang)` that dispatches to Google now and can later dispatch to alternatives.
 - If no key is configured, skip translation gracefully and log.


### 8) Replace Cloud Tasks

- Remove `google-cloud-tasks` and `/crawl/<uuid>` pattern. The GitHub Actions job loops through papers and invokes the same crawl logic inline.
- The `/crawl` HTTP endpoint can be replaced by a GitHub workflow_dispatch for manual triggers.


### 9) Python Dependencies Updates

- Switch to `psycopg2-binary` for CI portability.
- Lock newspaper dependencies in `requirements.txt` or reuse vendored `server/lib/newspaper`.
- Keep Flask only if you retain Flask locally for testing; Vercel APIs will be separate.

Proposed split requirements:
- `requirements.crawler.txt` (used by GitHub Actions): `psycopg2-binary`, `requests`, `lxml`, `beautifulsoup4`, etc.
- `requirements.local.txt` for local dev/testing.


### 10) Step-by-step Execution Plan

Phase 0: Prep
- Create Neon project and DB; capture `DATABASE_URL`.
- Create Vercel project.
- Set repo secrets in GitHub and Vercel (`DATABASE_URL`, translation key if used).

Phase 1: DB
- Apply schema to Neon (convert `initialize.py` into SQL or run it pointing to Neon).
- Seed `paper` and `category_set` using `newspaper_store.json` if needed.
  - Run locally: `python scripts/seed_papers.py` (use `--prune-missing` to remove stale categories; supports `--dry-run`).

Notes:
- Papers use a stable id derived from URL (`uuid = md5(url)`) so syncs are idempotent.
- Categories have a unique index `(paper_uuid, url)` to make upserts safe.

Phase 2: Frontend+API on Vercel
- Scaffold Vite app in `web/` and port UI/assets from `templates/` and `static/`.
- Implement `/api/query` and `/api/stats` as Vercel Functions (Node or Python) connecting to Neon.
- Choose single-project or monorepo setup per section 5 and configure Vercel accordingly.
- Deploy and validate map + queries.

Phase 3: Crawling via GitHub Actions
- Add `.github/workflows/crawl.yml` and `server/scripts/run_crawl.py`.
- Test workflow using `workflow_dispatch` on a branch.
- Verify data is written to Neon; confirm frontend shows results.

Phase 4: Translation (optional)
- Add translator provider abstraction and switch Google client usage to API key REST or client lib with API key.
- Add a `translate.yml` workflow scheduled less frequently.

Phase 5: Decommission GCP (progressively)
- Delete App Engine/Cloud Tasks/Cloud SQL proxy artifacts as their replacements go live; no formal rollback maintained.
- Update docs/README along the way.


### 11) Local Development & Debugging

- Prereqs: Node/npm, Vercel CLI, Neon `DATABASE_URL`.
- Environment: export `DATABASE_URL` in the same terminal you run the API, e.g. `export DATABASE_URL='postgres://...?...sslmode=require'`.
- API dev server (Vercel): run with inspector for debugging
  - `NODE_OPTIONS=--inspect=0 vercel dev`
  - VS Code: JavaScript Debug Terminal auto‑attaches; or add an Attach config (port shown in terminal) and set breakpoints in `api/query.js` or `api/stats.js`.
- Frontend dev (Vite): `cd web && npm run dev` (http://localhost:5173)
  - Vite dev proxy (`web/vite.config.js`) forwards `/api/*` to `http://localhost:3000` during dev.


### 12) Work Items (Checklist)

- [ ] Create Neon DB and set `DATABASE_URL` in Vercel and GitHub
- [x] Port schema to Neon and seed papers
- [x] Scaffold Vite app in `web/`; port UI and assets
- [x] Implement `/api/query` and `/api/stats` as Vercel Functions
- [x] Add Vite dev proxy and document local debugging with `vercel dev`
- [x] Add Neon schema (`sql/schema.sql`) and apply to Neon
- [x] Add idempotent JSON→DB sync script (`scripts/seed_papers.py`) and document usage
- [ ] Add translator provider abstraction and configure `TRANSLATE_PROVIDER`
- [ ] Store `GOOGLE_TRANSLATE_API_KEY` in GitHub and Vercel and wire usage
- [ ] Refactor `server/services/translate.py` to use provider abstraction
- [ ] Add GitHub Actions crawler workflow and script
- [ ] Migrate translation to API key or defer
- [ ] Remove Cloud Tasks, Cloud SQL proxy, and App Engine config
- [ ] Update documentation and remove unused deps


