# RAG Chatbot

A production-grade AI chatbot built on **LangGraph** that answers questions from uploaded documents, performs real-time web searches, and maintains persistent conversation history. Responses stream token-by-token to the browser via SSE.

---

## What it does

- Upload documents (PDF, DOCX, TXT) → ask questions from them
- Web search, URL reading, currency conversion via external tools
- Multi-turn conversation with persistent history (survives page refresh)
- Streams responses in real time with per-node progress indicators
- Role-based access — department and access level scoped document retrieval

---

## Stack

| Layer | Technology | Why |
|---|---|---|
| LLM | Gemini 2.5 Flash Lite | Fast, cheap, 1M token context |
| Orchestration | LangGraph | Stateful graph — loops, branching, memory |
| API | FastAPI | Async, SSE support, Python native |
| Database | PostgreSQL (AWS RDS) | Checkpointer + vectors + app data in one |
| Vector search | pgvector | Reuses Postgres — no extra service |
| Background jobs | Celery + Redis | Non-blocking document ingestion |
| Streaming | SSE | Simpler than WebSockets for one-way push |
| Auth | JWT | Stateless, works with async FastAPI |
| Migrations | Alembic | Schema versioning |

---

## Architecture

Every user message runs through a LangGraph directed graph:

```
START
  → input_guardrails          # safety check
  → check_messages_length     # rolling summarization trigger
  → document_context          # load session documents
  → classify                  # intent + doc resolution + tool selection (1 LLM call)
      ├── factual           → rag_node → llm_node
      ├── doc_analysis      → document_analysis_node → llm_node
      ├── summary           → summarize_document_node → llm_node
      ├── tool (simple)     → tool_node → llm_node
      ├── tool (complex)    → llm_node_with_tools → complex_tool_node → llm_node
      ├── conversation      → llm_node
      └── out_of_scope      → reject
  → persist_data              # Celery background — non-blocking
END
```

---

## Project structure

```
app/
  main.py                   # FastAPI app factory, graph init on startup
  celery_app.py             # Celery instance
  api/routes/
    chat.py                 # SSE streaming endpoint
    documents.py            # Upload + status endpoints
    auth.py                 # Login / logout / register
    update__event.py        # Document status SSE stream
  graph/
    builder.py              # StateGraph definition + compile
    chatstate.py            # ChatState TypedDict
    routes.py               # Routing functions
    model.py                # LLMFactory
    nodes/                  # One file per graph node
      classifier.py         # Intent + doc resolution + tool selection
      llm.py                # Final generation + streaming
      rag.py                # pgvector similarity search
      tool_node.py          # Classifier-driven tool executor
      summarize_conversation.py
      input_guardrails.py
      ...
  tools/
    websearch/              # Tavily (primary) + DuckDuckGo (fallback)
    fetchUrl/               # httpx + BeautifulSoup
  REG/                      # RAG pipeline
    embedding_model.py      # Google text-embedding-004
    store/                  # Parse → chunk → embed → store
    query/                  # Embed query → pgvector search
  models/                   # SQLAlchemy ORM models
  tasks/                    # Celery task definitions
  security/                 # Input validation, injection detection
  core/
    checkpointer.py         # AsyncPostgresSaver setup
    config.py               # Environment variables
migrations/                 # Alembic versions
```

---

## Setup

### Requirements

- Python 3.12+
- PostgreSQL 15+ with pgvector extension enabled
- Redis

### Environment variables

```env
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db?ssl=require
DATABASE_URL1=postgresql://user:pass@host:5432/db?sslmode=require
REDIS_URL=redis://localhost:6379/0
TAVILY_API_KEY=tvly-...
GOOGLE_API_KEY=...
SECRET_KEY=...
ALGORITHM=HS256
```

### Run

