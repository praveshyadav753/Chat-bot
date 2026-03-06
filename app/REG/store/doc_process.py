import re
from collections import defaultdict
from langchain_unstructured import UnstructuredLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


# ── Cleaning helpers ──────────────────────────────────────────────────────────

def clean_text(text: str) -> str:
    """
    Normalises raw page text so it reads well as chatbot context.

    Steps
    -----
    1. Remove TOC dot leaders  e.g. "Chapter 1 ......... 12"
    2. Remove page-number-only lines
    3. Strip hyphenation at line breaks  e.g. "infor-\nmation" → "information"
    4. Collapse whitespace / newlines to a single space
    5. Remove non-printable / control characters
    """
    # 1. TOC dot leaders
    text = re.sub(r"\.{3,}", " ", text)

    # 2. Standalone page numbers (lone digits on a line)
    text = re.sub(r"(?m)^\s*\d{1,4}\s*$", " ", text)

    # 3. Soft-hyphen line breaks
    text = re.sub(r"-\s*\n\s*", "", text)

    # 4. Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # 5. Non-printable characters (keep standard ASCII + common Unicode)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    return text


# ── Core processor ────────────────────────────────────────────────────────────

def process_book_for_rag(
    file_path: str,
    user_id: int,
    chunk_size: int = 512,
    chunk_overlap: int = 128,
) -> list[Document]:
    """
    Load a PDF and return clean, well-sized chunks ready for a RAG chatbot.

    Parameters
    ----------
    file_path    : Path to the PDF file.
    user_id      : Owner identifier, stored in every chunk's metadata.
    chunk_size   : Target token/character size per chunk.
                   512–768 chars works well for most LLM context windows.
    chunk_overlap: Overlap between consecutive chunks to preserve context.

    Returns
    -------
    List of LangChain Documents with metadata:
        source, page_number, user_id, chunk_id, chunk_index, total_chunks
    """

    # ── 1. Load ───────────────────────────────────────────────────────────────
    try:
        loader = UnstructuredLoader(
            file_path,
            mode="elements",
            strategy="fast",
            languages=["eng"],
        )
        raw_elements = loader.load()
    except Exception as exc:
        print(f"[RAG] Error loading '{file_path}': {exc}")
        return []

    if not raw_elements:
        print("[RAG] No elements extracted from file.")
        return []

    # ── 2. Group by page, drop noise categories ───────────────────────────────
    _NOISE_CATEGORIES = {"Header", "Footer", "PageBreak", "PageNumber"}

    pages_dict: dict[int, list[str]] = defaultdict(list)
    for el in raw_elements:
        category = el.metadata.get("category", "")
        if category in _NOISE_CATEGORIES:
            continue
        page_num = el.metadata.get("page_number", 1)
        pages_dict[page_num].append(el.page_content)

    # ── 3. Build one Document per page ───────────────────────────────────────
    _MIN_PAGE_CHARS = 80   # ignore near-empty pages

    page_docs: list[Document] = []
    for page_num in sorted(pages_dict):
        raw_text = " ".join(pages_dict[page_num])
        cleaned  = clean_text(raw_text)

        if len(cleaned) < _MIN_PAGE_CHARS:
            continue

        page_docs.append(
            Document(
                page_content=cleaned,
                metadata={
                    "source":      file_path,
                    "page_number": page_num,
                    "user_id":     user_id,
                },
            )
        )

    if not page_docs:
        print("[RAG] All pages were filtered out as noise/empty.")
        return []

    # ── 4. Split into RAG-sized chunks ────────────────────────────────────────
    # Sentence-aware separators → chunks end on natural boundaries,
    # which keeps context coherent for the chatbot.
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", "? ", "! ", " ", ""],
    )
    raw_chunks = splitter.split_documents(page_docs)

    # ── 5. Filter & label chunks ──────────────────────────────────────────────
    _MIN_CHUNK_CHARS = 120   # drop slivers with no real content

    final_chunks: list[Document] = []
    for i, chunk in enumerate(raw_chunks):
        content = chunk.page_content.strip()
        if len(content) < _MIN_CHUNK_CHARS:
            continue

        chunk.page_content = content
        chunk.metadata.update(
            {
                "chunk_id":    f"u{user_id}_c{i:05d}",
                "chunk_index": i,
            }
        )
        final_chunks.append(chunk)

    # Back-fill total_chunks now that we know the final count
    total = len(final_chunks)
    for chunk in final_chunks:
        chunk.metadata["total_chunks"] = total

    # print(f"[RAG] ✓ {total} chunks ready from '{file_path}' (user {user_id})")
    return final_chunks


# ── Quick sanity-check ────────────────────────────────────────────────────────

if __name__ == "__main__":
    FILE    = "REG/llm.pdf"
    USER_ID = 2

    docs = process_book_for_rag(FILE, USER_ID)
    print(docs)

    # if docs:
    #     print(f"\nFirst chunk preview\n{'─' * 40}")
    #     print(docs[0].page_content[:300])
    #     print(f"\nMetadata: {docs[0].metadata}")