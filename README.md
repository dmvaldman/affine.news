# Affine News (Vercel + Neon)

Modernized stack:
- Frontend: Vanilla SPA (index.html, js/app.js, css/app.css) in `web/`
- APIs: Vercel Functions (`web/api/*.js`)
- DB: Neon Postgres


## Prerequisites
- Node 18+
- Vercel CLI (`npm i -g vercel`)
- Python 3.9+ (for data seeding)
- psql (optional; or use Neon SQL editor)


## Environment
Set your Neon pooled connection string with SSL:

```bash
export DATABASE_URL='postgres://USER:PASSWORD@HOST/DB?sslmode=require'
```

Tip: keep this only in your shell or a local, uncommitted `.env`.


## Database
Create tables on Neon (once):

```bash
psql "$DATABASE_URL" -f sql/schema.sql
```

Seed or sync newspapers and categories from `crawler/db/newspaper_store.json`:

```bash
# Install Python dependencies first: pip install -r crawler/requirements.crawler.txt
python scripts/seed_papers.py            # upsert only
python scripts/seed_papers.py --prune-missing   # remove categories not in JSON
python scripts/seed_papers.py --dry-run         # preview changes
```

Updating sources:
- Edit `crawler/db/newspaper_store.json`
- Re-run one of the commands above to sync changes to the DB


## Running the Crawler Locally
You can run the newspaper crawler on your local machine to populate the database.

1.  **Install Dependencies**:
    ```bash
    pip install -r crawler/requirements.crawler.txt
    ```

2.  **Set Environment**:
    Make sure your `DATABASE_URL` is set in the terminal.
    ```bash
    export DATABASE_URL='postgres://...'
    ```

3.  **Run the Script**:
    ```bash
    # Crawl with default of 30 articles per paper
    python -m crawler.scripts.run_crawl

    # Crawl a smaller number of articles
    python -m crawler.scripts.run_crawl --max-articles 5
    ```

## Running Translation Locally
To translate untranslated articles, you can run the translation script locally.

1.  **Set Environment**:
    Make sure your `DATABASE_URL`, `GOOGLE_PROJECT_ID`, and `GOOGLE_TRANSLATE_API_KEY` are set.
    ```bash
    export DATABASE_URL='postgres://...'
    export GOOGLE_PROJECT_ID='your-gcp-project-id'
    export GOOGLE_TRANSLATE_API_KEY='your-api-key'
    ```

2.  **Run the Script**:
    ```bash
    python -m crawler.scripts.run_translate
    ```


## Quick Start (web-only SPA + Vercel Functions)

Local (from `web/`):

```bash
cd web
# 1) Set env for local dev (not committed)
echo "DATABASE_URL=postgres://USER:PASSWORD@HOST/DB?sslmode=require" > .env.local

# 2) Link once (select your existing Vercel project)
vercel link

# 3) Run dev server (serves SPA at / and functions at /api/*)
vercel dev  # http://localhost:3000
```

Deploy:
- Vercel Dashboard → Project → Settings → Root Directory: `web`
- Add Environment Variable: `DATABASE_URL`
- Push to your main branch (or click Deploy)

Routing (web/vercel.json):
- `/api/*` → serverless functions in `web/api`
- `/css/*` and `/js/*` → static assets
- `/(.*)` → `index.html` (SPA fallback)

Troubleshooting:
- 404 at `/`: ensure `web/vercel.json` has the catch‑all route to `/index.html`
- 404 on `/api/*`: confirm files in `web/api` and retry `vercel dev` from `web/`
- Hanging requests: ensure `web/.env.local` contains a valid `DATABASE_URL`
