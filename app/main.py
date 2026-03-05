from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.routes.auth import auth_route
from app.api.routes.chat import chat_router
from app.models import document, user
from app.models.connection import engine, get_db, init_db


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
# ------------------------------------------------------------------------
app.include_router(chat_router)
app.include_router(auth_route)

# ------------------------------------------------------------------------


@app.get("/")
async def main(request: Request, response_class: HTMLResponse):
    # return templates.TemplateResponse("cha.html", {"request": request})
    return RedirectResponse(
        url="/api/chat",
        status_code=303,
    )


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})
