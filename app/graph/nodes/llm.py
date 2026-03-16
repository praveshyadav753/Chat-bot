from app.graph.chatstate import ChatState
from app.graph.model import LLMFactory
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage


async def llm_node(state: ChatState) -> ChatState:
    print("llm_node....")

    try:
        query = state.get("user_input")
        custom_instruction = state.get("prompt")
        context = state.get("context")
        summary = state.get("summary", "")

        if not query:
            return {**state, "final_response": "Invalid request.", "status": "ERROR"}

        llm = LLMFactory.create_llm(streaming=True)

        messages = [SystemMessage(content="You are a helpful assistant.")]

        if summary:
            messages.append(SystemMessage(content=f"Conversation summary:\n{summary}"))

        if context:
            prompt_note = (
                f"\n\nAdditional instruction: {custom_instruction}\n"
                if custom_instruction
                else ""
            )
            messages.append(
                SystemMessage(
                    content=f"""Answer the question using ONLY the provided context.
If the answer is not in the context, say: "I don't have enough information to answer that."{prompt_note}

Context:
{context}"""
                )
            )

        messages.append(HumanMessage(content=query))

        response = ""
        async for chunk in llm.astream(messages, config={"tags": ["llm_response"]}):
            if chunk.content:
                response += chunk.content

        return {
            **state,
            "messages": [AIMessage(content=response)],
            "final_response": response,
            "status": "GENERATED",
        }

    except Exception as e:
        print("LLM error:", e)
        import traceback

        traceback.print_exc()
        return {
            **state,
            "final_response": "Internal error occurred.",
            "status": "ERROR",
            "error": str(e),
        }
