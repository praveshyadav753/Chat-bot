from app.graph.chatstate import ChatState


def guardrail_router(state: ChatState):
    if state.get("blocked"):
        return "reject"

    return "check_message_length"


def route_by_intent(state: ChatState):
    intent = state.get("intent")
    
    if state.get("clarification_needed"):
        return "clarification_node"
    
    if intent == "doc_analysis":
        return "document_analysis_node"
    
    if intent == "factual":
        return "rag_node"
    
    if intent =="summary":
        return "summary_node"

    if intent == "tool":
        return "tool_node"

    if intent == "out_of_scope":
        return "reject"
    
    

    return "llm_node"

