import json
import redis.asyncio as redis

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from app.auth.utility import get_current_active_user
from app.core.config import settings

router = APIRouter(prefix="/api", tags=["Events"])

redis_client = redis.from_url(
    settings.REDIS_URL,
    db=2,
    decode_responses=True,
)

@router.get("/document-status-stream")
async def event_stream(
    request: Request,
    user=Depends(get_current_active_user),   
):
    
    # Each user gets their own Redis channel — no cross-user leakage
    channel = f"document_status:{user.id}"

    async def event_generator():
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(channel)

        try:
            async for message in pubsub.listen():
                if await request.is_disconnected():
                    break

                if message["type"] == "message":
                    yield {
                        "event": "update",
                        "data": message["data"],
                    }
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    return EventSourceResponse(event_generator())