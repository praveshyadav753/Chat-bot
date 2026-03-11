from fastapi import Request
from app.auth.utility import get_current_active_user
from app.models.connection import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends


async def get_template_context(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Injects base template context into every page route.
    Checks the access_token cookie and sets is_authenticated.
    """
    is_authenticated = False

    token = request.cookies.get("access_token")
    if token:
        try:
            # Reuse your existing get_current_active_user logic
            user = await get_current_active_user(token=token, db=db)
            if user and user.is_active:
                is_authenticated = True
        except Exception:
            # Invalid / expired token — treat as logged out
            is_authenticated = False

    return {
        "request": request,
        "is_authenticated": is_authenticated,
    }