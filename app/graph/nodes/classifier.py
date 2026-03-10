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

### Document intents (requires at least one resolved ready document):
- `factual`      → Specific fact or detail from a document (e.g. "who signed?", "what is clause 5?")
- `doc_analysis` → Full-document analysis (e.g. "how many words?", "extract all locations")
- `summary`      → User wants a summary or overview of a document
- `comparison`   → Compare across multiple documents or sections

### General intents:
- `conversation` → Chitchat, greetings, or no ready documents available
- `tool`         → Needs calculation, API, or external lookup
- `out_of_scope` → Completely outside the assistant's domain

## Output Rules
- `resolved_document_ids` must be [] for: `conversation`, `tool`, `out_of_scope`
- Only return IDs that appear in the document lists above

## Output Format
Respond ONLY with a valid JSON object. No explanation, no markdown, no extra text.

{{
  "intent": "<one of: {valid_labels}>",
  "resolved_document_ids": ["<file_id>", ...],
  "reasoning": "<one short sentence>"
}}

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
    """Extracts JSON from LLM response, stripping markdown fences if present."""
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)
    return json.loads(text.strip())


def _build_ready_ids(session_documents: list[dict], active_docs: list[dict]) -> set[str]:
    """
    Builds a set of all valid ready file_ids from both document pools.
    This prevents LLM-resolved IDs from active_docs being silently dropped.
    """
    all_docs = session_documents + active_docs
    return {
        doc["file_id"]
        for doc in all_docs
        if doc.get("status") == "ready" and doc.get("file_id")
    }


async def classify_and_resolve(
    query: str,
    session_documents: list[dict],
    active_docs: list[dict],
) -> tuple[Intent, list[str]]:
    """
    Classifies intent and resolves relevant document IDs in a single LLM call.

    Args:
        query:            The user's input.
        session_documents: All docs in the session [{file_id, filename, status}].
        active_docs:      Recently uploaded/active docs, same shape.

    Returns:
        Tuple of (Intent, list of validated resolved file_ids)
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
    )

    response = await llm.ainvoke(prompt)
    raw = response.content.strip()

    try:
        parsed = _extract_json(raw)

        # Resolve intent
        label = parsed.get("intent", "").strip().lower()
        intent = next(
            (i for i in Intent if i.value == label),
            Intent.CONVERSATION,  # default fallback
        )

        # Validate resolved IDs against both document pools
        ready_ids = _build_ready_ids(session_documents, active_docs)
        resolved_ids = [
            fid for fid in parsed.get("resolved_document_ids", [])
            if fid in ready_ids
        ]

        print(
            f"[classifier] intent={intent.value} | "
            f"resolved_docs={resolved_ids} | "
            f"reason={parsed.get('reasoning')}"
        )
        return intent, resolved_ids

    except (json.JSONDecodeError, KeyError) as e:
        print(f"[classifier] Failed to parse LLM response: {e}\nRaw: {raw}")
        return Intent.CONVERSATION, []


async def classifier_node(state: ChatState) -> ChatState:
    print("[classifier_node] Running...")

    session_documents = state.get("session_documents", [])
    active_docs = state.get("active_documents", [])  # safe default to []

    try:
        intent, resolved_document_ids = await classify_and_resolve(
            query=state["user_input"],
            session_documents=session_documents,
            active_docs=active_docs,
        )
    except Exception as e:
        print(f"[classifier_node] Unexpected error: {e}. Defaulting to CONVERSATION.")
        intent = Intent.CONVERSATION
        resolved_document_ids = []

    return {
        **state,
        "intent": intent.value,
        "document_id": resolved_document_ids,
    }