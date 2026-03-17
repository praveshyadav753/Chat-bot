from langgraph.types import interrupt
from app.graph.chatstate import ChatState

async def clarification_node(state: ChatState) -> ChatState:
    user_response = interrupt({
        "question": state["clarification_question"],
        "options": state.get("clarification_options"),  
    })
    return {
        **state,
        "user_clarification": user_response,
        "clarification_needed": False,
    }