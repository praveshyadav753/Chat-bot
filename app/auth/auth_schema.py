from fastapi import Form, HTTPException
from pydantic import BaseModel,EmailStr


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None


class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool = False  # ✅ add this



class UserInDB(User):
    hashed_password: str



class UserCreate(BaseModel):
    username: str
    email: EmailStr|None = None
    full_name: str | None = None
    password: str


class UserResponse(BaseModel):
    username: str
    email: EmailStr
    full_name: str | None = None
    

    class Config:
        from_attributes = True

def user_form(
    username: str = Form(...),
    email: EmailStr = Form(...),
    full_name: str = Form(None),
    password: str = Form(...),
    confirm_password: str = Form(...),
):
    if password != confirm_password:
        raise HTTPException(
            status_code=400,
            detail="Passwords do not match"
        )

    return UserCreate(
        username=username,
        email=email,
        full_name=full_name,
        password=password,
    )