from datetime import date
from typing import List, Optional, Tuple
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from uuid import uuid4

from .supabase_client import get_client

app = FastAPI(title="LeftoverChef")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


def normalize(items: List[str]) -> List[str]:
    out = []
    for i in items:
        if not i:
            continue
        s = i.strip().lower()
        if s:
            out.append(s)
    return out


def score_recipes(ingredients: List[str]) -> List[Tuple[str, str, float]]:
    sb = get_client()
    # pobierz wszystkie powiązania składników z przepisami
    r = sb.table("recipe_ingredients").select("recipe_id,name").execute()
    if not r.data:
        return []

    wanted = set(ingredients)
    counts = {}
    for row in r.data:
        rid = row["recipe_id"]
        name = (row["name"] or "").strip().lower()
        if not name:
            continue
        counts.setdefault(rid, {"match": 0, "total": 0})
        counts[rid]["total"] += 1
        if name in wanted:
            counts[rid]["match"] += 1

    if not counts:
        return []

    # pobierz tytuły
    ids = list(counts.keys())
    recs = sb.table("recipes").select("id,title,directions,minutes,tags").in_("id", ids).execute().data

    scored = []
    for rec in recs:
        c = counts.get(rec["id"], {"match": 0, "total": 1})
        base = c["match"] / max(c["total"], 1)
        # delikatny boost za krótką listę składników (łatwiej ugotować)
        ease = 1.0 / max(c["total"], 1)
        score = base + 0.15 * ease
        scored.append((rec["title"], rec["directions"], float(score)))

    scored.sort(key=lambda x: x[2], reverse=True)
    return scored[:5]


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
    names = normalize(ingredient or [])
    pairs = list(zip(names, (expiry or [""] * len(names))))

    # zapis batcha w submissions (demo)
    if pairs:
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

    # dobór przepisów
    recipe_scores = score_recipes(names)
    suggestions = [f"{title}" for title, _dir, _s in recipe_scores]

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "suggestions": suggestions or ["Add ingredients to get suggestions."],
            "ingredients_list": pairs,
            "recipes": recipe_scores,
        },
    )

