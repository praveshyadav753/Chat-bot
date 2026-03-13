import asyncio
from typing import Union

from app.REG.query.utility import get_reranker, retrieve_context
from app.REG.Schema import RetrievalQuery, RetrievalUser
from app.core.config import settings
from app.REG.store.vec_store import get_vectorstore


async def Retrievel_pipeline(request: RetrievalQuery, user: RetrievalUser):

    results = await retrieve_context(request, user)
    if not results:
        return []

    docs = [doc for doc, _ in results]
    reranker = get_reranker()
    pairs = [(request.query, doc.page_content) for doc in docs]

    # FIX: reranker.predict() is a CPU-bound blocking call.
    # Running it directly in an async function blocks the entire event loop.
    # Use run_in_executor to offload it to a thread pool.
    loop = asyncio.get_event_loop()
    scores = await loop.run_in_executor(None, reranker.predict, pairs)

    reranked = sorted(
        zip(docs, scores),
        key=lambda x: x[1],
        reverse=True,
    )

    valid = [
        (doc, score)
        for doc, score in reranked
        if score >= settings.SIMILARITY_THRESHOLD
    ]

    if not valid:
        return []

    return [
        {
            "content": doc.page_content,
            "source": doc.metadata["source"],
            "page_number": doc.metadata["page_number"],
            "document_id": doc.metadata["document_id"],
            "score": float(score),
        }
        for doc, score in valid[: settings.max_context_chunks]
    ]


async def get_document_chunks(document_id: Union[str, list[str]], user: RetrievalUser):

    store = get_vectorstore()
    if isinstance(document_id, str):
        document_id = [document_id]

    results = store._collection.get(
        where={
            "$and": [
                {"document_id": {"$in": document_id}},
                {"uploaded_by": user.user_id},
                {"access_level": {"$lte": user.access_level}},
                {"department": user.department},
                {"classification": "internal"},
            ]
        }
    )

    if not results or not results.get("documents"):
        return []

    return [
        {
            "content": doc,
            "page_number": meta.get("page_number", 0),
            "document_id": meta.get("document_id"),
        }
        for doc, meta in zip(results["documents"], results["metadatas"])
    ]