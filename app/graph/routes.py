from app.graph.chatstate import ChatState


def guardrail_router(state: ChatState):
    if state.get("blocked"):
        return "reject"

    return "classify"


def route_by_intent(state: ChatState):
    intent = state.get("intent")

    if intent == "factual":
        return "rag_node"

    if intent == "comparison":
        return "comparison_rag_node"

    if intent == "tool":
        return "tool_node"

    if intent == "out_of_scope":
        return "reject"

    return "llm_node"

