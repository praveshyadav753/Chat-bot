import json
import redis.asyncio as redis
from app.core.config import settings

from fastapi import APIRouter
# from app.redis_client import redis_client
from sse_starlette.sse import EventSourceResponse

router = APIRouter(prefix="/api", tags=["Events"])

redis_client = redis.from_url(
    settings.REDIS_URL,
    db=2,
    decode_responses=True
)

@router.get("/document-status-stream")
async def event_stream():

    async def event_generator():

        pubsub = redis_client.pubsub()
        # await pubsub.subscribe(f"document_status:{session_id}")
        await pubsub.subscribe("document_status")

        async for message in pubsub.listen():

            if message["type"] == "message":
                print(message)

                yield {
                    "event": "update",
                    "data": message["data"],
                }

    return EventSourceResponse(event_generator())