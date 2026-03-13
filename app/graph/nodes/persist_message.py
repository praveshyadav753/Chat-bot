from app.graph.chatstate import ChatState
from app.tasks.messages_store import persist_messages_task
import logging

logger = logging.getLogger(__name__)


async def persist_message_node(state: ChatState) -> ChatState:
    print("[persist_message_node] dispatching to background...")

    user_id    = state.get("user_id")
    session_id = state.get("session_id")
    query      = state.get("user_input")
    response   = state.get("final_response")
    summary    = state.get("summary") or ""

    if not user_id or not session_id:
        logger.warning("[persist_message_node] missing user_id or session_id, skipping")
        return state

    persist_messages_task.delay(
        session_id=session_id,
        user_id=user_id,
        query=query,
        response=response,
        summary=summary,
    )

    return state  