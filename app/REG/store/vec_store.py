import threading

from langchain_chroma import Chroma
from app.REG.embedding_model import get_embeddings

_vectorstore_instance = None
_lock = threading.Lock()


def get_vectorstore():
    global _vectorstore_instance

    # use the lock to prevent race conditions from concurrent Celery workers
    if _vectorstore_instance is None:
        with _lock:
            if _vectorstore_instance is None:
                print("Initializing Chroma vectorstore...")
                embeddings = get_embeddings()
                _vectorstore_instance = Chroma(
                    collection_name="rag_collection",
                    embedding_function=embeddings,
                    persist_directory="./chroma_db",
                    collection_metadata={"hnsw:space": "cosine"},
                )

    return _vectorstore_instance


def store_documents(docs):
    vectorstore = get_vectorstore()
    vectorstore.add_documents(docs)
  