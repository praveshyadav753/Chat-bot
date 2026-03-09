from enum import Enum
from app.graph.chatstate import ChatState
from app.graph.model import LLMFactory

# from app.models.connection import AsyncSessionLocal
from app.models.document import Document
from sqlalchemy import select


class Intent(str, Enum):
    FACTUAL = "factual"
    DOC_ANALYSIS = "doc_analysis"
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

    If document exists:

    1. Questions about specific information from document
    Example:
    - who signed the agreement
    - what is clause 5
    - what is refund policy
    → factual

    2. Questions requiring whole document analysis
    Example:
    - total words
    - total lines
    - extract locations
    - what is this document about
    → doc_analysis

    3. If user asks to summarize document
    → summary

    4. If document exists but not processed
    → conversation

    General rules:
    - Normal chat → conversation
    - Calculations / APIs → tool
    - Outside domain → out_of_scope

    Return ONLY one category:

    factual | doc_analysis | summary | comparison | conversation | tool | out_of_scope

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
        document_ready=state.get("document_ready", False),
    )

    return {
        **state,
        "intent": intent.value,
    }
