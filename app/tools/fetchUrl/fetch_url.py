# app/graph/tools/fetch_url/tool.py

import re
from typing import Annotated
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from .extractor import fetch_and_extract


def _looks_like_url(text: str) -> bool:
    return bool(re.match(r"https?://\S+", text.strip()))


@tool
def fetch_url(
    url: str,
    state: Annotated[dict, InjectedState],
) -> str:
    """
    Fetch and read the content of a web page from a URL.
    Use when the user shares a link and wants it read, summarized, or analyzed.
    Input must be a full URL starting with http:// or https://
    """
    url = url.strip()

    if not _looks_like_url(url):
        return f"Invalid URL: '{url}'. Must start with http:// or https://"

    user_id = state.get("user_id")
    return fetch_and_extract(url)