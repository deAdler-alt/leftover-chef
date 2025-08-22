from datetime import date
from typing import List, Optional, Dict, Any, Tuple
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from uuid import uuid4
import io
import os

from .supabase_client import get_client, get_admin_client

app = FastAPI(title="LeftoverChef")
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET", "dev-secret"))
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
BOOT_ID = os.getenv("SESSION_BOOT_ID") or str(uuid4())

FALLBACK_MAP = {
    "fallback-omelette": {"id":"fallback-omelette","title":"Simple Omelette","minutes":10,"directions":"Whisk 3 eggs with salt and pepper. Heat a non-stick pan with a little butter. Pour in the eggs and cook on medium heat, lifting the edges so the uncooked egg flows underneath. Add chopped herbs, cheese or leftover veggies. Fold and serve warm.","tags":["breakfast","quick"],"keys":["egg","eggs","cheese","bell pepper","onion"]},
    "fallback-shakshuka": {"id":"fallback-shakshuka","title":"Tomato & Egg Shakshuka","minutes":25,"directions":"Warm olive oil in a skillet. Soften sliced onion and garlic with a pinch of chili. Add crushed tomatoes, salt and a pinch of sugar; simmer until thick. Make small wells and crack in eggs. Cover and cook until whites set and yolks are still soft. Finish with parsley.","tags":["eggs","tomato"],"keys":["tomato","tomatoes","egg","eggs","onion","garlic"]},
    "fallback-fried-rice": {"id":"fallback-fried-rice","title":"Veggie Fried Rice","minutes":20,"directions":"Heat oil in a wok. Add diced carrot and peas; stir-fry 2–3 min. Add cold cooked rice, soy sauce and a splash of sesame oil; toss to coat. Push rice aside, scramble an egg, then mix through. Finish with sliced spring onion.","tags":["rice","stirfry"],"keys":["rice","egg","eggs","carrot","peas","soy sauce","spring onion"]},
    "fallback-panzanella": {"id":"fallback-panzanella","title":"Panzanella Salad","minutes":15,"directions":"Toast torn stale bread until crisp. Combine chopped tomatoes, cucumber and red onion with olive oil and red wine vinegar. Toss with bread so it soaks up juices. Season and stand 10 min. Scatter with basil.","tags":["salad","zero-waste"],"keys":["bread","tomato","tomatoes","cucumber","red onion","olive oil","vinegar","basil"]},
    "fallback-aglio-olio": {"id":"fallback-aglio-olio","title":"Garlic Olive Oil Pasta (Aglio e Olio)","minutes":15,"directions":"Cook spaghetti in salted water. Gently sizzle sliced garlic in olive oil until pale gold; add chili flakes. Toss pasta with some cooking water to emulsify. Finish with parsley and black pepper.","tags":["pasta"],"keys":["pasta","garlic","olive oil","chili flakes","parsley"]},
    "fallback-salad": {"id":"fallback-salad","title":"Zero-waste Salad","minutes":10,"directions":"Combine chopped vegetables and herbs. Add olive oil, lemon, salt and pepper. Toss and serve with toasted seeds or croutons.","tags":["salad"],"keys":["lettuce","cucumber","tomato","pepper","onion","herbs"]}
}

def parse_iso(s: str):
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

def split_valid_outdated(pairs: List[Tuple[str, str]]):
    valid = []
    outdated = []
    today = date.today()
    for n, e in pairs or []:
        d = parse_iso(e) if e else None
        if d is not None and d < today:
            outdated.append((n, e))
        else:
            valid.append((n, e))
    return valid, outdated

def weight_for_expiry(d):
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
    for rid, r in FALLBACK_MAP.items():
        if s & set(r["keys"]):
            out.append({"id":rid,"title":r["title"],"directions":r["directions"],"minutes":r["minutes"],"tags":r["tags"],"score":0.5})
    if not out and s:
        r = FALLBACK_MAP["fallback-salad"]
        out.append({"id":r["id"],"title":r["title"],"directions":r["directions"],"minutes":r["minutes"],"tags":r["tags"],"score":0.35})
    return out[:5]

