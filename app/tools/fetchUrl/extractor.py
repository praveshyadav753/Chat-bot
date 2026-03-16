# Fetches a URL and returns clean readable text.
import logging
from typing import Optional

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Tags that never contain useful article content
_NOISE_TAGS = [
    "script", "style", "nav", "footer", "header",
    "aside", "advertisement", "noscript", "iframe",
]

MAX_CHARS = 8_000  # cap output so it fits in LLM context


def fetch_and_extract(url: str) -> str:
    """
    Fetch a URL and return clean readable text.
    Returns error string on failure — never raises.

    Args:
        url: Full URL including scheme (https://...)

    Returns:
        Clean text content, capped at MAX_CHARS.
        Error message string if fetch fails.
    """
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (compatible; LangGraphBot/1.0)"
            )
        }
        response = httpx.get(url, headers=headers, timeout=10, follow_redirects=True)
        response.raise_for_status()

    except httpx.TimeoutException:
        logger.warning(f"[fetch_url] timeout for {url}")
        return f"Could not fetch URL: request timed out after 10s."

    except httpx.HTTPStatusError as e:
        logger.warning(f"[fetch_url] HTTP {e.response.status_code} for {url}")
        return f"Could not fetch URL: HTTP {e.response.status_code}."

    except Exception as e:
        logger.error(f"[fetch_url] unexpected error for {url}: {e}")
        return f"Could not fetch URL: {e}"

    soup = BeautifulSoup(response.text, "html.parser")

    # Remove noise tags in place
    for tag in soup(  _NOISE_TAGS):
        tag.decompose()

    # Try article/main first — best signal for actual content
    content_el = (
        soup.find("article")
        or soup.find("main")
        or soup.find(id="content")
        or soup.find(class_="content")
        or soup.body
    )

    if not content_el:
        return "Could not extract readable content from this URL."

    # Get text, collapse whitespace
    text = content_el.get_text(separator="\n", strip=True)
    lines = [line for line in text.splitlines() if line.strip()]
    clean = "\n".join(lines)

    if not clean:
        return "Page appears to have no readable text content."

    # Cap length with a note if truncated
    if len(clean) > MAX_CHARS:
        clean = clean[:MAX_CHARS]
        clean += f"\n\n[Content truncated at {MAX_CHARS} characters]"

    logger.info(f"[fetch_url] extracted {len(clean)} chars from {url}")
    return clean