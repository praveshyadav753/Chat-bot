import re
import uuid
from datetime import datetime
from collections import defaultdict
from typing import List
from langchain_unstructured import UnstructuredLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter




async def process_document(
    file_path: str,
    document_id: str,
    user_id: int,
    access_level: int = 1,
    department: str = "general",
) -> List[Document]:
    """
   

    Returns cleaned, structured, metadata-enriched Document chunks
    ready for vector DB storage.

    """

    try:
        loader = UnstructuredLoader(
            file_path,
            mode="elements",
            strategy="fast",
            languages=["eng"],
        )
        raw_elements = loader.load()
    except Exception as e:
        print(f"[ERROR] Failed to load file: {e}")
        return []

    if not raw_elements:
        return []

    document_id = document_id
    created_at = datetime.utcnow().isoformat()

    # -----------------------------
    # Group elements by page
    # -----------------------------
    pages_dict = defaultdict(list)

    for el in raw_elements:
        page_num = el.metadata.get("page_number", 1)
        category = el.metadata.get("category", "")

        # Skip obvious noise
        if category in ["Header", "Footer"]:
            continue

        content = el.page_content.strip()

        if not content:
            continue

        # Preserve tables explicitly
        if category == "Table":
            content = f"\n[TABLE_START]\n{content}\n[TABLE_END]\n"

        pages_dict[page_num].append(content)

    # -----------------------------
    # Page-Level Cleaning
    # -----------------------------
    page_documents = []

    for page_num, contents in pages_dict.items():
        page_text = "\n".join(contents)

        # Remove TOC dot leaders
        page_text = re.sub(r"\.{3,}", " ", page_text)

        # Normalize whitespace
        page_text = re.sub(r"[ \t]+", " ", page_text)
        page_text = re.sub(r"\n{3,}", "\n\n", page_text)
        page_text = page_text.strip()

        if len(page_text) < 100:
            continue

        page_documents.append(
            Document(
                page_content=page_text,
                metadata={
                    "source": file_path,
                    "document_id": document_id,
                    "page_number": page_num,
                    "uploaded_by": user_id,
                    "access_level": access_level,
                    "department": department,
                    "created_at": created_at,
                    "classification": "internal",
                },
            )
        )

    if not page_documents:
        return []

    # -----------------------------
    # Chunking (Character-based but structured)
    # -----------------------------
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,
        chunk_overlap=250,
        separators=["\n\n", "\n", " ", ""],
    )

    chunked_docs = text_splitter.split_documents(page_documents)

    # -----------------------------
    # Final Metadata Enrichment
    # -----------------------------
    final_chunks = []

    for idx, chunk in enumerate(chunked_docs):
        if len(chunk.page_content.strip()) < 150:
            continue

        chunk.metadata.update(
            {
                "chunk_id": f"{document_id}_chunk_{idx}",
                "chunk_index": idx,
                "embedding_model": "to_be_set_at_embedding_time",
            }
        )

        final_chunks.append(chunk)

    return final_chunks

# print(process_document("REG/llm.pdf",2,1))