from fastapi import FastAPI, Request, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

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

@app.get("/posts/{post_id}",include_in_schema=False)
def post_page(request:Request,post_id:int):
    for post in posts:
        if post.get("id")==post_id:
            role=post["role"][:20]
            return templates.TemplateResponse(
                request,
                "post.html",
                {
                    "post":post,
                    "role":role
                }
            )
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="post not found")

@app.get("/api/posts")
def get_posts():
    return posts

@app.get("/api/posts/{post_id}")
def get_post(post_id:int):
    for post in posts:
        if post.get("id")==post_id:
            return post
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="post not found")

@app.exception_handler(StarletteHTTPException)
def general_http_exception_handler(request:Request,exception:StarletteHTTPException):
    message=(
        exception.detail
        if exception.detail
        else "error occured.check request and try again"
    )

    if request.url.path.startswith("/api"):
        return JSONResponse(
            status_code=exception.status_code,
            content={"detail":message}
        )

    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "status_code":exception.status_code,
            "title":exception.status_code,
            "message":message
        },
        status_code=exception.status_code
    )

@app.exception_handler(RequestValidationError)
def validation_handler(request:Request,exception:RequestValidationError):
    if request.url.path.startswith("/api"):
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content={"detail":exception.errors()}
            ) 

    return templates.TemplateResponse(
            request,
            "error.html",
            {
                "status_code":status.HTTP_422_UNPROCESSABLE_CONTENT,
                "title":status.HTTP_422_UNPROCESSABLE_CONTENT,
                "message":"invalid request.check and try again"
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT
        )
    
