from app.graph.chatstate import ChatState
from app.security.quadrails import run_input_guardrails
# from app.graph.builder import graph

async def input_guardrail_node(state: ChatState) -> ChatState:
    result = await run_input_guardrails(  
        state["user_input"]
    )

    if not result.allowed:
        return {
            **state,
            "blocked": True,
            "block_reason": result.reasons
        }

    return {
        **state,
        "blocked": False
    }