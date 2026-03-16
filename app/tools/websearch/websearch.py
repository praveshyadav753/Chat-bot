
# InjectedState injects user_id + session_id from graph state automatically.
# ToolNode handles the injection — LLM never sees those params in the schema.

from typing import Annotated, Optional
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from .providers import search


@tool
def web_search(
    query: str,
    state: Annotated[dict, InjectedState],
) -> str:
    """
    Search the web for current information, news, prices, or real-time data.
    Use when the user asks about recent events, live data, or anything
    not found in their uploaded documents.
    Do NOT use for questions answerable from uploaded documents.
    """
    # InjectedState gives us user context for logging — LLM never sees this
    user_id    = state.get("user_id")
    session_id = state.get("session_id")

    return search(query, user_id=user_id)