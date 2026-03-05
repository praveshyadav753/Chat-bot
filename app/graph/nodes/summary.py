from app.graph.chatstate import ChatState
from app.REG.query.query_db import get_document_chunks
from app.REG.Schema import RetrievalUser


async def summary_node(state: ChatState) -> ChatState:
    print("summary node.....")
    has_document = state.get("has_document", False)
    document_ready = state.get("document_ready", False)
    document_id = state.get("document_id")
    user_request = state.get("user_input", "")

    if not has_document:
        return {
            **state,
            "final_response": "No document is available to summarize.",
        }

    if not document_ready:
        return {
            **state,
            "final_response": "Your document is still being processed. Please wait until processing is complete.",
        }

    if not document_id:
        return {
            **state,
            "error": "Missing document ID for summary.",
        }

    user = RetrievalUser(
        user_id=state["user_id"],
        access_level=state.get("access_level", 1),
        department=state.get("department", "general"),
        role=state.get("role", "user"),
    )

    try:
        chunks = await get_document_chunks(
            document_id=document_id,
            user=user
        )
    except Exception as e:
        return {
            **state,
            "error": "Failed to retrieve document.",
            "debug_error": str(e)
        }

    if not chunks:
        return {
            **state,
            "error": "Document not found or access denied.",
        }

    chunks = sorted(chunks, key=lambda x: x.get("page_number", 0))

    full_text = "\n\n".join(chunk["content"] for chunk in chunks)

    prompt = f"""
You are a professional document summarization assistant. if content not provided just say i dont have content

User Request:
{user_request}

Instructions:
- Generate a clear and structured summary.
- Highlight key points.
- Preserve important facts and numbers.
- Do NOT hallucinate information not present in the document.
- If the document contains sections, summarize section-wise.

DOCUMENT CONTENT:
{full_text}
"""

    return {
        **state,
        "context": full_text,
        "retrieved_docs": chunks,
        "user_input": prompt,
        "summary_mode": True
    }

  