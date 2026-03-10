from app.graph.chatstate import ChatState
from sqlalchemy import select
from app.models.document import Document
from app.models.connection import AsyncSessionLocal


async def get_session_documents(session_id: str, user_id: int) -> list[dict]:
    """
    Fetches all documents for a session and returns them as a list of dicts
    with file_id, filename, and status — ready for the classifier node.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Document.id, Document.filename, Document.status).where(
                Document.session_id == session_id,
                Document.uploaded_by == user_id,
            )
        )
        rows = result.all()

    return [
        {
            "file_id": str(id),
            "filename": filename,
            "status": "ready" if status == "READY" else status.lower(),
        }
        for id, filename, status in rows
    ]


async def document_context_node(state: ChatState) -> ChatState:
    print("[document_context_node] Fetching session documents...")

    session_documents = await get_session_documents(
        session_id=state["session_id"],
        user_id=state["user_id"],
    )

    ready_docs = [doc for doc in session_documents if doc["status"] == "ready"]

    return {
        **state,
        "has_document": len(session_documents) > 0,
        "document_ready": len(ready_docs) > 0,
        "session_documents": session_documents,  
    }