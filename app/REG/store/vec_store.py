import threading

from langchain_chroma import Chroma  # from chroma import 
from app.REG.embedding_model import get_embeddings

_vectorstore_instance = None
_lock = threading.Lock()


def get_vectorstore():
    global _vectorstore_instance

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
    vectorstore.persist()
    # vectorstore.similarity_search_with_score()