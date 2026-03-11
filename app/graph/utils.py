from app.graph.chatstate import ChatState


def message_router(state: ChatState):
    if state.get("need_conversation_summary"):
        return "summarize_conversation"

    return "document_check"