from enum import Enum
from app.graph.chatstate import ChatState
from app.graph.model import LLMFactory
import json
import re


class Intent(str, Enum):
    FACTUAL       = "factual"
    DOC_ANALYSIS  = "doc_analysis"
    COMPARISON    = "comparison"
    CONVERSATION  = "conversation"
    SUMMARY       = "summary"
    TOOL          = "tool"
    OUT_OF_SCOPE  = "out_of_scope"


VALID_LABELS = " | ".join(i.value for i in Intent)


SIMPLE_TOOLS_DESCRIPTION = """
- `web_search`       → Search the web for current news, prices, facts, or real-time data
- `fetch_url`        → Fetch and read the content of a URL/link the user provided
- `convert_currency` → Convert an amount between currencies using live exchange rates
""".strip()



INTENT_PROMPT = """
You are an intent classifier and document resolver for a RAG-based document assistant.

════════════════════════════════════════
SESSION DOCUMENTS (all documents uploaded so far)
════════════════════════════════════════
{session_docs_formatted}

════════════════════════════════════════
ACTIVE DOCUMENTS (most recently uploaded in this turn)
════════════════════════════════════════
{active_docs_formatted}

════════════════════════════════════════
DOCUMENT RESOLUTION RULES
════════════════════════════════════════
- "this document" / "current document" / "just uploaded" → resolve from ACTIVE DOCUMENTS first
- Specific filename or past document mentioned → resolve from SESSION DOCUMENTS
- Only include documents where status == "ready"
- If no specific document is mentioned and session has ready documents → include ALL ready session documents
- `resolved_document_ids` MUST be [] for intents: conversation | tool | out_of_scope

════════════════════════════════════════
INTENT DEFINITIONS
════════════════════════════════════════
Document intents (only valid when at least one ready document is resolved):
  factual      → User asks for a specific fact, clause, value, or detail from a document
  doc_analysis → User wants structural analysis (word count, extract entities, tables, etc.)
  summary      → User wants a summary or high-level overview of a document
  comparison   → User wants to compare content across multiple documents or sections

General intents:
  conversation → Greeting, chitchat, or no ready documents are available
  tool         → Query requires an external tool (see AVAILABLE TOOLS below)
  out_of_scope → Query is completely outside the assistant's domain

════════════════════════════════════════
AVAILABLE TOOLS  (only relevant when intent == "tool")
════════════════════════════════════════
{simple_tools_description}

Tool selection rules:
  - Set selected_tools to tool names from the list above that should run
  - Set selected_tools: [] if no tool above fits (the LLM will handle it directly)
  - Set sequential: true  if tool 2 needs the output of tool 1
  - Set sequential: false if tools can run in parallel


════════════════════════════════════════
CLARIFICATION HISTORY  ← ALREADY ANSWERED — DO NOT RE-ASK THESE
════════════════════════════════════════
{clarification_history}
 
Rules for clarification history:
- Every Q/A pair above has ALREADY been answered by the user. NEVER ask them again.
- Treat all answers as confirmed facts when classifying.
- Only set needs_clarification: true if critical information is STILL missing
  that was NOT covered by any question already in the history above.
- If the history gives you enough to classify confidently → SET needs_clarification: false
  and return the correct intent immediately.

════════════════════════════════════════
CLARIFICATION RULES  ← READ CAREFULLY
════════════════════════════════════════
NEVER ask a follow-up question in your response text.
If you need more information before you can classify accurately, you MUST signal it
via the structured fields below — NOT by writing a question in "reasoning".

Set needs_clarification: true ONLY when ALL of the following are true:
  1. The query is genuinely ambiguous (multiple very different intents are equally likely)
  2. You cannot make a reasonable default assumption
  3. A one-sentence clarification question would meaningfully change your classification

Set needs_clarification: false when:
  - The intent is clear enough to proceed (even if not 100% certain)
  - The query is a greeting, chitchat, or small-talk
  - You could pick a reasonable default intent and proceed

When needs_clarification is true:
  - Write a SHORT, direct clarification_question (one sentence, no filler)
  - Set clarification_options to 2–4 short option strings IF the answer is multiple-choice
  - Set clarification_options: null if a free-text reply is more appropriate
note : if user says create app then we need clarification question like "what type of app do you want to create?" with options "mobile", "web", "desktop" and what language do you want to use? with options "python", "javascript", "java"
════════════════════════════════════════
OUTPUT FORMAT
════════════════════════════════════════
Respond ONLY with a single valid JSON object.
No explanation. No markdown fences. No extra text before or after the JSON.

{{
  "intent": "<{valid_labels}>",
  "resolved_document_ids": [],
  "selected_tools": [],
  "sequential": false,
  "needs_clarification": false,
  "clarification_question": null,
  "clarification_options": null,
  "reasoning": "<one concise sentence — no questions here>"
}}

════════════════════════════════════════
USER QUERY
════════════════════════════════════════
{query}
""".strip()


# ── Formatting helpers ────────────────────────────────────────────────────────

def _format_docs(docs: list[dict]) -> str:
    if not docs:
        return "None."
    return "\n".join(
        f"- file_id: {doc.get('file_id')} | "
        f"filename: {doc.get('filename')} | "
        f"status: {doc.get('status')}"
        for doc in docs
    )


