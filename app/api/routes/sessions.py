# app/api/routes/sessions.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.utility import get_current_active_user
from app.models.connection import get_db
from app.models.chat import ChatSession
from app.models.messages import Message
from app.models.document import Document

sessions_router = APIRouter(prefix="/api/sessions", tags=["Sessions"])


# ── Create session 
@sessions_router.post("")
async def create_session(
    user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Called by the frontend when user clicks 'New Chat'.
    Creates the ChatSession row so documents and messages
    can reference it via FK.
    """
    from uuid import uuid4
    session_id = str(uuid4())

    session = ChatSession(
        id=session_id,
        user_id=user.id,
        title="New Chat",
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return {
        "session_id": session_id,
        "title":      session.title,
        "created_at": session.created_at.isoformat(),
    }


# ── List sessions for current user 
@sessions_router.get("")
async def list_sessions(
    user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns all sessions for the logged-in user, newest first.
    Used on page load to restore the sidebar session list.
    """
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == user.id)
        .order_by(ChatSession.created_at.desc())
    )
    sessions = result.scalars().all()

    return {
        "sessions": [
            {
                "session_id": s.id,
                "title":      s.title or "New Chat",
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            }
            for s in sessions
        ]
    }


# ── Update session title 
@sessions_router.patch("/{session_id}")
async def update_session(
    session_id: str,
    title: str,
    user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Called when user renames a session (double-click in sidebar).
    Also called automatically when first message is sent (auto-title).
    """
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.title = title[:100]   # cap at 100 chars
    await db.commit()
    return {"session_id": session_id, "title": session.title}


# ── Delete session 
@sessions_router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Deletes session + all its messages from the DB.
    LangGraph checkpointer data is NOT deleted (kept for audit/replay).
    Documents are unlinked (session_id set to NULL) not deleted —
    the user may want to re-attach them.
    """
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Delete messages
    await db.execute(
        delete(Message).where(Message.session_id == session_id)
    )

    # Unlink documents ( — just break the session link)
    result_docs = await db.execute(
        select(Document).where(Document.session_id == session_id)
    )
    for doc in result_docs.scalars().all():
        doc.session_id = None

    await db.delete(session)
    await db.commit()

    return {"deleted": session_id}


# ── Get messages for a session 
@sessions_router.get("/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
   
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.asc())
    )
    messages = result.scalars().all()

    return {
        "session_id": session_id,
        "messages": [
            {
                "role":       m.role,
                "content":    m.content,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
    }