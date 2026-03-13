from app.graph.chatstate import ChatState
from langchain_core.messages import AIMessage

MAX_EXCHANGES_BEFORE_SUMMARY = 10
EXCHANGES_TO_KEEP = 5


async def check_message_length_node(state: ChatState) -> ChatState:
    print("[check_message_length_node] running...")

    messages = state.get("messages", [])
    exchange_count = sum(1 for m in messages if isinstance(m, AIMessage))

    return {
        **state,
        "need_conversation_summary": exchange_count >= MAX_EXCHANGES_BEFORE_SUMMARY,
    }