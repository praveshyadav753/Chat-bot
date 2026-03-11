from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy import update

from app.models.connection import AsyncSession, get_db
from app.auth.auth_schema import Token, User, user_form, UserCreate
from app.models.user import User as db_User
from app.auth.utility import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    authenticate_user,
    create_access_token,
    get_current_active_user,
    get_password_hash,
)
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from .service import register_user_service

auth_route = APIRouter(prefix="/auth", tags=["Authentication"])

templates = Jinja2Templates(directory="app/templates")
templates.env.auto_reload = True
templates.env.cache = {}


# ── JSON API endpoints ────────────────────────────────────────────────────────


@auth_route.post("/register")
async def register_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    user = await register_user_service(user, db)
    return user


@auth_route.post("/token")
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: AsyncSession = Depends(get_db),
) -> Token:
    user = await authenticate_user(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return Token(access_token=access_token, token_type="bearer")


# ── Web (HTML) endpoints ──────────────────────────────────────────────────────


@auth_route.post("/web/register", response_class=HTMLResponse)
async def register_user_web(
    request: Request,
    user: UserCreate = Depends(user_form),
    db: AsyncSession = Depends(get_db),
):
    try:
        await register_user_service(user, db)
        return RedirectResponse(url="/login", status_code=303)
    except Exception as e:
        print("Register error:", e)
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "is_authenticated": False,
                "error": "Registration failed. Please try again.",
            },
        )


@auth_route.post("/web/token", response_class=HTMLResponse)
async def login_web(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    # ── Authenticate ─────────────────────────────────────────────────────────
    try:
        user = await authenticate_user(username, password, db)
    except Exception as e:
        print("Auth error:", e)
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "is_authenticated": False,
                "error": "Internal server error. Please try again.",
            },
        )

    if not user:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "is_authenticated": False,
                "error": "Invalid username or password.",
            },
        )

    # ── Update last login ─────────────────────────────────────────────────────
    try:
        await db.execute(
            update(db_User)
            .where(db_User.username == username)
            .values(last_login_at=datetime.now(timezone.utc))
        )
        await db.commit()
    except Exception as e:
        print("DB update error (last_login_at):", e)

    # ── Issue token & redirect ────────────────────────────────────────────────
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    response = RedirectResponse(url="/api/chat", status_code=303)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,
        samesite="lax",
    )
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


# ── API: current user ─────────────────────────────────────────────────────────


@auth_route.get("/users/me/")
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    return current_user


@auth_route.get("/users/me/items/")
async def read_own_items(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    return [{"item_id": "Foo", "owner": current_user.username}]
