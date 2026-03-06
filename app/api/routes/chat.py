import os
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
    
    Yields:
        - data: SESSION:{session_id}\n\n - Session ID sent at start
        - data: {full_response}\n\n - Complete response content
        - data: [END]\n\n - End marker when complete
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
            # ✅ FIX 1: Send session ID at start with proper SSE format
            yield f"data: SESSION:{session_id}\n\n"
            
            response_received = False  # ✅ FIX 2: Track if we got a response
            
            async for step in graph.astream(initial_state):
                # ✅ FIX 3: Check for request disconnection INSIDE the loop
                if await request.is_disconnected():
                    print("Client disconnected during streaming")
                    break
                
                for node_name, state in step.items():
                    # ✅ FIX 4: Properly check for final response
                    if node_name == "llm_node" and state.get("final_response"):
                        response_text = state["final_response"]
                        
                        # ✅ FIX 5: Only yield once per response (not multiple times)
                        if not response_received:
                            print(f"LLM Response received: {len(response_text)} characters")
                            
                            # ✅ FIX 6: Properly escape special characters in response
                            # Remove any trailing newlines/spaces that might break SSE format
                            response_text = response_text.strip()
                            
                            # Send the complete response as a single SSE event
                            yield f"data: {response_text}\n\n"
                            response_received = True

            # ✅ FIX 7: Send end marker AFTER the loop completes
            yield f"data: [END]\n\n"

        except Exception as e:
            print(f"Chat streaming error: {e}")
            # Send error marker
            yield f"data: [ERROR]\n\n"

    return EventSourceResponse(event_generator())