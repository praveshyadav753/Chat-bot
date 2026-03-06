import json
import redis.asyncio as redis

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

router = APIRouter(prefix="/api", tags=["Events"])

redis_client = redis.Redis(host="localhost", port=6379, decode_responses=True)


@router.get("/document-status-stream")
async def event_stream():

    async def event_generator():

        pubsub = redis_client.pubsub()
        await pubsub.subscribe("events")

        async for message in pubsub.listen():

            if message["type"] == "message":
                print(message)

                yield {
                    "event": "update",
                    "data": message["data"],
                }

    return EventSourceResponse(event_generator())