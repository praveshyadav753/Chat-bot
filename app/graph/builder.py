from langgraph.graph import START, END, StateGraph
from app.graph.chatstate import ChatState

from app.graph.nodes.check_message_length import check_message_length_node
from app.graph.nodes.document_analysis import document_analysis_node
from app.graph.nodes.document_context import document_context_node
from app.graph.nodes.input_guardrails import input_guardrail_node
from app.graph.nodes.classifier import classifier_node
from app.graph.nodes.llm import llm_node
from app.graph.nodes.persist_message import persist_message_node
from app.graph.nodes.rag import rag_node
from app.graph.nodes.reject import reject_node
from app.graph.nodes.summarize_doc import summarize_document_node
from app.graph.nodes.summarize_conversation import summarize_conversation
from app.graph.routes import guardrail_router, route_by_intent
from app.graph.utils import message_router
from app.graph.nodes.memory_loder import load_state_node
from langgraph.checkpoint.memory import InMemorySaver
from IPython.display import Image, display


builder = StateGraph(ChatState)

# Add nodes
builder.add_node("load_state", load_state_node)
builder.add_node("input_guardrails", input_guardrail_node)
builder.add_node("check_messages_length", check_message_length_node)
builder.add_node("summarize_conversation",summarize_conversation)
builder.add_node("document_context", document_context_node)
builder.add_node("classify", classifier_node)
builder.add_node("rag_node", rag_node)
builder.add_node("summarize_document_node", summarize_document_node)
builder.add_node("document_analysis_node",document_analysis_node)
builder.add_node("llm_node", llm_node)
builder.add_node("reject", reject_node)
builder.add_node("persist_data",persist_message_node)


builder.add_edge(START, "load_state")

# Load memory → guardrail
builder.add_edge("load_state", "input_guardrails")

# Guardrail routing
builder.add_conditional_edges(
    "input_guardrails",
    guardrail_router,
    {
        "reject": "reject",
        "check_message_length": "check_messages_length",
    },
)

builder.add_conditional_edges(
    "check_messages_length",
    message_router,
    {
        "summarize_conversation": "summarize_conversation",
        "document_check": "document_context"
    },
)
builder.add_edge("summarize_conversation", "document_context")  

builder.add_edge("document_context", "classify")

builder.add_conditional_edges(
    "classify",
    route_by_intent,
    {
        "rag_node": "rag_node",
        "llm_node": "llm_node",
        "summary_node": "summarize_document_node",
        "document_analysis_node":"document_analysis_node",
        "reject": "reject",
       
    },
)

builder.add_edge("rag_node", "llm_node")

builder.add_edge("summarize_document_node", "llm_node")
builder.add_edge("document_analysis_node","llm_node")
builder.add_edge("llm_node","persist_data")
builder.add_edge("persist_data", END)
builder.add_edge("reject", END)


checkpointer = InMemorySaver()

graph = builder.compile(checkpointer=checkpointer)

display(Image(graph.get_graph().draw_mermaid_png()))
