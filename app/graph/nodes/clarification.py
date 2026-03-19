from langgraph.types import interrupt
from app.graph.chatstate import ChatState


async def clarification_node(state: ChatState) -> ChatState:
    """
    Interrupts to ask the user a clarification question, then resumes with
    their answer.  Crucially, ALL previous Q&A pairs are preserved so the
    classifier sees the full clarification history on every subsequent pass.
    """
    question = state["clarification_question"]
    options = state.get("clarification_options")

    #  Pause and wait for the user's answer
    user_response = interrupt(
        {
            "question": question,
            "options": options,
        }
    )

  
    history: list[dict] = list(state.get("clarification_history", []) or [])
    history.append({"question": question, "answer": user_response})

    # Build a single enriched string the classifier can read directly.
    clarification_context = "\n\n".join(
        f"Q: {entry['question']}\nA: {entry['answer']}" for entry in history
    )

    return {
        **state,
        "user_clarification": clarification_context,
        "clarification_history": history,
        "clarification_needed": False,
        "clarification_question": None,
        "clarification_options": None,
    }
