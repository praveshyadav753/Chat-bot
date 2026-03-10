from typing import TypedDict, List, Optional, Dict, Any
from typing_extensions import Annotated
from langgraph.graph import add_messages
# from model import llm


class ChatState(TypedDict):
    
    messages: Annotated[list, add_messages]
    message_count :int
    summary: Optional[str]
    summary_type: Optional[str]   # document | conversation

    conversation_messages: Optional[list]
    session_summary: Optional[str]
    need_conversation_summary: bool
    user_input: str
    prompt :str 
    final_response: Optional[str]

  
    user_id: str
    session_id: str
    role:str
    access_level:int
    department : str

  
    intent: Optional[str]  # RAG | TOOL | DIRECT_LLM
    requires_retrieval: bool
   
    document_id: Optional[List[str]]
    session_documents : Optional[List[dict]]
    active_documents :Optional[list[dict]]
    retrieved_docs: Optional[List[Dict[str, Any]]]
    has_document : bool
    document_ready:bool

    context: Optional[str]
    retrieval_confidence: Optional[float]

    
    tool_calls: Optional[List[Dict[str, Any]]]
    tool_results: Optional[List[str]]

   
    is_valid: Optional[bool]

    requires_approval: bool
    approved: Optional[bool]
    block_reason:str    
    injection_detected: bool
    out_of_scope: bool
    validation_error: Optional[str]
   
    cache_hit: bool
    status: str  # STARTED | CLASSIFIED | RETRIEVED | RERANKED | GENERATED | VALIDATED | TOOL_RUNNING | WAITING_APPROVAL | COMPLETED | ERROR
    error: Optional[str]
    debug_error :Optional[str]