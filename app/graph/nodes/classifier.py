# graph/nodes/classifier_node.py

from enum import Enum
# from app.security.models import GuardrailResult
from app.graph.chatstate import ChatState
from app.graph.model import LLMFactory


class Intent(str, Enum):
    FACTUAL = "factual"
    COMPARISON = "comparison"
    CONVERSATION = "conversation"
    SUMMARY = "summary"
    TOOL = "tool"
    OUT_OF_SCOPE = "out_of_scope"


llm = LLMFactory.create_llm(
    provider="gemini",
    model="gemini-2.5-flash-lite", 
    temperature=0
)

async def classify_intent( query: str, ) -> Intent:
    prompt = f"""
    Classify the user query into one of the following categories:

    - factual (requires document retrieval)
    - summary (if user has gives document and include commands like summarize  and similar intent)
    - comparison (requires multiple document retrieval)
    - conversation (general chat, no retrieval)
    - tool (requires calculator or external API)
    - out_of_scope

    Respond with ONLY one category.

    Query:
    {query} {document_for_summary}
    """

    response = await llm.ainvoke(prompt)
    label = response.content.strip().lower()

    try:
        return Intent(label)
    except:
        return Intent.CONVERSATION
    

async def classifier_node(state: ChatState) -> ChatState:
    intent = await classify_intent(
        state["user_input"]
    )
    print("classifier node-->")
    return {
        **state,
        "intent": intent.value
    }

