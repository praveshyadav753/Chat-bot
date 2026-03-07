from app.graph.chatstate import ChatState
from app.graph.model import LLMFactory
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage


async def llm_node(state: ChatState) -> ChatState:
    print("llm_node....")

    try:
        query = state.get("user_input")
        context = state.get("context")
        history = state.get("messages", [])
        summary = state.get("summary","")

        if not query:
            return {"final_response": "Invalid request.", "status": "ERROR"}

        llm = LLMFactory.create_llm()

        messages = [SystemMessage(content="You are a helpful assistant.")]

        if summary:
            messages.append(SystemMessage(content=f"Conversation summary:\n{summary}"))

        messages.extend(history)

        if context:
            messages.append(
                SystemMessage(
                    content=f"""Answer the question using ONLY the provided context.If the answer is not in the context say:"I don't have enough information to answer that."
                    Context:
                    {context}
                    """
                )
            )

        messages.append(HumanMessage(content=query))

        response = await llm.ainvoke(messages)

        return {
            "messages": [HumanMessage(content=query),AIMessage(content=response.content)],  # reducer will append
            "final_response": response.content,
            "status": "GENERATED",
        }

    except Exception as e:
        print("LLM error:", e)

        return {
            "final_response": "Internal error occurred.",
            "status": "ERROR",
            "error": str(e),
        }
