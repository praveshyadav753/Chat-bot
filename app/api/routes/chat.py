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

    session_id = session_id or str(uuid4())
                        
    initial_state: ChatState = {
        "user_input": message,
        "user_id": user.id,
        "access_level":user.access_level,
        "department":user.department,
        "session_id": session_id,
        "blocked": False,
        "intent": None,
        "context": None,
        "retrieved_docs": [],
        "final_response": None,
        
    }

    async def event_generator():
        try:
            async for step in graph.astream(initial_state):

                # step is like: {"node_name": updated_state}
                for node_name, state in step.items():

                    # Stream only when LLM node updates response
                    if node_name == "llm_node" and state.get("final_response"):
                        print(state["final_response"])
                        yield {
                            "event": "message",
                            "data": state["final_response"],
                        }

                if await request.is_disconnected():
                    break

            # Send session ID at end
            yield {
                "event": "end",
                "data": f"SESSION:{session_id}",
            }

        except Exception as e:
            print(e)
            yield {
                "event": "error",
                "data": "Internal server error",
            }

    return EventSourceResponse(event_generator())
