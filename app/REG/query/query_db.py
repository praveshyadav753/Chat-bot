# from typing import Annotated
# from app.REG.Schema import RetrievalQuery
import asyncio
from typing import Union

from app.REG.query.utility import get_reranker,retrieve_context
from app.REG.Schema import RetrievalQuery,RetrievalUser
from app.core.config import settings
from app.REG.store.vec_store import get_vectorstore

_reranker_instance = None

async def Retrievel_pipeline(request: RetrievalQuery, user: RetrievalUser):

    results = await retrieve_context(request,user)

    docs = [doc for doc,_ in results]
    reranker = get_reranker()
    pairs = [(request.query, doc.page_content) for doc in docs]

    scores = reranker.predict(pairs)

    reranked = sorted(
        zip(docs, scores),
        key=lambda x: x[1],
        reverse=True
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
            "score": score
        }
        for doc, score in valid[:settings.max_context_chunks]
    ]


# if __name__ == "__main__":
#     import asyncio
#     from app.REG.Schema import RetrievalQuery, RetrievalUser

#     test_request = RetrievalQuery(
#         query="What is llm?"
#     )

#     test_user = RetrievalUser(
#         user_id=1,
#         access_level=2,
#         department="general",
#         role="user"
#     )

#     result = asyncio.run(
#         Retrievel_pipeline(test_request, test_user)
#     )

#     print(result)




async def get_document_chunks(document_id: Union[str, list[str]], user:RetrievalUser):

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

    # print(results)
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

# if __name__ == "__main__":
#     user = RetrievalUser(user_id=2,access_level=1,department="general",role="moderator")
#     result= asyncio.run( get_document_chunks("2efca688-634b-43da-bf7d-ab714d8adbf3",user))
#     print(result)