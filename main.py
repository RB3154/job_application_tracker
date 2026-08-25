from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app=FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

posts:list[dict]=[
    {
        "id":1,
        "role":"SDE",
        "company":"Amazon",
        "location":"Bengaluru",
        "date_applied":"1-1-26",
        "status":"applied"
    },
    {
        "id":2,
        "role":"MLE",
        "company":"Google",
        "location":"Bengaluru",
        "date_applied":"2-1-26",
        "status":"applied"
    }
]

@app.get("/", include_in_schema=False, name="home")
@app.get("/posts", include_in_schema=False, name="posts")
def home(request: Request):
    return templates.TemplateResponse(
        request,
        "home.html",
        {"posts": posts, "Company": "Home"},
    )

@app.get("/api/posts")
def get_posts():
    return posts