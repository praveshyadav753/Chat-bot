async def get_document_chunks(document_id: str, user_id: str):
    """
    Fetch all chunks of a document with RBAC filtering.
    No similarity search.
    """

    results = collection.get(
        where={
            "document_id": document_id,
            "user_id": user_id
        }
    )

    return [
        {
            "content": doc,
            "page_number": meta["page_number"],
            "document_id": meta["document_id"],
        }
        for doc, meta in zip(results["documents"], results["metadatas"])
    ]