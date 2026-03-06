from app.graph.chatstate import ChatState


def message_router(state: ChatState):
    if state.get("need_conversation_summary"):
        return "summary_node"

    return "intent_classifier"