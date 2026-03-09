from app.REG.Schema import RetrievalQuery, RetrievalUser
from app.graph.chatstate import ChatState
from app.REG.query.query_db import Retrievel_pipeline


def build_context_text(docs):
    if not docs:
        return ""

    return "\n\n".join(
        f"[Source: {doc['document_id']} | Page: {doc['page_number']}]\n{doc['content']}"
        for doc in docs
    )

async def rag_node(state: ChatState) -> ChatState :
    print("reg_node..")
    query = state.get("user_input")
    user_id = state.get("user_id")

    if not query:
        state["error"] = "Missing user input"
        return state
    
    request = RetrievalQuery(query=query)

    user = RetrievalUser(
        user_id=user_id,
        access_level=state.get("access_level", 1),
        department=state.get("department", "general"),
        role=state.get("role", "user"),
    )
    try:
        results = await Retrievel_pipeline(request, user)
    except Exception as e:
        state["error"] = "Retrieval failed"
        state["debug_error"] = str(e)
        return state

    if not results:
        return {
            **state,
            "final_response": "I couldn't find relevant information in your documents. Please try a different question or upload more documents.",
            "status": "NO_CONTEXT"
        }
    
    state["retrieved_docs"] = results

    state["context"] = "\n\n".join(
        doc["content"] for doc in results
    )
    state["sources"] = [
        {
            "source": doc["source"],
            "page_number": doc["page_number"],
            "document_id": doc["document_id"],
            "score": doc["score"],
        }
        for doc in results
    ]
    print("rag_node")
    return state
    



