
# Flow:
#   llm_node_with_tools → LLM sees tool schemas → decides tool + args
#   → tool_calls on AIMessage
#   route_after_llm_tools checks:
#     has tool_calls? → prebuilt ToolNode executes → llm_node (format response)
#     no tool_calls?  → llm_node directly (LLM answered without a tool)

import logging
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.prebuilt import ToolNode

from app.graph.chatstate import ChatState
from app.graph.model import LLMFactory
# from app.graph.nodes.tools import COMPLEX_TOOLS

logger = logging.getLogger(__name__)

COMPLEX_TOOLS=""
complex_tool_node = ToolNode(
    tools=COMPLEX_TOOLS ,
    handle_tool_errors=True,
)


async def llm_node_with_tools(state: ChatState) -> ChatState:
    """
    LLM node with complex tools bound.
    LLM sees tool schemas and decides which tool to call and with what args.

    Returns updated state with AIMessage added to messages.
    If AIMessage has tool_calls → route_after_llm_tools sends to complex_tool_node.
    If no tool_calls → route_after_llm_tools sends to llm_node for response.
    """
    print("[llm_node_with_tools] running...")

    llm = LLMFactory.create_llm(streaming=False)  # non-streaming — we need full response to check tool_calls
    llm_with_tools = llm.bind_tools(COMPLEX_TOOLS)

    messages = list(state.get("messages", []))

    # Inject summary as system context if present
    summary = state.get("conversation_summary", "")
    if summary:
        messages = [SystemMessage(content=f"Conversation so far:\n{summary}")] + messages

    # Inject RAG context if available (from prior rag_node run)
    context = state.get("context", "")
    if context:
        messages.append(
            HumanMessage(content=f"[Context from tools/documents]\n{context}")
        )

    ai_message = await llm_with_tools.ainvoke(messages)

    has_tool_calls = bool(getattr(ai_message, "tool_calls", None))
    print(f"[llm_node_with_tools] has_tool_calls={has_tool_calls}")

    return {
        **state,
        "messages": [ai_message],   
    }


