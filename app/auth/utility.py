from datetime import datetime, timedelta, timezone
from typing import Annotated
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash
from sqlalchemy import select
from . import auth_schema
from app.models.connection import get_db
from app.models.connection import AsyncSession
from app.core.config import settings
from app.models.user import User
from fastapi.security.utils import get_authorization_scheme_param


SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES


password_hash = PasswordHash.recommended()


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token",auto_error=False)  #if not found then manual logic will be check for cookies

async def get_token(
    request: Request,
    bearer_token: str | None = Depends(oauth2_scheme),  # Swagger / API clients
) -> str:
    if bearer_token:
        return bearer_token

    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        scheme, param = get_authorization_scheme_param(cookie_token)
        if scheme.lower() == "bearer":
            return param
        return cookie_token  

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )

def verify_password(plain_password, hashed_password) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def get_password_hash(password):
    return password_hash.hash(password)


async def get_user(username: str, db: AsyncSession):
    result = await db.execute(select(User).where(User.username == username))
   
    user = result.scalar_one_or_none()
  
    if user:
        # return auth_schema.UserInDB(
        #     username=user.username,
        #     email=user.email,
        #     full_name = f"{(user.first_name or '')} {(user.last_name or '')}".strip(),      
        #     hashed_password=user.hashed_password,
        #     disabled=not user.is_active
        # )
        return user
    return None


async def authenticate_user(username: str, password: str, db: AsyncSession):
    user = await get_user(username, db)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(
    token: Annotated[str, Depends(get_token)], db: AsyncSession = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        print("username",username)
        if username is None:
            raise credentials_exception
        token_data = auth_schema.TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = await get_user(
        username=token_data.username,
        db=db,
    )
    if user is None:
        raise credentials_exception
    print("user:",user)
    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user