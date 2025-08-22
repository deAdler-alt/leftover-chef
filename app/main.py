from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import List, Optional

app = FastAPI(title="LeftoverChef")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


def simple_suggest(ingredients: List[str]) -> List[str]:
    normalized = {i.strip().lower() for i in ingredients if i and i.strip()}
    suggestions: List[str] = []

    if {"egg", "eggs"} & normalized:
        suggestions.append("Leftover omelette (eggs + veggies).")
    if "tomato" in normalized or "tomatoes" in normalized:
        suggestions.append("Shakshuka with tomatoes and eggs.")
    if "rice" in normalized:
        suggestions.append("Fried rice with mixed veggies and soy sauce.")
    if not suggestions and normalized:
        suggestions.append("Zero-waste salad: chop everything, add olive oil and herbs.")
    if not normalized:
        suggestions.append("Add ingredients to get suggestions.")
    return suggestions


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "suggestions": [], "ingredients_list": []},
    )


@app.post("/plan", response_class=HTMLResponse)
def plan(
    request: Request,
    ingredient: Optional[List[str]] = Form(default=None),
    expiry: Optional[List[str]] = Form(default=None),
):
    ingredients = ingredient or []
    suggestions = simple_suggest(ingredients)
    pairs = list(zip(ingredients, (expiry or [""] * len(ingredients))))
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "suggestions": suggestions, "ingredients_list": pairs},
    )


@app.post("/row", response_class=HTMLResponse)
def row(request: Request):
    return templates.TemplateResponse("partials/ingredient_row.html", {"request": request})

