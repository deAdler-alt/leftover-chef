from datetime import date
from typing import List, Optional, Tuple
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from uuid import uuid4
import os

from .supabase_client import get_client

app = FastAPI(title="LeftoverChef")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

def normalize(items: List[str]) -> List[str]:
    out = []
    for i in items or []:
        s = (i or "").strip().lower()
        if s:
            out.append(s)
    return out

def fallback_suggest(ingredients: List[str]) -> List[Tuple[str, str, float]]:
    s = set(ingredients)
    out = []
    if {"egg", "eggs"} & s:
        out.append(("Simple Omelette", "Beat eggs with salt and pepper, cook in a pan; optionally add chopped veggies or cheese.", 0.6))
    if "tomato" in s or "tomatoes" in s:
        out.append(("Tomato & Egg Shakshuka", "Sauté onion and garlic, add tomatoes and spices, simmer, crack eggs and cook until set.", 0.55))
    if "rice" in s:
        out.append(("Veggie Fried Rice", "Cook or use day-old rice. Stir-fry veggies, add rice and soy sauce; push aside and scramble an egg; mix.", 0.5))
    if "bread" in s and ("tomato" in s or "tomatoes" in s):
        out.append(("Panzanella Salad", "Toast stale bread, toss with tomatoes, cucumber, onion, olive oil, vinegar, and herbs.", 0.45))
    if "garlic" in s and "pasta" in s:
        out.append(("Garlic Olive Oil Pasta (Aglio e Olio)", "Cook pasta. Sauté sliced garlic in oil, add chili flakes, toss pasta and finish with parsley.", 0.4))
    if not out and s:
        out.append(("Zero-waste Salad", "Chop available vegetables, add olive oil, lemon or vinegar, salt, pepper, and herbs.", 0.3))
    return out[:5]

def score_recipes(ingredients: List[str]) -> List[Tuple[str, str, float]]:
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_ANON_KEY", "")
    if not url or not key:
        return fallback_suggest(ingredients)
    try:
        sb = get_client()
        ri = sb.table("recipe_ingredients").select("recipe_id,name").execute()
        if not ri.data:
            return fallback_suggest(ingredients)
        wanted = set(ingredients)
        counts = {}
        for row in ri.data:
            rid = row.get("recipe_id")
            name = (row.get("name") or "").strip().lower()
            if not rid or not name:
                continue
            counts.setdefault(rid, {"match": 0, "total": 0})
            counts[rid]["total"] += 1
            if name in wanted:
                counts[rid]["match"] += 1
        if not counts:
            return fallback_suggest(ingredients)
        ids = list(counts.keys())
        recs = sb.table("recipes").select("id,title,directions,minutes,tags").in_("id", ids).execute().data
        scored = []
        for rec in recs:
            c = counts.get(rec["id"], {"match": 0, "total": 1})
            base = c["match"] / max(c["total"], 1)
            ease = 1.0 / max(c["total"], 1)
            scored.append((rec["title"], rec["directions"], float(base + 0.15 * ease)))
        scored.sort(key=lambda x: x[2], reverse=True)
        if not scored:
            return fallback_suggest(ingredients)
        return scored[:5]
    except Exception:
        return fallback_suggest(ingredients)

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "suggestions": [], "ingredients_list": [], "recipes": []},
    )

@app.post("/plan", response_class=HTMLResponse)
def plan(
    request: Request,
    ingredient: Optional[List[str]] = Form(default=None),
    expiry: Optional[List[str]] = Form(default=None),
):
    names = normalize(ingredient)
    pairs = list(zip(names, (expiry or [""] * len(names))))
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_ANON_KEY", "")
    if names and url and key:
        try:
            sb = get_client()
            batch_id = str(uuid4())
            rows = []
            for n, e in pairs:
                ed = None
                if e:
                    try:
                        ed = date.fromisoformat(e)
                    except Exception:
                        ed = None
                rows.append({"batch_id": batch_id, "name": n, "expiry": ed})
            sb.table("ingredients_submissions").insert(rows).execute()
        except Exception:
            pass
    recipe_scores = score_recipes(names)
    suggestions = [t for t, _d, _s in recipe_scores] or (["Add ingredients to get suggestions."] if not names else [])
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "suggestions": suggestions, "ingredients_list": pairs, "recipes": recipe_scores},
    )

@app.post("/row", response_class=HTMLResponse)
def row(request: Request):
    return templates.TemplateResponse("partials/ingredient_row.html", {"request": request})
