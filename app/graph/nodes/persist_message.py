from app.graph.chatstate import ChatState
from app.models.connection import AsyncSessionLocal
from app.models.messages import Message
from app.models.chat import ChatSession

from sqlalchemy.future import select
from datetime import datetime, timezone
from langchain_core.messages import HumanMessage, AIMessage
import logging
logger = logging.getLogger(__name__)


async def persist_message_node(state: ChatState) -> ChatState:
    print("data-persistent node......")
    user_id = state.get("user_id")
    session_id = state.get("session_id")
    query = state.get("user_input")
    final_response = state.get("final_response")
    summary = state.get("summary") or ""
    messages = state.get("messages", [])  
    message_count = state.get("message_count", 0)

    if not user_id or not session_id:
        logger.warning("Missing user_id or session_id, skipping persistence")
        return state
    try:
        async with AsyncSessionLocal() as session:
            async with session.begin():

                result = await session.execute(
                    select(ChatSession).where(ChatSession.id == session_id)
                )

                chat_session = result.scalars().first()

                if not chat_session:
                    chat_session = ChatSession(
                        id=session_id,
                        user_id=user_id,
                        summary=summary
                    )
                    session.add(chat_session)

                else:
                        print(f"  → Updating session summary ({len(summary)} chars)")
                        chat_session.summary = summary
                        chat_session.updated_at = datetime.now(timezone.utc)

                
                if query:
                    session.add(
                        Message(
                            session_id=session_id,
                            role="user",
                            content=query,
                            created_at=datetime.now(timezone.utc),
                        )
                    )
                    

                if final_response:
                    session.add(
                        Message(
                            session_id=session_id,
                            role="assistant",
                            content=final_response,
                            created_at=datetime.now(timezone.utc),
                        )
                    )
            await session.commit()
    except Exception as e:
        logger.error(f"Error persisting messages: {str(e)}")            

    return state