# LeftoverChef

Plan meals from what you already have. Enter ingredients with expiry dates, get ranked recipes, export a shopping list, and generate quick ideas locally in the browser.

<!--
Sections: Quickstart · Supabase · AI (optional) · Shopping list · Offline · Times · Dev
-->

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export SESSION_SECRET='dev-secret'
uvicorn app.main:app --reload
Open http://127.0.0.1:8000
```

## Supabase
Run schema + RLS once in Supabase SQL Editor (see /docs/schema.sql or project notes).

Set env:
```bash
export SUPABASE_URL='https://<project>.supabase.co'
export SUPABASE_ANON_KEY='<anon>'
Optional local seed (do not use in production):
```

```bash
export SUPABASE_SERVICE_ROLE_KEY='<service_role>'
export ALLOW_SEED=true
curl -X POST http://127.0.0.1:8000/admin/seed
export ALLOW_SEED=false
```


### AI (optional)
Three modes:
- Local Ideas (default, runs in the browser, no keys)
- Browser AI (WebGPU, optional)
- Server API (disabled by default; can be wired later)

No configuration required for Local Ideas.

### Shopping list
On a recipe page use Download .txt or Download .pdf.
List = recipe ingredients minus valid items you already have.

### Offline
Without Supabase env the app runs on built-in recipes and shows an offline banner.


## Dev
/app        FastAPI app, templates and static assets
/api        Vercel functions (Python entry + Node utilities)
vercel.json Routing and function runtimes (Python 3.11, Node 20)
