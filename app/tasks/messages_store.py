
from datetime import datetime, timezone
from app.celery_app import celery_app
from app.models.connection import sync_session_maker
from app.models.chat import ChatSession
from app.models.messages import Message
import logging

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, max_retries=3)
def persist_messages_task(self, session_id: str, user_id: int, query: str, response: str, summary: str = ""):
    db = sync_session_maker()

    if not user_id or not session_id:
            logger.warning("Missing user_id or session_id, skipping persistence")
            return
           
    try:
        chat_session = db.get(ChatSession, session_id)
        if not chat_session:
            chat_session = ChatSession(
                id=session_id,
                user_id=user_id,
                summary=summary
            )
            db.add(chat_session)

        else:
                chat_session.summary = summary
                chat_session.updated_at = datetime.now(timezone.utc)

        
        if query:
            db.add(
                Message(
                    session_id=session_id,
                    role="user",
                    content=query,
                    created_at=datetime.now(timezone.utc),
                )
            )
        if response:
            db.add(
                Message(
                    session_id=session_id,
                    role="assistant",
                    content=response,
                    created_at=datetime.now(timezone.utc),
                )
            )
        db.commit()
    except Exception as e:
        logger.error(f"Error persisting messages: {str(e)}")    