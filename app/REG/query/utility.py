from chromadb import Where
from sentence_transformers import CrossEncoder
from app.REG.store.vec_store import get_vectorstore
from app.core.config import settings
from app.REG.Schema import RetrievalQuery, RetrievalUser


_reranker_instance = None


def get_reranker():
    global _reranker_instance
    if _reranker_instance is None:
        _reranker_instance = CrossEncoder("BAAI/bge-reranker-base")
    return _reranker_instance


async def retrieve_context(request, user):
    store = get_vectorstore()
    results = store.similarity_search_with_score(
        query=request.query,
        k=settings.initial_retrieval_k,
        filter={
            "$and": [
                {"access_level": {"$lte": user.access_level}},
                {"department": user.department},
                {"classification": "internal"},
            ]
        },
    )
    if not results:
        return []
    
    return results


