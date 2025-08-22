from datetime import date, datetime
from typing import List, Optional, Dict, Any, Tuple
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from uuid import uuid4
import os

from .supabase_client import get_client, get_admin_client

app = FastAPI(title="LeftoverChef")
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET", "dev-secret"))
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

INIT_DONE = False

def parse_iso(s: str) -> Optional[date]:
    try:
        return date.fromisoformat(s)
    except Exception:
        return None

def normalize(items: List[str]) -> List[str]:
    out = []
    for i in items or []:
        s = (i or "").strip().lower()
        if s:
            out.append(s)
    return out

def weight_for_expiry(d: Optional[date]) -> float:
    if not d:
        return 1.0
    today = date.today()
    delta = (d - today).days
    if delta <= 0:
        return 1.6
    if delta >= 30:
        return 1.0
    return 1.0 + 0.6 * (30 - delta) / 30.0

def build_use_first(pairs: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
    items = []
    for n, e in pairs or []:
        ed = parse_iso(e) if e else None
        days = None
        if ed:
            days = (ed - date.today()).days
        items.append({"name": n, "expiry": e or "", "days": days})
    def sort_key(x):
        if x["days"] is None:
            return (1, 10**9, x["name"])
        return (0, x["days"], x["name"])
    items.sort(key=sort_key)
    return items

def fallback_suggest(ingredients: List[str]) -> List[Dict[str, Any]]:
    s = set(ingredients)
    out = []
    if {"egg", "eggs"} & s:
        out.append({"id":"fallback-omelette","title":"Simple Omelette","directions":"Whisk 3 eggs with a pinch of salt and pepper. Heat a non-stick pan with a little butter. Pour in the eggs and cook on medium heat, lifting the edges so the uncooked egg flows underneath. Add chopped herbs, cheese or leftover veggies. Fold and serve warm.","score":0.62,"minutes":10,"tags":["breakfast","quick"]})
    if "tomato" in s or "tomatoes" in s:
        out.append({"id":"fallback-shakshuka","title":"Tomato & Egg Shakshuka","directions":"Warm olive oil in a skillet. Soften sliced onion and garlic with a pinch of chili. Add crushed tomatoes, salt and a pinch of sugar; simmer until thick. Make small wells and crack in eggs. Cover and cook until whites set and yolks are still soft. Finish with parsley.","score":0.58,"minutes":25,"tags":["eggs","tomato"]})
    if "rice" in s:
        out.append({"id":"fallback-fried-rice","title":"Veggie Fried Rice","directions":"Heat oil in a wok. Add diced carrot and peas; stir-fry 2–3 min. Add cold cooked rice, soy sauce and a splash of sesame oil; toss to coat. Push rice aside, scramble an egg, then mix through. Finish with sliced spring onion.","score":0.54,"minutes":20,"tags":["rice"]})
    if "bread" in s and ("tomato" in s or "tomatoes" in s):
        out.append({"id":"fallback-panzanella","title":"Panzanella Salad","directions":"Toast torn stale bread in the oven until crisp. Combine chopped tomatoes, cucumber and red onion with olive oil and red wine vinegar. Toss with bread so it soaks up juices. Season and stand 10 min. Scatter with basil.","score":0.49,"minutes":15,"tags":["salad","zero-waste"]})
    if "garlic" in s and "pasta" in s:
        out.append({"id":"fallback-aglio-olio","title":"Garlic Olive Oil Pasta (Aglio e Olio)","directions":"Cook spaghetti in salted water. Gently sizzle sliced garlic in olive oil until pale gold; add chili flakes. Toss pasta with some cooking water to emulsify. Finish with parsley and black pepper.","score":0.45,"minutes":15,"tags":["pasta"]})
    if not out and s:
        out.append({"id":"fallback-salad","title":"Zero-waste Salad","directions":"Combine chopped vegetables and herbs. Add olive oil, lemon, salt and pepper. Toss and serve with toasted seeds or croutons.","score":0.35,"minutes":10,"tags":["salad"]})
    return out[:5]

def score_with_db(pairs: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_ANON_KEY", "")
    if not url or not key:
        return []
    sb = get_client()
    ri = sb.table("recipe_ingredients").select("recipe_id,name").execute()
    if not ri.data:
        return []
    wmap = {}
    names = []
    for n, e in pairs or []:
        ed = parse_iso(e) if e else None
        w = weight_for_expiry(ed)
        nn = (n or "").strip().lower()
        if nn:
            names.append(nn)
            wmap[nn] = max(wmap.get(nn, 1.0), w)
    wanted = set(names)
    counts = {}
    for row in ri.data:
        rid = row.get("recipe_id")
        name = (row.get("name") or "").strip().lower()
        if not rid or not name:
            continue
        c = counts.setdefault(rid, {"match_w": 0.0, "total": 0})
        c["total"] += 1
        if name in wanted:
            c["match_w"] += wmap.get(name, 1.0)
    if not counts:
        return []
    ids = list(counts.keys())
    recs = sb.table("recipes").select("id,title,directions,minutes,tags").in_("id", ids).execute().data
    out = []
    for rec in recs:
        c = counts.get(rec["id"], {"match_w": 0.0, "total": 1})
        base = c["match_w"] / max(c["total"], 1)
        ease = 1.0 / max(c["total"], 1)
        score = float(base + 0.12 * ease)
        out.append({"id":rec["id"],"title":rec["title"],"directions":rec["directions"],"minutes":rec.get("minutes"),"tags":rec.get("tags",[]),"score":score})
    out.sort(key=lambda x: x["score"], reverse=True)
    return out[:5]

def score_recipes(pairs: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_ANON_KEY", "")
    if not url or not key:
        return fallback_suggest([n for n, _ in pairs or []])
    try:
        out = score_with_db(pairs)
        if not out:
            return fallback_suggest([n for n, _ in pairs or []])
        return out
    except Exception:
        return fallback_suggest([n for n, _ in pairs or []])

def set_form_session(request: Request, pairs: List[Tuple[str, str]]) -> None:
    request.session["pairs"] = pairs

def get_form_session(request: Request) -> List[Tuple[str, str]]:
    data = request.session.get("pairs") or []
    if not isinstance(data, list):
        return []
    out = []
    for item in data:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            out.append((str(item[0]), str(item[1])))
    return out

def reset_and_seed_supabase() -> None:
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        return
    sb = get_admin_client()
    try:
        sb.table("recipe_ingredients").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    except Exception:
        pass
    try:
        sb.table("ingredients_submissions").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    except Exception:
        pass
    try:
        sb.table("recipes").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    except Exception:
        pass
    recipes = [
        {"title":"Simple Omelette","minutes":10,"directions":"Crack eggs into a bowl and whisk with salt and pepper.\nHeat a non-stick pan with butter over medium heat.\nPour in eggs and pull set edges toward the center.\nAdd herbs, cheese or leftover vegetables.\nFold and slide onto a plate.","tags":["breakfast","quick"]},
        {"title":"Tomato & Egg Shakshuka","minutes":25,"directions":"Warm olive oil in a skillet and add sliced onion.\nStir in garlic and chili and cook until fragrant.\nAdd crushed tomatoes, salt and a pinch of sugar; simmer to thicken.\nMake wells and crack in eggs.\nCover and cook until whites set; garnish with parsley.","tags":["eggs","tomato","skillet"]},
        {"title":"Veggie Fried Rice","minutes":20,"directions":"Heat oil in a wok and add diced carrot and peas.\nAdd cold rice and toss with soy sauce.\nPush rice to the side; scramble an egg.\nCombine and stir-fry until steamy.\nFinish with spring onion and a splash of sesame oil.","tags":["rice","stirfry"]},
        {"title":"Panzanella Salad","minutes":15,"directions":"Toast torn stale bread until crisp.\nCombine tomatoes, cucumber, and red onion.\nDress with olive oil and red wine vinegar.\nToss with bread to soak up juices.\nSeason and rest 10 minutes; add basil.","tags":["salad","bread","tomato","zero-waste"]},
        {"title":"Garlic Olive Oil Pasta (Aglio e Olio)","minutes":15,"directions":"Cook spaghetti in salted water.\nGently sizzle sliced garlic in olive oil.\nAdd chili flakes and a ladle of pasta water.\nToss pasta to emulsify and coat.\nFinish with parsley and black pepper.","tags":["pasta","garlic","quick"]}
    ]
    sb.table("recipes").insert(recipes).execute()
    rows = sb.table("recipes").select("id,title").in_("title", [r["title"] for r in recipes]).execute().data
    by_title = {r["title"]: r["id"] for r in rows}
    ing = {
        "Simple Omelette": ["egg","eggs","cheese","bell pepper","onion"],
        "Tomato & Egg Shakshuka": ["tomato","tomatoes","egg","eggs","onion","garlic"],
        "Veggie Fried Rice": ["rice","egg","eggs","carrot","peas","soy sauce","spring onion"],
        "Panzanella Salad": ["bread","tomato","tomatoes","cucumber","red onion","olive oil","vinegar","basil"],
        "Garlic Olive Oil Pasta (Aglio e Olio)": ["pasta","garlic","olive oil","chili flakes","parsley"]
    }
    links = []
    for t, names in ing.items():
        rid = by_title.get(t)
        if not rid:
            continue
        for n in names:
            links.append({"recipe_id": rid, "name": n})
    if links:
        sb.table("recipe_ingredients").insert(links).execute()

def maybe_init():
    global INIT_DONE
    if INIT_DONE:
        return
    if os.getenv("RESET_ON_FIRST_HIT", "false").lower() == "true":
        reset_and_seed_supabase()
    INIT_DONE = True

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    maybe_init()
    pairs = get_form_session(request)
    use_first = build_use_first(pairs)
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "suggestions": [], "ingredients_list": pairs, "recipes": [], "use_first": use_first},
    )

@app.post("/plan", response_class=HTMLResponse)
def plan(
    request: Request,
    ingredient: Optional[List[str]] = Form(default=None),
    expiry: Optional[List[str]] = Form(default=None),
):
    names = normalize(ingredient)
    pairs = list(zip(names, (expiry or [""] * len(names))))
    set_form_session(request, pairs)
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_ANON_KEY", "")
    if names and url and key:
        try:
            sb = get_client()
            batch_id = str(uuid4())
            rows = []
            for n, e in pairs:
                ed = parse_iso(e) if e else None
                rows.append({"batch_id": batch_id, "name": n, "expiry": ed})
            sb.table("ingredients_submissions").insert(rows).execute()
        except Exception:
            pass
    recipe_scores = score_recipes(pairs)
    suggestions = [r["title"] for r in recipe_scores] or (["Add ingredients to get suggestions."] if not names else [])
    use_first = build_use_first(pairs)
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "suggestions": suggestions, "ingredients_list": pairs, "recipes": recipe_scores, "use_first": use_first},
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
