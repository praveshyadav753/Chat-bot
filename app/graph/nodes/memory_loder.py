from sqlalchemy import select
from app.models.connection import AsyncSessionLocal
from app.models import Message, Document, ChatSession
from app.graph.chatstate import ChatState
from langchain_core.messages import HumanMessage, AIMessage


async def load_state_node(state: ChatState) -> ChatState:
    MAX_HISTORY = 10
    session_id = state["session_id"]

    async with AsyncSessionLocal() as db:

        # Load previous messages
        result = await db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.desc())
            .limit(MAX_HISTORY)
        )
        messages = result.scalars().all()
        messages = list(reversed(messages))

        # Convert to LangChain message format

        chat_messages = []

        for msg in messages:
            if msg.role == "user":
                chat_messages.append(HumanMessage(content=msg.content))
            else:
                chat_messages.append(AIMessage(content=msg.content))

        result = await db.execute(
            select(ChatSession.summary).where(ChatSession.id == session_id)
        )
        summary = result.scalar_one_or_none()
        # Load documents
        docs_result = await db.execute(
            select(Document).where(Document.session_id == session_id)
        )
        documents = docs_result.scalars().all()

    return {
        **state,
        "messages": chat_messages,
        "summary": summary,
        "documents": documents,
        "documents_ready": all(doc.status == "processed" for doc in documents),
        "has_document": len(documents) > 0,
    }
