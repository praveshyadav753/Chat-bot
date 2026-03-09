from app.graph.chatstate import ChatState
from app.models.connection import AsyncSessionLocal
from app.models.messages import Message
from app.models.chat import ChatSession

from sqlalchemy.future import select
from datetime import datetime
from langchain_core.messages import HumanMessage, AIMessage

async def persist_message_node(state: ChatState) -> ChatState:

    user_id = state.get("user_id")
    session_id = state.get("session_id")
    query = state.get("user_input")
    final_response = state.get("final_response")
    summary = state.get("summary", "")

    if not user_id or not session_id:
        return state

    async with AsyncSessionLocal() as session:
        async with session.begin():

            # 1️⃣ Ensure chat session exists FIRST
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
                chat_session.summary = summary
                chat_session.updated_at = datetime.utcnow()

            # 2️⃣ Now insert messages
            if query:
                session.add(
                    Message(
                        session_id=session_id,
                        role="user",
                        content=query,
                        created_at=datetime.utcnow(),
                    )
                )

            if final_response:
                session.add(
                    Message(
                        session_id=session_id,
                        role="assistant",
                        content=final_response,
                        created_at=datetime.utcnow(),
                    )
                )

    return state