def _extract_json(text: str) -> dict:
    """
    Extract a JSON object from LLM output.
    Handles:
      - Raw JSON
      - JSON wrapped in ```json ... ``` fences
      - Stray text before/after the JSON object
    """
    # 1. Try stripping markdown fences
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))

    # 2. Try extracting the first {...} block (handles leading/trailing prose)
    bare = re.search(r"\{.*\}", text, re.DOTALL)
    if bare:
        return json.loads(bare.group(0))

    # 3. Last resort — parse the whole thing and let json.loads raise
    return json.loads(text.strip())

def _format_clarification_history(history: list[dict] | None) -> str:
    """Format accumulated Q&A pairs into a readable block for the prompt."""
    if not history:
        return "None — no clarification has been collected yet."
    return "\n\n".join(
        f"Q: {entry['question']}\nA: {entry['answer']}"
        for entry in history
    )

def _build_ready_ids(
    session_documents: list[dict],
    active_docs: list[dict],
) -> set[str]:
    """Return the set of file_ids that are ready across both document pools."""
    all_docs = session_documents + active_docs
    return {
        doc["file_id"]
        for doc in all_docs
        if doc.get("status") == "ready" and doc.get("file_id")
    }


# ── Known simple tool names — classifier output is validated against this ─────
_SIMPLE_TOOL_NAMES: frozenset[str] = frozenset({"web_search", "fetch_url", "convert_currency"})

# ── Safe defaults returned on any failure path ────────────────────────────────
_SAFE_DEFAULT: tuple = (
    Intent.CONVERSATION,  
    [],                  
    [],                   
    False,               
    False,               
    None,                 
    None,                 
)


async def classify_and_resolve(
    query: str,
    session_documents: list[dict],
    active_docs: list[dict],
    clarification_history: list[dict] | None = None,

) -> tuple[Intent, list[str], list[str], bool, bool, str | None, list[str] | None]:
    """
    Classifies intent, resolves document IDs, and selects tools in ONE LLM call.

    Returns a 7-tuple:
        (intent, resolved_doc_ids, selected_tools, sequential,
         needs_clarification, clarification_question, clarification_options)

    Never raises — always returns _SAFE_DEFAULT on failure.
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
        clarification_history=_format_clarification_history(clarification_history),
    )

    try:
        response = await llm.ainvoke(prompt)
        raw = response.content.strip()
    except Exception as e:
        print(f"[classifier] LLM call failed: {e}")
        return _SAFE_DEFAULT

    try:
        parsed = _extract_json(raw)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[classifier] JSON parse failed: {e}\nRaw output:\n{raw}")
        return _SAFE_DEFAULT

    try:
        # ── Intent
        label  = parsed.get("intent", "").strip().lower()
        intent = next(
            (i for i in Intent if i.value == label),
            Intent.CONVERSATION,
        )

        # ── Document IDs — only for document intents
        ready_ids    = _build_ready_ids(session_documents, active_docs)
        resolved_ids = [
            fid
            for fid in parsed.get("resolved_document_ids", [])
            if fid in ready_ids
        ]

        # ── Tools — only trusted when intent is tool; unknown names discarded
        raw_tools      = parsed.get("selected_tools", []) if intent == Intent.TOOL else []
        selected_tools = [t for t in raw_tools if t in _SIMPLE_TOOL_NAMES]
        sequential     = bool(parsed.get("sequential", False))

        # ── Clarification
        needs_clarification    = bool(parsed.get("needs_clarification", False))
        clarification_question = parsed.get("clarification_question") or None
        clarification_options  = parsed.get("clarification_options")  # None or list[str]

        # Guard: if clarification is needed, question must be present
        if needs_clarification and not clarification_question:
            print("[classifier] needs_clarification=true but no question supplied — ignoring")
            needs_clarification = False

        # Guard: options must be a non-empty list or None
        if clarification_options is not None:
            if not isinstance(clarification_options, list) or not clarification_options:
                clarification_options = None

        print(
            f"[classifier] intent={intent.value} | "
            f"docs={resolved_ids} | "
            f"tools={selected_tools} | "
            f"sequential={sequential} | "
            f"clarify={needs_clarification} | "
            f"reason={parsed.get('reasoning', '')}"
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

    except Exception as e:
        print(f"[classifier] Unexpected error while processing parsed output: {e}")
        return _SAFE_DEFAULT


# ── LangGraph node ────────────────────────────────────────────────────────────

async def classifier_node(state: ChatState) -> ChatState:
    print("[classifier_node] Running...")

    session_documents = state.get("session_documents", [])
    active_docs       = state.get("active_documents", [])
    user_clarification = state.get("user_clarification")
    clarification_history = state.get("clarification_history") or []


    query = state["user_input"]
    if clarification_history:
        qa_text = "\n\n".join(
            f"Q: {e['question']}\nA: {e['answer']}"
            for e in clarification_history
        )
        query = f"{query}\n\nClarification so far:\n{qa_text}"

    # classify_and_resolve never raises — safe to call without try/except
    (
        intent,
        resolved_document_ids,
        selected_tools,
        sequential,
        needs_clarification,
        clarification_question,
        clarification_options,
    ) = await classify_and_resolve(
        query=query,                       
        session_documents=session_documents,
        active_docs=active_docs,
        clarification_history=clarification_history,

    )

    return {
        **state,
        "intent":                 intent.value,
        "document_id":            resolved_document_ids,
        "selected_tools":         selected_tools,
        "sequential":             sequential,
        "clarification_needed":   needs_clarification,
        "clarification_question": clarification_question,
        "clarification_options":  clarification_options,
    }