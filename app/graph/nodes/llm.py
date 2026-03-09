from app.graph.chatstate import ChatState
from app.graph.model import LLMFactory
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage


async def llm_node(state: ChatState) -> ChatState:
    print("llm_node....")

    try:
        query = state.get("user_input")
        custom_instruction = state.get("prompt")
        context = state.get("context")
        history = state.get("messages", [])
        summary = state.get("summary", "")

        if not query:
            return {"final_response": "Invalid request.", "status": "ERROR"}

        llm = LLMFactory.create_llm()

        messages = [SystemMessage(content="You are a helpful assistant.")]

        if summary:
            messages.append(SystemMessage(content=f"Conversation summary:\n{summary}"))

        messages.extend(history)

        if context:
            # Build context instruction with custom note if provided
            prompt_note = ""
            if custom_instruction:
                prompt_note = f"\n\nAdditional instruction: {custom_instruction}\n"

            context_instruction = f"""Answer the question using ONLY the provided context.
If the answer is not in the context, say: "I don't have enough information to answer that."{prompt_note}

Context:
{context}"""
            messages.append(SystemMessage(content=context_instruction))

        messages.append(HumanMessage(content=query))

        response = await llm.ainvoke(messages)
        print(state.get("error"))

        return {
            "messages": [
                HumanMessage(content=query),
                AIMessage(content=response.content),
            ],
            "final_response": response.content,
            "status": "GENERATED",
        }

    except Exception as e:
        print("LLM error:", e)
        import traceback
        traceback.print_exc()

        return {
            "final_response": "Internal error occurred.",
            "status": "ERROR",
            "error": str(e),
        }
