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
    # Generate or use existing session ID
    session_id = session_id or str(uuid4())
                        
    initial_state: ChatState = {
        "user_input": message,
        "user_id": user.id,
        "access_level": user.access_level,
        "department": user.department,
        "session_id": session_id,
        "blocked": False,
        "intent": None,
        "context": None,
        "retrieved_docs": [],
        "final_response": None,
    }

    async def event_generator():
        try:
            # ✅ Step 1: Send session ID as control message
            # This is NOT displayed - frontend filters it out
            yield f"data: SESSION:{session_id}\n\n"
            
            response_received = False
            
            async for step in graph.astream(initial_state):
                # ✅ Check for disconnection first
                if await request.is_disconnected():
                    print("Client disconnected")
                    break
                
                for node_name, state in step.items():
                    if node_name == "llm_node" and state.get("final_response"):
                        response_text = state["final_response"]
                        
                        # ✅ Only yield once
                        if not response_received:
                            print(f"LLM Response: {len(response_text)} characters")
                            
                            # ✅ CRITICAL FIX: Encode response as JSON to preserve formatting
                            # This ensures multiline text is sent as a single SSE event
                            # without breaking the SSE format
                            response_json = json.dumps({
                                "content": response_text.strip()
                            })
                            
                            # ✅ Send as single-line JSON (no internal newlines to break SSE)
                            yield f"data: {response_json}\n\n"
                            response_received = True

            # ✅ Step 2: Send completion marker
            yield f"data: [END]\n\n"

        except Exception as e:
            print(f"Chat streaming error: {e}")
            import traceback
            traceback.print_exc()
            yield f"data: [ERROR]\n\n"

    return EventSourceResponse(event_generator())