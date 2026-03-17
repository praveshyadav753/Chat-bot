from langgraph.graph import START, END, StateGraph
from langgraph.prebuilt import tools_condition

from app.graph.chatstate import ChatState
from app.graph.routes import guardrail_router, route_by_intent
from app.graph.utils import message_router
from app.core.checkpointer import get_checkpointer

#  Nodes
from app.graph.nodes.input_guardrails import input_guardrail_node
from app.graph.nodes.check_message_length import check_message_length_node
from app.graph.nodes.summarize_conversation import summarize_conversation
from app.graph.nodes.document_context import document_context_node
from app.graph.nodes.classifier import classifier_node
from app.graph.nodes.rag import rag_node
from app.graph.nodes.summarize_doc import summarize_document_node
from app.graph.nodes.document_analysis import document_analysis_node
from app.graph.nodes.tools import tool_node
from app.graph.nodes.llm_with_tool import llm_node_with_tools, complex_tool_node
from app.graph.nodes.llm import llm_node
from app.graph.nodes.reject import reject_node
from app.graph.nodes.persist_message import persist_message_node
from app.graph.nodes.clarification import clarification_node


builder = StateGraph(ChatState)

#  Register nodes 
builder.add_node("input_guardrails", input_guardrail_node)
builder.add_node("check_messages_length", check_message_length_node)
builder.add_node("summarize_conversation", summarize_conversation)
builder.add_node("document_context", document_context_node)
builder.add_node("classify", classifier_node)
builder.add_node("rag_node", rag_node)
builder.add_node("summarize_document_node", summarize_document_node)
builder.add_node("document_analysis_node", document_analysis_node)
builder.add_node("tool_node", tool_node)
builder.add_node("llm_node_with_tools", llm_node_with_tools)
builder.add_node("complex_tool_node", complex_tool_node)
builder.add_node("llm_node", llm_node)
builder.add_node("reject", reject_node)
builder.add_node("persist_data", persist_message_node)
builder.add_node("clarification_node", clarification_node)

#  Edges 

builder.add_edge(START, "input_guardrails")

# Guardrail → reject or continue
builder.add_conditional_edges(
    "input_guardrails",
    guardrail_router,
    {
        "reject": "reject",
        "check_message_length": "check_messages_length",
    },
)

# Message length → summarize or continue
builder.add_conditional_edges(
    "check_messages_length",
    message_router,
    {
        "summarize_conversation": "summarize_conversation",
        "document_check": "document_context",
    },
)

builder.add_edge("summarize_conversation", "document_context")
builder.add_edge("document_context", "classify")

# Classifier → route by intent
builder.add_conditional_edges(
    "classify",
    route_by_intent,
    {
        "rag_node": "rag_node",
        "summary_node": "summarize_document_node",  
        "document_analysis_node": "document_analysis_node",
        "tool_node": "tool_node",
        "llm_node_with_tools": "llm_node_with_tools",
        "llm_node": "llm_node",
        "reject": "reject",
    },
)
builder.add_edge("clarification_node", "classify")

# ── Simple tool path 
builder.add_edge("tool_node", "llm_node")

# ── Complex tool path 
builder.add_conditional_edges(
    "llm_node_with_tools",
    tools_condition,
    {
        "tools": "complex_tool_node",
        "__end__": "llm_node",
    },
)
builder.add_edge("complex_tool_node", "llm_node")

# ── Document paths 
builder.add_edge("rag_node", "llm_node")
builder.add_edge("summarize_document_node", "llm_node")
builder.add_edge("document_analysis_node", "llm_node")

# ── Final 
builder.add_edge("llm_node", "persist_data")
builder.add_edge("persist_data", END)
builder.add_edge("reject", END)


async def build_graph():
    checkpointer = await get_checkpointer()
    graph = builder.compile(checkpointer=checkpointer)
    return graph
