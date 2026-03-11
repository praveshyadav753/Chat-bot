from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.routes.auth import auth_route
from app.api.routes.chat import chat_router
from app.auth.utility import  get_current_user, get_token
from app.models import document, user
from app.api.routes import documents, update__event
from app.models.connection import engine, init_db,get_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("App is starting...")
    await init_db()
    yield
    await engine.dispose()
    print("App is shutting down...")


app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")
templates.env.auto_reload = True
templates.env.bytecode_cache = None


# ── Global 401 handler: redirect browser requests to /login ──────────────────
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        # Check if it's a browser request (accepts HTML) vs API request
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            return RedirectResponse(url="/login", status_code=303)

    # For all other errors (and non-browser 401s), return default JSON
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=dict(exc.headers) if exc.headers else {},
    )


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(chat_router)
app.include_router(auth_route)
app.include_router(documents.router)
app.include_router(update__event.router)


# ── Page routes ───────────────────────────────────────────────────────────────
@app.get("/")
async def main(request: Request):
    # Redirect to chat if already logged in, else to login
    token = request.cookies.get("access_token")
    if token:
        return RedirectResponse(url="/api/chat", status_code=303)
    return RedirectResponse(url="/login", status_code=303)


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {
        "request": request,
        "is_authenticated": False,
    })


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db=Depends(get_db)):
    try:
        # Reuse existing utilities — just call them directly with the args they need
        token = await get_token(request=request, bearer_token=None)
        user  = await get_current_user(token=token, db=db)
        if user and user.is_active:
            return RedirectResponse(url="/api/chat", status_code=303)
    except HTTPException:
        # Token missing, expired, or invalid — clear cookie, show login
        response = templates.TemplateResponse("login.html", {
            "request": request,
            "is_authenticated": False,
        })
        response.delete_cookie("access_token")
        return response

    return templates.TemplateResponse("login.html", {
        "request": request,
        "is_authenticated": False,
    })

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("access_token")
    return response