from app.graph.chatstate import ChatState
from app.graph.model import LLMFactory
from langchain_core.messages import HumanMessage, SystemMessage


async def llm_node(state: ChatState) -> ChatState:
    try:
        query = state.get("user_input")
        context = state.get("context")

        if not query:
            state["final_response"] = "Invalid request."
            return state

        llm = LLMFactory.create_llm()

        # Build structured messages
        if context:
            messages = [
                SystemMessage(
                    content="You are a helpful assistant. Use ONLY the provided context."
                ),
                HumanMessage(
                    content=f"Context:\n{context}\n\nQuestion:\n{query}"
                ),
            ]
        else:
            messages = [
                SystemMessage(content="You are a helpful assistant."),
                HumanMessage(content=query),
            ]

        response = await llm.ainvoke(messages)

        state["final_response"] = response.content
        return state

    except Exception as e:
        print("LLM error:", e)
        state["final_response"] = "Internal error occurred."
        return state