```bash
# Install
pip install -r requirements.txt

# Database migrations
alembic upgrade head

# Enable pgvector
psql -d yourdb -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Start API
uvicorn app.main:app --reload --port 8000

# Start Celery worker (separate terminal)
celery -A app.celery_app worker --loglevel=info
```

---

## Key design decisions

**Why LangGraph over plain LangChain chains?**
LangChain chains are linear — no loops, no branching, no shared state across steps. LangGraph models the workflow as a directed graph which gives us conditional routing (different paths for RAG vs tools vs conversation), cycles (ReAct tool loop), and a persistent checkpointer for free.

**Why pgvector over Pinecone / Chroma / Weaviate?**
pgvector runs inside the existing PostgreSQL instance — no extra service to deploy, no extra cost, no extra network hop. At this scale (< 1M vectors) pgvector cosine similarity performance is sufficient. A dedicated vector DB adds operational complexity with no meaningful benefit.

**Why SSE over WebSockets?**
SSE is unidirectional (server → client) which is exactly what token streaming needs. WebSockets are bidirectional — useful for the chat input channel but overkill for streaming output. SSE works over HTTP/1.1, has a native browser `EventSource` API, auto-reconnects, and needs no library.

**Why Celery for document ingestion?**
Document processing (parse → chunk → embed → store) takes 5–30 seconds. Blocking the FastAPI async event loop for this would freeze all other requests. Celery workers run in separate OS processes and can block freely.

**Why classifier does 3 jobs in 1 LLM call?**
The classifier determines intent, resolves which documents are relevant, and selects which tools to run. Splitting these into 3 separate LLM calls would triple the latency on every message. One prompt with all context does all three.

**Why hybrid tool routing?**
Simple tools (web search, currency, URL fetch) have obvious args extractable directly from the query — no LLM needed to pick them. The classifier selects them for 0 extra LLM calls. Complex tools (GitHub reader, email) need the LLM to reason about args like `mode`, `path`, or `recipients`, so those use `bind_tools` and LangGraph's prebuilt `ToolNode`.

---

## Memory model

**Short-term (per conversation)** — LangGraph `AsyncPostgresSaver` checkpointer saves full state after every node. History is restored automatically on each message via `thread_id = session_id`. No manual DB queries needed.

**Rolling summarization** — when message count exceeds 10, old messages are summarized and removed. The summary is injected as a `SystemMessage` so the LLM retains context without the full token cost.

**Time travel** — because every node execution is checkpointed, the graph supports: undo (rewind to past checkpoint), branch (fork to new session), and replay (re-run exact failing state for debugging).

---

## RAG pipeline

```
Upload
  → FastAPI saves file, returns document_id immediately
  → Celery: parse (PyMuPDF / python-docx) → chunk (~500 tokens)
          → embed (Google text-embedding-004)
          → store in pgvector
  → status: PROCESSING → READY
  → browser notified via SSE

Query
  → embed user query
  → pgvector: cosine similarity search filtered by resolved document_ids
  → top-K chunks → state["context"]
  → injected into LLM prompt just before user query (recency bias)
```

---

## Streaming events

All SSE events are JSON:

```
{"type": "session",  "session_id": "..."}   first event
{"type": "progress", "node": "rag_node"}    per graph node
{"type": "chunk",    "content": "Hello"}    per LLM token
{"type": "end"}                             stream complete
{"type": "error"}                           exception
```

---

## Known gotchas

- `**state` must always be spread **first** in node return dicts — spreading it last silently overwrites your new keys
- `RemoveMessage` must be issued **after** a successful summary LLM call — issuing it before means messages are lost if the LLM call fails
- Celery tasks must use **sync** SQLAlchemy sessions — never `asyncio.run()` inside a Celery task
- `ToolNode` requires the real `RunnableConfig` (injected by LangGraph as second param) — a manually constructed config dict causes `Missing required config key` errors
- Gemini requires at least one `HumanMessage` in the messages list — a list of only `SystemMessage` raises `contents are required`