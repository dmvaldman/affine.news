# Affine News (Vercel + Neon)

Modernized stack:
- Frontend: Vite (web/)
- APIs: Vercel Functions (api/query.js, api/stats.js)
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

Seed or sync newspapers and categories from `server/db/newspaper_store.json`:

```bash
# Install Python dependencies first: pip install -r requirements.crawler.txt
python scripts/seed_papers.py            # upsert only
python scripts/seed_papers.py --prune-missing   # remove categories not in JSON
python scripts/seed_papers.py --dry-run         # preview changes
```

Updating sources:
- Edit `server/db/newspaper_store.json`
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


## Local Development (API & Frontend)
Run API (Vercel) and Frontend (Vite) side-by-side:

```bash
# Terminal 1 (root)
export DATABASE_URL='postgres://USER:PASSWORD@HOST/DB?sslmode=require'
vercel dev  # starts serverless APIs on http://localhost:3000

# Terminal 2 (web/)
cd web && npm install && npm run dev  # http://localhost:5173
```

The Vite dev server proxies `/api/*` to `http://localhost:3000`.


## Debugging APIs (VS Code)
Use the JavaScript Debug Terminal (auto-attach) or attach to a specific port.

Option A (auto-attach):
1. VS Code → Run and Debug → JavaScript Debug Terminal
2. In that terminal: `NODE_OPTIONS=--inspect=0 vercel dev`
3. Set breakpoints in `api/query.js` or `api/stats.js` and trigger requests

Option B (manual attach):
1. Start: `NODE_OPTIONS=--inspect=9230 vercel dev`
2. Add a VS Code launch config to attach to port `9230`


## Deployment
- Vercel Project → Settings → Environment Variables → add `DATABASE_URL`
- Deploy the repo; APIs and frontend will build on Vercel

Notes:
- Keep `DATABASE_URL` out of the Vite client (do not prefix with `VITE_`)
- Use Neon “pooled” connection string with `sslmode=require`
