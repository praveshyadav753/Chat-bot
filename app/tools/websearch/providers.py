# app/graph/tools/web_search/providers.py
#
# Private — NOT exported from __init__.py
# Pure search logic. No @tool, no LangChain imports.
# tool.py calls search() and doesn't care which provider ran.
#
# Provider priority:
#   1. Tavily  — structured results + synthesized answer (preferred)
#   2. DuckDuckGo — free fallback, no API key needed

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def search(query: str, user_id: Optional[str] = None) -> str:
    """
    Try Tavily first. Fall through to DuckDuckGo on any failure.
    Never returns empty — always returns something usable.

    Args:
        query:   The search query string.
        user_id:  — for logging which user triggered the search.

    Returns:
        Formatted string of results for LLM consumption.
    """
    log_prefix = f"[web_search] user={user_id or 'unknown'}"

    tavily_error: Optional[Exception] = None
    ddg_error:    Optional[Exception] = None

    try:
        from tavily import TavilyClient

        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            raise ValueError("TAVILY_API_KEY not set in environment")

        client  = TavilyClient(api_key=api_key)
        results = client.search(
            query=query,
            search_depth="basic",
            max_results=4,
            include_answer=True,
        )

        output = []

        if results.get("answer"):
            output.append(f"**Direct Answer:** {results['answer']}\n")

        for r in results.get("results", []):
            output.append(
                f"**{r.get('title', '')}**\n"
                f"{r.get('content', '')}\n"
                f"Source: {r.get('url', '')}"
            )

        if output:
            logger.info(f"{log_prefix} Tavily succeeded — {len(output)} results")
            return "\n\n---\n\n".join(output)

        # Tavily responded but with no usable content
        raise ValueError("Tavily returned empty results")

    except Exception as e:
        tavily_error = e
        logger.warning(f"{log_prefix} Tavily failed: {e} — falling back to DuckDuckGo")

    #  DuckDuckGo fallback
    try:
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=4))

        if not results:
            raise ValueError("DuckDuckGo returned empty results")

        logger.info(f"{log_prefix} DuckDuckGo succeeded — {len(results)} results")
        return "\n\n---\n\n".join(
            f"**{r.get('title', '')}**\n"
            f"{r.get('body', '')}\n"
            f"Source: {r.get('href', '')}"
            for r in results
        )

    except Exception as e:
        ddg_error = e
        logger.error(f"{log_prefix} DuckDuckGo also failed: {e}")

    return (
        f"Web search is currently unavailable.\n"
        f"Tavily error: {tavily_error}\n"
        f"DuckDuckGo error: {ddg_error}"
    )