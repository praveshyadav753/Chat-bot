import json
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sse_starlette.sse import EventSourceResponse

from app.auth.utility import get_current_active_user
from app.graph.chatstate import ChatState
from app.models.connection import get_db
from langgraph.types import Command

chat_router = APIRouter(prefix="/api/chat", tags=["Chat Routes"])
templates = Jinja2Templates(directory="app/templates")
templates.env.auto_reload = True


@chat_router.get("/", response_class=HTMLResponse)
async def chat_home(
    request: Request,
    user=Depends(get_current_active_user),
):
    return templates.TemplateResponse(
        "chat.html",
        {
            "request": request,
            "is_authenticated": True,
        },
    )


@chat_router.post("/stream")
async def stream_chat(
    request: Request,
    user=Depends(get_current_active_user),
    message: str = Form(...),
    session_id: Optional[str] = Form(None),
    active_documents: Optional[str] = Form(None),
    is_clarification: bool = Form(False),
    db=Depends(get_db),
):
    session_id = session_id 
    print(f"[chat] received message: {message!r} session_id={session_id} is_clarification={is_clarification}")

    parsed_active_documents = []
    if active_documents:
        try:
            parsed_active_documents = json.loads(active_documents)
        except (json.JSONDecodeError, TypeError):
            parsed_active_documents = []

    print(f"[chat] session={session_id} | is_clarification={is_clarification}")
    print(f"[chat] active_docs={parsed_active_documents}")

    if is_clarification:
        initial_state = Command(resume=message)
    else:
        initial_state: ChatState = {
            "user_input": message,
            "user_id": user.id,
            "role": user.role.value if user.role else "user",
            "access_level": user.access_level,
            "department": user.department,
            "session_id": session_id,
            "blocked": False,
            "intent": None,
            "context": None,
            "retrieved_docs": [],
            "final_response": None,
            "active_documents": parsed_active_documents,
            "clarification_history": [],  
        }

    async def event_generator():
        try:
            yield json.dumps({"type": "session", "session_id": session_id})

            graph = request.app.state.graph

            async for mode, chunk in graph.astream(
                initial_state,
                stream_mode=["messages", "updates"],
                config={"configurable": {"thread_id": session_id}},
            ):
                if await request.is_disconnected():
                    print("[chat] client disconnected")
                    break
                if mode == "messages":
                    msg, metadata = chunk
                    if msg.content and "llm_response" in metadata.get("tags", []):
                        yield json.dumps({"type": "chunk", "content": msg.content})

                elif mode == "updates":

                    if "__interrupt__" in chunk:
                        interrupt_data = chunk["__interrupt__"][0].value
                        question = interrupt_data.get("question", "")
                        options  = interrupt_data.get("options")   # None or list[str]

                        print(f"[chat] interrupt → question={question!r} options={options!r}")

                        yield json.dumps({
                            "type":     "clarification",
                            "question": question,
                            "options":  options,
                        })
                        return  # stop streaming — frontend takes over

                    node_name = list(chunk.keys())[0]
                    yield json.dumps({"type": "progress", "node": node_name})

            yield json.dumps({"type": "end"})

        except Exception as e:
            print(f"[chat] streaming error: {e}")
            import traceback
            traceback.print_exc()
            yield json.dumps({"type": "error"})

    return EventSourceResponse(event_generator())