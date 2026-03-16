# app/graph/tools/__init__.py
#
# Central tool registry.
# Rule: ONE import line per tool package. Nothing else lives here.
#
# To add a new tool:
#   1. Create app/graph/tools/<tool_name>/ package
#   2. Export the @tool function from its __init__.py
#   3. Add ONE import + ONE entry in ALL_TOOLS below

from app.tools.websearch.websearch import web_search
from app.tools.fetchUrl.fetch_url  import fetch_url
# from .currency   import convert_currency
# from .github     import github_reader

# Simple tools — classifier picks these (0 extra LLM calls) 
SIMPLE_TOOLS: list = [
    web_search,
    fetch_url,
    # convert_currency,
]

# These need reasoning to determine args (mode, path, recipients etc.)
COMPLEX_TOOLS: list = [
    # github_reader,
]

ALL_TOOLS: list = SIMPLE_TOOLS + COMPLEX_TOOLS

TOOL_MAP: dict = {t.name: t for t in ALL_TOOLS}