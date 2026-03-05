from enum import Enum
from app.graph.chatstate import ChatState
from app.graph.model import LLMFactory
# from app.models.connection import AsyncSessionLocal
from app.models.document import Document
from sqlalchemy import select


class Intent(str, Enum):
    FACTUAL = "factual"
    COMPARISON = "comparison"
    CONVERSATION = "conversation"
    SUMMARY = "summary"
    TOOL = "tool"
    OUT_OF_SCOPE = "out_of_scope"


async def classify_intent(
    query: str,
    has_document: bool,
    document_ready: bool,
) -> Intent:

    llm = LLMFactory.create_llm(
        provider="gemini",
        model="gemini-2.5-flash-lite",
        temperature=0,
    )

    prompt = f"""
You are an intent classifier for a RAG-based system.

System Context:
- User has uploaded document: {has_document}
- Document processing completed: {document_ready}

Rules:
- If user asks to summarize but no document is available → return conversation
- If document exists and user asks to summarize → return summary
- If document exists but not ready → return conversation
- If user asks factual question about document → return factual
- If general chat → return conversation
- If calculation or API needed → return tool
- If outside domain → return out_of_scope

Return ONLY one category:
factual | summary | comparison | conversation | tool | out_of_scope

User Query:
{query}
"""

    response = await llm.ainvoke(prompt)
    label = response.content.strip().lower()

    for intent in Intent:
        if intent.value in label:
            return intent

    return Intent.CONVERSATION




async def classifier_node(state: ChatState) -> ChatState:
    
    
    print("classifier_node......")
    intent = await classify_intent(
        query=state["user_input"],
        has_document=state["has_document"],
        document_ready=["document_ready"],
    )

    return {
        **state,
        "intent": intent.value,
    }