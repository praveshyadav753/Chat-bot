# app/graph/nodes/tool_node.py
#
# Classifier-driven tool executor — Pattern 6 (simple tools).
#
# Flow:
#   classifier sets state["selected_tools"] + state["sequential"]
#   this node reads those, builds fake tool_calls, runs via prebuilt ToolNode
#   results stored in state["context"] for llm_node to format
#
# Why prebuilt ToolNode instead of manual invoke loop?
#   - Handles InjectedState injection automatically
#   - Handles parallel execution natively
#   - Handles errors gracefully (returns ToolMessage with error, not raise)
#   - Handles Command() returns correctly
#   - We get all official behaviour for free
#
# The trick: we construct AIMessage.tool_calls manually from classifier output
# so ToolNode thinks the LLM made the decision — but really the classifier did.

import json
import asyncio
import logging
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import ToolNode

from app.graph.chatstate import ChatState
from app.tools import SIMPLE_TOOLS, TOOL_MAP

logger = logging.getLogger(__name__)

# ── One shared ToolNode instance for all simple tools ─────────────────────────
# handle_tool_errors=True: on error returns ToolMessage with error text
# instead of raising — graph keeps running, llm_node sees the error message
_simple_tool_node = ToolNode(
    tools=SIMPLE_TOOLS,
    handle_tool_errors=True,
)


async def _extract_args_for_tool(
    tool_name: str,
    query: str,
    previous_result: str,
    state: ChatState,
) -> dict[str, Any]:
    """
    Extract tool args from the user query.
    For most simple tools args are obvious — use lightweight pattern matching.
    Args:
        tool_name:       Name of the tool to extract args for.
        query:           Original user query.
        previous_result: Output of previous tool in sequential chain.
        state:           Full graph state (for user context).

    Returns:
        dict of args to pass to the tool (excluding InjectedState fields).
    """
    q = query.lower().strip()

    if tool_name == "web_search":
        return {"query": query}

    if tool_name == "fetch_url":
        import re

        match = re.search(r"https?://\S+", query)
        url = match.group(0) if match else query.strip()
        return {"url": url}

    # Unknown tool — pass query as-is, let tool handle it
    logger.warning(f"[tool_node] no arg extractor for '{tool_name}', passing raw query")
    return {"query": query}


def _build_tool_call(tool_name: str, args: dict, call_id: str) -> dict:
    """Build a tool_call dict in the format AIMessage expects."""
    return {
        "name": tool_name,
        "args": args,
        "id": call_id,
        "type": "tool_call",
    }


async def tool_node(state: ChatState, config: RunnableConfig) -> ChatState:
    """
    Classifier-driven tool executor.

    Reads state["selected_tools"] and state["sequential"] set by classifier.
    Builds synthetic AIMessage with tool_calls, runs through prebuilt ToolNode.
    Stores combined results in state["context"] for llm_node.

    config: LangGraph injects this automatically — contains thread_id,
            checkpointer refs, run metadata. We pass it straight to ToolNode
            so InjectedState resolution works correctly.

    Parallel:   all tools run simultaneously via ToolNode's native parallel exec.
    Sequential: tools run one at a time, each result passed to next arg extraction.
    """
    print("[tool_node] running...")

    selected_tools: list[str] = state.get("selected_tools") or []
    sequential: bool = state.get("sequential", False)
    query: str = state.get("user_input", "")

    if not selected_tools:
        logger.warning("[tool_node] called with no selected_tools — skipping")
        return state

    # Validate all tools exist in registry
    unknown = [t for t in selected_tools if t not in TOOL_MAP]
    if unknown:
        logger.error(f"[tool_node] unknown tools: {unknown}")
        return {**state, "context": f"Tool(s) not found: {unknown}"}

    results: list[str] = []

    # ── Sequential execution ──────────────────────────────────────────────────
    if sequential:
        print(f"[tool_node] sequential mode: {selected_tools}")
        previous_result = ""

        for idx, tool_name in enumerate(selected_tools):
            call_id = f"call_{idx}"
            args = await _extract_args_for_tool(
                tool_name, query, previous_result, state
            )

            print(
                f"[tool_node] sequential [{idx+1}/{len(selected_tools)}] {tool_name} args={args}"
            )

            # Build synthetic AIMessage so ToolNode can execute
            fake_ai_msg = AIMessage(
                content="",
                tool_calls=[_build_tool_call(tool_name, args, call_id)],
            )

            tool_output = await _simple_tool_node.ainvoke(
                {"messages": [fake_ai_msg]},
                config,  # ← real LangGraph config
            )

            # Extract text from ToolMessage
            result_text = _extract_result_text(tool_output, call_id)
            results.append(f"[{tool_name}]\n{result_text}")
            previous_result = result_text
            print(f"[tool_node] {tool_name} result preview: {result_text[:100]}")

    # ── Parallel execution ────────────────────────────────────────────────────
    else:
        print(f"[tool_node] parallel mode: {selected_tools}")

        # Extract all args in parallel first (most are instant pattern matches)
        args_list = await asyncio.gather(
            *[_extract_args_for_tool(t, query, "", state) for t in selected_tools]
        )

        # Build ONE AIMessage with ALL tool_calls — ToolNode runs them in parallel
        tool_calls = [
            _build_tool_call(tool_name, args, f"call_{idx}")
            for idx, (tool_name, args) in enumerate(zip(selected_tools, args_list))
        ]

        print(f"[tool_node] parallel tool_calls: {[tc['name'] for tc in tool_calls]}")

        fake_ai_msg = AIMessage(content="", tool_calls=tool_calls)

        tool_output = await _simple_tool_node.ainvoke(
            {"messages": [fake_ai_msg]},
            config,  # ← real LangGraph config
        )

        # ToolNode returns messages list — extract each ToolMessage result
        output_messages = tool_output.get("messages", [])
        for tool_call, msg in zip(tool_calls, output_messages):
            if isinstance(msg, ToolMessage):
                results.append(f"[{tool_call['name']}]\n{msg.content}")
                print(
                    f"[tool_node] parallel result [{tool_call['name']}]: {msg.content[:100]}"
                )

    combined = "\n\n---\n\n".join(results)
    print(f"[tool_node] done. total context chars: {len(combined)}")

    return {
        **state,
        "context": combined,
        "tool_results": results,
    }


def _extract_result_text(tool_output: dict, call_id: str) -> str:
    """
    Pull the result text out of ToolNode's output for a specific call_id.
    ToolNode returns {"messages": [ToolMessage(...), ...]}
    """
    messages = tool_output.get("messages", [])
    for msg in messages:
        if isinstance(msg, ToolMessage) and msg.tool_call_id == call_id:
            return msg.content
    # Fallback — return first message content
    if messages and isinstance(messages[0], ToolMessage):
        return messages[0].content
    return "Tool returned no output."
