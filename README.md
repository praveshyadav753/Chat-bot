# chatbot

A project created with FastAPI CLI.

## Quick Start

### Start the development server

```bash
uv run fastapi dev
```

Visit http://localhost:8000

### Deploy to FastAPI Cloud

> FastAPI Cloud is currently in private beta. Join the waitlist at https://fastapicloud.com

```bash
uv run fastapi login
uv run fastapi deploy
```

## Project Structure

- `main.py` - Your FastAPI application
- `pyproject.toml` - Project dependencies

## Learn More

- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [FastAPI Cloud](https://fastapicloud.com)
# Chat-bot



workflow:

load_state (load from DB with history)
  ↓
track_messages 
  ├─ messages = [old1, old2, ..., new]
  ↓
input_guardrails (security check)
  ├─ OK → continue
  └─ BLOCKED → reject
  ↓
check_message_length
  ├─ Always evaluates 
  ├─ If >= 8 messages: set need_conversation_summary = True
  └─ Always continues (no early return)
  ↓
message_router
  ├─ If need_conversation_summary:
  │   └─ → summary_node 
  │      └─ Summarizes old messages
  │      └─ Keeps last 5 recent
  │      └─ Returns to classify
  └─ Otherwise → document_context
  ↓
classify (determine intent)
  ├─ factual → rag_node
  ├─ summary → summary_node
  └─ conversation → llm_node
  ↓
llm_node (generate response)
  ↓
persist_message 
  ├─ Save to DB
  ├─ Preserve messages in state 
  ├─ Update summary 
  └─ Continue with full history
  ↓
END