from sqlalchemy import select
from app.models.user import User
from app.auth.utility import get_password_hash
from fastapi import HTTPException, status


async def register_user_service(user_data, db):
    # Check username
    result = await db.execute(
        select(User).where(User.username == user_data.username)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    # Check email
    result = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    fullname =user_data.full_name
    first_name=""
    last_name=""
    if  fullname :

        full_name = fullname.strip()
        parts = full_name.split()

        first_name = parts[0]
        last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

    new_user = User(
        username=user_data.username,
        email=user_data.email,
        first_name=first_name,
        last_name=last_name,
        hashed_password=get_password_hash(user_data.password),
       
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return new_user