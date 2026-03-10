from app.graph.chatstate import ChatState
from app.REG.query.query_db import get_document_chunks
from app.REG.Schema import RetrievalUser
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
import logging

from app.graph.model import LLMFactory
logger = logging.getLogger(__name__)

# async def summary_node(state: ChatState) -> ChatState:
#     print("summary node.....")

#     # summary_type = state.get("summary_type", "document")
#     summary_type = state.get("summary_type", "conversation")

#     if summary_type == "conversation":
#         return await _summarize_conversation(state)

   
#     elif summary_type == "document":
#         return await _summarize_document(state)

#     return state


async def summarize_document_node(state: ChatState) -> ChatState:
    """
    Summarize a specific document for analysis.
    """
    
    print("Summarization mode: DOCUMENT")
    
    has_document = state.get("has_document", False)
    document_ready = state.get("document_ready", False)
    document_id = state.get("document_id")
    user_request = state.get("user_input", "")

    if not has_document:
        print("No document available")
        return {
            **state,
            "final_response": "No document is available. Please upload a document first.",
        }

    if not document_ready:
        print("Document still processing")
        return {
            **state,
            "final_response": "Your document is still being processed. Please wait until processing is complete.",
        }

    if not document_id:
        logger.error("Missing document ID")
        return {
            **state,
            "error": "Missing document ID for summary.",
        }

    user = RetrievalUser(
        user_id=state.get("user_id", 0),
        access_level=state.get("access_level", 1),
        department=state.get("department", "general"),
        role=state.get("role", "user"),
    )

    try:
        chunks = await get_document_chunks(
            document_id=document_id if isinstance(document_id, list) else [document_id],
            user=user
        )
        

    except Exception as e:
        logger.error(f"Error retrieving document chunks: {str(e)}")
        print(f" Retrieval error: {str(e)}")
        return {
            **state,
            "error": "Failed to retrieve document.",
            "debug_error": str(e)
        }

    if not chunks:
        print("No document chunks found")
        return {
            **state,
            "error": "Document not found or access denied.",
        }

    chunks = sorted(chunks, key=lambda x: x.get("page_number", 0))
    full_text = "\n\n".join(chunk["content"] for chunk in chunks)

    print(f"  → Document text: {len(full_text)} chars")

    prompt = f"""
You are a document summarization assistant.

DOCUMENT CONTENT:
{full_text}

USER REQUEST:
{user_request}

INSTRUCTIONS:
- Provide a comprehensive summary
- Answer the user's specific question if asked
- Highlight key sections and important points
- Include relevant data, numbers, and facts
- Do NOT hallucinate or add information not in the document
- If the document doesn't contain answer, say so explicitly

RESPONSE:
"""


    return {
        **state,
        "user_input": user_request,
        "prompt": prompt,
        "context": full_text,
        "retrieved_docs": chunks,
        "summary_mode": True
    }
