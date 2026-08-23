from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app=FastAPI()

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

@app.get("/",response_class=HTMLResponse,include_in_schema=False)
def home():
    return f"<h1>{posts[0]['role']}</h1>"

@app.get("/api/posts")
def get_posts():
    return posts