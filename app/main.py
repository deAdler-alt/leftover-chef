from datetime import date
from typing import List, Optional, Dict, Any
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

def fallback_suggest(ingredients: List[str]) -> List[Dict[str, Any]]:
    s = set(ingredients)
    out = []
    if {"egg", "eggs"} & s:
        out.append({"id":"fallback-omelette","title":"Simple Omelette","directions":"Beat eggs with salt and pepper, cook in a pan; optionally add chopped veggies or cheese.","score":0.6,"minutes":10,"tags":["breakfast","quick"]})
    if "tomato" in s or "tomatoes" in s:
        out.append({"id":"fallback-shakshuka","title":"Tomato & Egg Shakshuka","directions":"Sauté onion and garlic, add tomatoes and spices, simmer, crack eggs and cook until set.","score":0.55,"minutes":25,"tags":["eggs","tomato"]})
    if "rice" in s:
        out.append({"id":"fallback-fried-rice","title":"Veggie Fried Rice","directions":"Cook or use day-old rice. Stir-fry veggies, add rice and soy sauce; push aside and scramble an egg; mix.","score":0.5,"minutes":20,"tags":["rice"]})
    if "bread" in s and ("tomato" in s or "tomatoes" in s):
        out.append({"id":"fallback-panzanella","title":"Panzanella Salad","directions":"Toast stale bread, toss with tomatoes, cucumber, onion, olive oil, vinegar, and herbs.","score":0.45,"minutes":15,"tags":["salad","zero-waste"]})
    if "garlic" in s and "pasta" in s:
        out.append({"id":"fallback-aglio-olio","title":"Garlic Olive Oil Pasta (Aglio e Olio)","directions":"Cook pasta. Sauté sliced garlic in oil, add chili flakes, toss pasta and finish with parsley.","score":0.4,"minutes":15,"tags":["pasta"]})
    if not out and s:
        out.append({"id":"fallback-salad","title":"Zero-waste Salad","directions":"Chop available vegetables, add olive oil or vinegar, salt, pepper, and herbs.","score":0.3,"minutes":10,"tags":["salad"]})
    return out[:5]

def score_recipes(ingredients: List[str]) -> List[Dict[str, Any]]:
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
        out = []
        for rec in recs:
            c = counts.get(rec["id"], {"match": 0, "total": 1})
            base = c["match"] / max(c["total"], 1)
            ease = 1.0 / max(c["total"], 1)
            score = float(base + 0.15 * ease)
            out.append({"id":rec["id"],"title":rec["title"],"directions":rec["directions"],"minutes":rec.get("minutes"),"tags":rec.get("tags",[]),"score":score})
        out.sort(key=lambda x: x["score"], reverse=True)
        if not out:
            return fallback_suggest(ingredients)
        return out[:5]
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
    suggestions = [r["title"] for r in recipe_scores] or (["Add ingredients to get suggestions."] if not names else [])
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "suggestions": suggestions, "ingredients_list": pairs, "recipes": recipe_scores},
    )

@app.get("/recipe/{rid}", response_class=HTMLResponse)
def recipe_detail(request: Request, rid: str):
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_ANON_KEY", "")
    if not url or not key or rid.startswith("fallback-"):
        recipe = {"title":"Recipe", "minutes":None, "tags":[], "directions":"No extra details available."}
        return templates.TemplateResponse("recipe.html", {"request": request, "recipe": recipe, "ingredients": [], "steps": []})
    try:
        sb = get_client()
        r = sb.table("recipes").select("id,title,directions,minutes,tags").eq("id", rid).single().execute().data
        ing = sb.table("recipe_ingredients").select("name").eq("recipe_id", rid).execute().data
        directions = (r.get("directions") or "").strip()
        parts = [p.strip() for p in directions.replace("\r\n","\n").split("\n") if p.strip()]
        if len(parts) <= 1:
            tmp = [x.strip() for x in directions.split(".") if x.strip()]
            parts = tmp
        return templates.TemplateResponse("recipe.html", {"request": request, "recipe": r, "ingredients": ing, "steps": parts})
    except Exception:
        recipe = {"title":"Recipe", "minutes":None, "tags":[], "directions":"No extra details available."}
        return templates.TemplateResponse("recipe.html", {"request": request, "recipe": recipe, "ingredients": [], "steps": []})

@app.post("/row", response_class=HTMLResponse)
def row(request: Request):
    return templates.TemplateResponse("partials/ingredient_row.html", {"request": request})