def score_with_db(valid_pairs: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
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
    for n, e in valid_pairs or []:
        ed = parse_iso(e) if e else None
        w = weight_for_expiry(ed)
        nn = (n or "").strip().lower()
        if nn:
            names.append(nn)
            wmap[nn] = max(wmap.get(nn, 1.0), w)
    wanted = set(names)
    if not wanted:
        return []
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

def score_recipes(pairs: List[Tuple[str, str]]):
    valid, outdated = split_valid_outdated(pairs)
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_ANON_KEY", "")
    if not url or not key:
        return fallback_suggest([n for n,_ in valid]), outdated
    try:
        out = score_with_db(valid)
        if not out:
            return fallback_suggest([n for n,_ in valid]), outdated
        return out, outdated
    except Exception:
        return fallback_suggest([n for n,_ in valid]), outdated

def set_form_session(request: Request, pairs: List[Tuple[str, str]]):
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

def reset_and_seed_supabase():
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        return
    try:
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
        recipes = []
        for k in ["fallback-omelette","fallback-shakshuka","fallback-fried-rice","fallback-panzanella","fallback-aglio-olio"]:
            r = FALLBACK_MAP[k]
            recipes.append({"title":r["title"],"minutes":r["minutes"],"directions":r["directions"],"tags":r["tags"]})
        sb.table("recipes").insert(recipes).execute()
        rows = sb.table("recipes").select("id,title").in_("title", [r["title"] for r in recipes]).execute().data
        by_title = {r["title"]: r["id"] for r in rows}
        links = []
        for k in ["fallback-omelette","fallback-shakshuka","fallback-fried-rice","fallback-panzanella","fallback-aglio-olio"]:
            r = FALLBACK_MAP[k]
            rid = by_title.get(r["title"])
            if not rid:
                continue
            for n in r["keys"]:
                links.append({"recipe_id": rid, "name": n})
        if links:
            sb.table("recipe_ingredients").insert(links).execute()
    except Exception:
        return

def ensure_boot(request: Request):
    if request.session.get("boot") != BOOT_ID:
        request.session.clear()
        request.session["boot"] = BOOT_ID

def log_event(name: str, extra: Dict[str, Any] = None):
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_ANON_KEY", "")
    if not url or not key:
        return
    try:
        sb = get_client()
        sb.table("events").insert({"type": name, "meta": extra or {}}).execute()
    except Exception:
        return

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    ensure_boot(request)
    pairs = get_form_session(request)
    valid, outdated = split_valid_outdated(pairs)
    use_first = build_use_first(pairs)
    today_iso = date.today().isoformat()
    offline = not (os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_ANON_KEY"))
    log_event("page_view", {})
    return templates.TemplateResponse("index.html", {"request": request, "suggestions": [], "ingredients_list": pairs, "recipes": [], "use_first": use_first, "outdated": outdated, "all_outdated": bool(pairs and not valid), "today": today_iso, "offline": offline})

@app.post("/plan", response_class=HTMLResponse)
def plan(request: Request, ingredient: Optional[List[str]] = Form(default=None), expiry: Optional[List[str]] = Form(default=None)):
    ensure_boot(request)
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
    recipe_scores, outdated = score_recipes(pairs)
    suggestions = [r["title"] for r in recipe_scores] if recipe_scores else []
    use_first = build_use_first(pairs)
    today_iso = date.today().isoformat()
    offline = not (os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_ANON_KEY"))
    log_event("plan_submit", {"count": len(pairs)})
    return templates.TemplateResponse("index.html", {"request": request, "suggestions": suggestions, "ingredients_list": pairs, "recipes": recipe_scores, "use_first": use_first, "outdated": outdated, "all_outdated": bool(pairs and not [p for p in pairs if p not in outdated]), "today": today_iso, "offline": offline})

@app.get("/recipe/{rid}", response_class=HTMLResponse)
def recipe_detail(request: Request, rid: str):
    ensure_boot(request)
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_ANON_KEY", "")
    log_event("view_recipe", {"rid": rid})
    if rid.startswith("fallback-") or not url or not key:
        r = FALLBACK_MAP.get(rid) or {"title":"Recipe","minutes":None,"tags":[],"directions":"No extra details available."}
        steps = [p.strip() for p in (r.get("directions","").replace("\r\n","\n").split("\n")) if p.strip()]
        return templates.TemplateResponse("recipe.html", {"request": request, "recipe": r, "ingredients": [{"name":k} for k in r.get("keys", [])], "steps": steps})
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
        r = {"title":"Recipe","minutes":None,"tags":[],"directions":"No extra details available."}
        return templates.TemplateResponse("recipe.html", {"request": request, "recipe": r, "ingredients": [], "steps": []})

@app.get("/recipe/{rid}/shopping")
def shopping_list(request: Request, rid: str, format: str = "txt"):
    ensure_boot(request)
    pairs = get_form_session(request)
    valid, _ = split_valid_outdated(pairs)
    have = set([n for n,_ in valid])
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_ANON_KEY", "")
    title = "Recipe"
    need = []
    if rid.startswith("fallback-") or not url or not key:
        r = FALLBACK_MAP.get(rid)
        if r:
            title = r["title"]
            need = sorted(list(set(r["keys"]) - have))
    else:
        try:
            sb = get_client()
            rec = sb.table("recipes").select("title").eq("id", rid).single().execute().data
            title = rec["title"]
            ing = sb.table("recipe_ingredients").select("name").eq("recipe_id", rid).execute().data
            keys = set([(i["name"] or "").strip().lower() for i in ing if i.get("name")])
            need = sorted(list(keys - have))
        except Exception:
            need = []
    log_event("download_shopping", {"rid": rid, "count": len(need)})
    if format == "pdf":
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
            buf = io.BytesIO()
            c = canvas.Canvas(buf, pagesize=letter)
            w, h = letter
            y = h - 72
            c.setFont("Helvetica-Bold", 16)
            c.drawString(72, y, f"Shopping list — {title}")
            y -= 24
            c.setFont("Helvetica", 12)
            if need:
                for item in need:
                    c.drawString(72, y, f"• {item}")
                    y -= 18
                    if y < 72:
                        c.showPage()
                        y = h - 72
            else:
                c.drawString(72, y, "No missing items.")
            c.showPage()
            c.save()
            buf.seek(0)
            return StreamingResponse(buf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="shopping_{rid}.pdf"'})
        except Exception:
            text = f"Shopping list — {title}\n" + ("\n".join(f"- {x}" for x in need) if need else "No missing items.")
            return PlainTextResponse(text, headers={"Content-Disposition": f'attachment; filename="shopping_{rid}.txt"'})
    text = f"Shopping list — {title}\n" + ("\n".join(f"- {x}" for x in need) if need else "No missing items.")
    return PlainTextResponse(text, headers={"Content-Disposition": f'attachment; filename="shopping_{rid}.txt"'})

@app.post("/row", response_class=HTMLResponse)
def row(request: Request):
    ensure_boot(request)
    today_iso = date.today().isoformat()
    return templates.TemplateResponse("partials/ingredient_row.html", {"request": request, "today": today_iso})

@app.post("/save")
def save(request: Request, ingredient: Optional[List[str]] = Form(default=None), expiry: Optional[List[str]] = Form(default=None)):
    ensure_boot(request)
    names = normalize(ingredient)
    pairs = list(zip(names, (expiry or [""] * len(names))))
    set_form_session(request, pairs)
    return JSONResponse({"ok": True})

@app.post("/admin/seed")
def admin_seed():
    reset_and_seed_supabase()
    return JSONResponse({"ok": True})
