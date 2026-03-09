from app.graph.chatstate import ChatState
from app.graph.model import LLMFactory







async def document_analysis_node(state: ChatState) -> ChatState:

    full_doc = state["document_text"]

    llm = LLMFactory.create_llm(
        provider="gemini",
        model="gemini-2.5-flash-lite",
        temperature=0,
    )

    prompt = f"""
You are analyzing a document.

Document:
{full_doc}

User question:
{state['user_input']}
"""

    response = await llm.ainvoke(prompt)

    return {
        **state,
        "response": response.content
    }