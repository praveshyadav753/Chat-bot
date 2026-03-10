import os
import json
from typing import List, Optional
from uuid import uuid4
from app.models.connection import get_db
import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sse_starlette.sse import EventSourceResponse

from app.tasks.ingest_document import store_rag_doc
from app.auth.utility import get_current_active_user
from app.graph.builder import graph
from app.graph.chatstate import ChatState
from app.models.document import Document

chat_router = APIRouter(prefix="/api/chat", tags=["Chat Routes"])
templates = Jinja2Templates(directory="app/templates")


@chat_router.get("/", response_class=HTMLResponse)
async def chat_home(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})


@chat_router.post("/stream")
async def stream_chat(
    request: Request,
    user=Depends(get_current_active_user),
    message: str = Form(...),
    session_id: Optional[str] = Form(None),
    active_documents: Optional[str] =Form(None),
    db=Depends(get_db)
):
    """
    Stream chat responses via Server-Sent Events (SSE).
    
    Properly handles multiline responses by encoding them as JSON.
    
    Yields:
        - data: SESSION:{session_id}\n\n - Session ID (control message)
        - data: {"content": "..."}\n\n - Response content as JSON (single line)
        - data: [END]\n\n - End marker
    """
    session_id = session_id or str("abc")
    parsed_active_documents = []
    if active_documents:
        try:
            parsed_active_documents = json.loads(active_documents)
        except (json.JSONDecodeError, TypeError):
            parsed_active_documents = []
    print(f"recenty uploaded docs:{parsed_active_documents}")
    print("-----------------------------------------")
                        
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
    }

    async def event_generator():
        try:
            yield f"data: SESSION:{session_id}\n\n"

            async for msg, metadata in graph.astream(        
                initial_state,
                stream_mode="messages",
            ):
                if await request.is_disconnected():
                    print("Client disconnected")
                    break

                if (
                    msg.content
                    and metadata.get("langgraph_node") == "llm_node"
                ):
                    chunk_data = json.dumps({"content": msg.content})
                    yield f"data: {chunk_data}\n\n"

            yield "data: [END]\n\n"

        except Exception as e:
            print(f"Chat streaming error: {e}")
            import traceback
            traceback.print_exc()
            yield "data: [ERROR]\n\n"

    return EventSourceResponse(event_generator())
