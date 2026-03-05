# embeddings_factory.py

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_openai import OpenAIEmbeddings

_embeddings_instance = None


def get_embeddings(provider: str = "local"):
    global _embeddings_instance

    if _embeddings_instance is not None:
        return _embeddings_instance

    if provider == "local":
        print("Loading local embedding model...")
        _embeddings_instance = HuggingFaceEmbeddings(
            model_name="BAAI/bge-base-en-v1.5",
            encode_kwargs={"normalize_embeddings": True},
        )

    elif provider == "openai":
        print("Using OpenAI embeddings...")
        _embeddings_instance = OpenAIEmbeddings(
            model="text-embedding-3-small"
        )

    else:
        raise ValueError("Invalid embedding provider")

    return _embeddings_instance