from enum import Enum
from app.graph.chatstate import ChatState
from app.graph.model import LLMFactory
import json
import re


class Intent(str, Enum):
    FACTUAL = "factual"
    DOC_ANALYSIS = "doc_analysis"
    COMPARISON = "comparison"
    CONVERSATION = "conversation"
    SUMMARY = "summary"
    TOOL = "tool"
    OUT_OF_SCOPE = "out_of_scope"


VALID_LABELS = " | ".join(i.value for i in Intent)


SIMPLE_TOOLS_DESCRIPTION = """
- `web_search`        → Search the web for current news, prices, facts, or real-time data
- `fetch_url`         → Fetch and read the content of a URL/link the user provided
- `convert_currency`  → Convert an amount between currencies using live exchange rates
""".strip()

INTENT_PROMPT = """
You are an intent classifier and document resolver for a RAG-based document assistant.

## All Session Documents
{session_docs_formatted}

## Active (Recently Uploaded) Documents
{active_docs_formatted}

## Document Resolution Priority
- If the query refers to "this document", "current document", "just uploaded" → resolve from Active Documents first
- If the query mentions a specific filename or past document → resolve from All Session Documents
- Only include documents where `status == "ready"`
- If ambiguous and no specific doc is mentioned → include ALL ready documents from session

## Classification Rules
If the query is ambiguous and you cannot confidently classify it:
- Set "needs_clarification": true
- Write a short "clarification_question"  
- Optionally set "clarification_options": ["opt1", "opt2"] if obvious choices exist
- Leave options null if free-text reply is better

### Document intents (requires at least one resolved ready document):
- `factual`      → Specific fact or detail from a document (e.g. "who signed?", "what is clause 5?")
- `doc_analysis` → Full-document analysis (e.g. "how many words?", "extract all locations")
- `summary`      → User wants a summary or overview of a document
- `comparison`   → Compare across multiple documents or sections

### General intents:
- `conversation` → Chitchat, greetings, or no ready documents available
- `tool`         → Needs an external tool (see available tools below)
- `out_of_scope` → Completely outside the assistant's domain

## Available Simple Tools (only for `tool` intent)
{simple_tools_description}

## Tool Selection Rules (only when intent is `tool`)
- Set `selected_tools` to a list of tool names FROM the list above that should run
- Set `selected_tools: []` if the tool needed is NOT in the list above (LLM will handle it)
- Set `sequential: true` if tool 2 needs the output of tool 1 (e.g. search price THEN convert)
- Set `sequential: false` if tools are independent and can run at the same time

## Output Rules
- `resolved_document_ids` must be [] for: `conversation`, `tool`, `out_of_scope`
- Only return IDs that appear in the document lists above
- `selected_tools` and `sequential` only matter when intent is `tool`

## Output Format
Respond ONLY with a valid JSON object. No explanation, no markdown, no extra text.

{{
  "intent": "<one of: {valid_labels}>",
  "resolved_document_ids": [],
  "selected_tools": [],
  "sequential": false,
  "needs_clarification": false,
  "clarification_question": null,
  "clarification_options": null,
  "reasoning": "<one sentence>"

## User Query
{query}
""".strip()


def _format_docs(docs: list[dict]) -> str:
    if not docs:
        return "None."
    return "\n".join(
        f"- file_id: {doc.get('file_id')} | filename: {doc.get('filename')} | status: {doc.get('status')}"
        for doc in docs
    )


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response, strip markdown fences if present."""
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)
    return json.loads(text.strip())


def _build_ready_ids(
    session_documents: list[dict], active_docs: list[dict]
) -> set[str]:
    """Build set of all valid ready file_ids from both document pools."""
    all_docs = session_documents + active_docs
    return {
        doc["file_id"]
        for doc in all_docs
        if doc.get("status") == "ready" and doc.get("file_id")
    }


# ── Known simple tool names — validate classifier output against this ─────────
_SIMPLE_TOOL_NAMES = {"web_search", "fetch_url"}


async def classify_and_resolve(
    query: str,
    session_documents: list[dict],
    active_docs: list[dict],
) -> tuple[Intent, list[str], list[str], bool]:
    """
    Classifies intent, resolves document IDs, and selects tools in ONE LLM call.

    Returns:
        Tuple of (Intent, resolved_doc_ids, selected_tools, sequential)
    """
    llm = LLMFactory.create_llm(
        provider="gemini",
        model="gemini-2.5-flash-lite",
        temperature=0,
    )

    prompt = INTENT_PROMPT.format(
        query=query,
        session_docs_formatted=_format_docs(session_documents),
        active_docs_formatted=_format_docs(active_docs),
        valid_labels=VALID_LABELS,
        simple_tools_description=SIMPLE_TOOLS_DESCRIPTION,
    )

    response = await llm.ainvoke(prompt)
    raw = response.content.strip()
    try:
        parsed = _extract_json(raw)

        label = parsed.get("intent", "").strip().lower()
        intent = next(
            (i for i in Intent if i.value == label),
            Intent.CONVERSATION,
        )

        ready_ids = _build_ready_ids(session_documents, active_docs)
        resolved_ids = [
            fid for fid in parsed.get("resolved_document_ids", []) if fid in ready_ids
        ]

        # ── Tool selection
        # Only trust selected_tools when intent is actually tool
        # Validate each name against known simple tools — discard unknown names
        raw_tools = parsed.get("selected_tools", []) if intent == Intent.TOOL else []
        selected_tools = [t for t in raw_tools if t in _SIMPLE_TOOL_NAMES]
        sequential = bool(parsed.get("sequential", False))
        needs_clarification = bool(parsed.get("needs_clarification", False))
        clarification_question = parsed.get("clarification_question")
        clarification_options = parsed.get("clarification_options")  # None or list

        print(
            f"[classifier] intent={intent.value} | "
            f"resolved_docs={resolved_ids} | "
            f"tools={selected_tools} | "
            f"sequential={sequential} | "
            f"reason={parsed.get('reasoning')}"
        )
        return (
            intent,
            resolved_ids,
            selected_tools,
            sequential,
            needs_clarification,
            clarification_question,
            clarification_options,
        )

    except (json.JSONDecodeError, KeyError) as e:
        print(f"[classifier] Failed to parse LLM response: {e}\nRaw: {raw}")
        return Intent.CONVERSATION, [], [], False


async def classifier_node(state: ChatState) -> ChatState:
    print("[classifier_node] Running...")

    session_documents = state.get("session_documents", [])
    active_docs = state.get("active_documents", [])
    user_clarification = state.get("user_clarification")
    query = state["user_input"]
    if user_clarification:
        query = f"{query}\n\nUser clarified: {user_clarification}"

    try:
        (
            intent,
            resolved_document_ids,
            selected_tools,
            sequential,
            needs_clarification,
            clarification_question,
            clarification_options,
        ) = await classify_and_resolve(
            query=state["user_input"],
            session_documents=session_documents,
            active_docs=active_docs,
        )
    except Exception as e:
        print(f"[classifier_node] Unexpected error: {e}. Defaulting to CONVERSATION.")
        intent = Intent.CONVERSATION
        resolved_document_ids = []
        selected_tools = []
        sequential = False

    return {
        **state,
        "intent": intent.value,
        "document_id": resolved_document_ids,
        "selected_tools": selected_tools,
        "sequential": sequential,
        "needs_clarification": needs_clarification,
        "clarification_question": clarification_question,
        "clarification_options": clarification_options,
    }
