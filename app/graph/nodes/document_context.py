from app.graph.chatstate import ChatState
# from app.services.document_service import get_document_status_flags
from sqlalchemy import select
from app.models.document import Document
from app.models.connection import AsyncSessionLocal


async def get_document_status_flags(session_id: str, user_id: int):
    print("document_context_node....")
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Document).where(
                Document.session_id == session_id,
                Document.uploaded_by == user_id,
            )
        )

        docs = result.scalars().all()

    return {
        "has_document": len(docs) > 0,
        "document_ready": any(doc.status == "READY" for doc in docs),
    }

async def document_context_node(state: ChatState) -> ChatState:

    flags = await get_document_status_flags(
        session_id=state["session_id"],
        user_id=state["user_id"],
    )

    return {
        **state,
        "has_document": flags["has_document"],
        "document_ready": flags["document_ready"],
    }