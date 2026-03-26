import threading
import os

import chromadb
from langchain_chroma import Chroma
from app.REG.embedding_model import get_embeddings

_vectorstore_instance = None
_lock = threading.Lock()


def _get_chroma_client():
    """
    Returns a ChromaDB client.
    - In production (CHROMA_HOST set): connects to self-hosted Chroma ECS service over HTTP
    - In local dev (no CHROMA_HOST): falls back to local PersistentClient
    """
    host = os.getenv("CHROMA_HOST")
    port = int(os.getenv("CHROMA_PORT", "8000"))

    if host:
        print(f"Connecting to remote Chroma at {host}:{port}")
        return chromadb.HttpClient(
            host=host,
            port=port,
            settings=chromadb.Settings(anonymized_telemetry=False),
        )
    else:
        print("Using local Chroma PersistentClient (dev mode)")
        return chromadb.PersistentClient(
            path="./chroma_db",
            settings=chromadb.Settings(anonymized_telemetry=False),
        )


def get_vectorstore():
    global _vectorstore_instance

    # Lock prevents race conditions from concurrent Celery workers
    if _vectorstore_instance is None:
        with _lock:
            if _vectorstore_instance is None:
                print("Initializing Chroma vectorstore...")
                embeddings = get_embeddings()
                client = _get_chroma_client()

                _vectorstore_instance = Chroma(
                    client=client,
                    collection_name="rag_collection",
                    embedding_function=embeddings,
                    collection_metadata={"hnsw:space": "cosine"},
                )

    return _vectorstore_instance


def store_documents(docs):
    vectorstore = get_vectorstore()
    vectorstore.add_documents(docs)