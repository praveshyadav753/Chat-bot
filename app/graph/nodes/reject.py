# graph/nodes/reject.py

from app.graph.chatstate import ChatState


def reject_node(state: ChatState) -> ChatState:
    """
    Final node when request is blocked .
    """

    reasons = state.get("reasons", [])
    severity = state.get("severity", "medium")

    # Safe user-facing message
    state["response"] = (
        "I'm unable to process this request due to policy restrictions."
    )

    # Structured metadata (for logs / analytics)
    state["blocked"] = True
    state["block_metadata"] = {
        "reasons": reasons,
        "severity": severity,
    }

    return state