from app.graph.chatstate import ChatState
from app.REG.query.query_db import get_document_chunks
from app.REG.Schema import RetrievalUser
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
import logging
from app.graph.model import LLMFactory

logger = logging.getLogger(__name__)



async def summarize_conversation(state: ChatState) -> ChatState:

    messages = state.get("conversation_messages", [])
    current_summary = state.get("summary") or ""
    user_input = state.get("user_input")

    if not messages:
        print("  → No old messages to summarize")
        return state

    history_text = ""
    for msg in messages:
        role = msg.get("role", "").upper()
        content = msg.get("content", "")
        
        # Truncate very long messages
        # if len(content) > 300:
        #     content = content[:300] + "..."
        
        history_text += f"{role}: {content}\n\n"

    print(f"  → Conversation history: {len(history_text)} chars")
    print(f"  → Current summary: {len(current_summary)} chars")

    #  Use LLM to create/update summary
    try:
        llm = LLMFactory.create_llm(
            provider="gemini",
            model="gemini-2.5-flash-lite",
            temperature=0.3,
        )

        prompt = f"""
You are a conversation summarizer. Your job is to create a concise summary that preserves important context.

{'PREVIOUS SUMMARY (update this):\n' + current_summary + '\n\n' if current_summary else 'CREATE A NEW SUMMARY:\n\n'}

CONVERSATION TO SUMMARIZE:
{history_text}

RULES:
1. Max 350 words
2. Include:
   - User's main goals and questions
   - Key decisions or conclusions
   - Important facts, names, or numbers
   - Any follow-up items mentioned
3. Write in 2nd person (about "the user")
4. Remove small talk and greetings
5. If previous summary exists, update it with new information
6. Use bullet points for clarity
7. Focus on what's important for context

SUMMARY (350 words max):
"""

        response = await llm.ainvoke([HumanMessage(content=prompt)])
        new_summary = response.content.strip()

        print(f"Summary created: {len(new_summary)} chars")

        return {
            **state,
            "summary": new_summary, 
            "user_input": user_input, 
            "summary_type": None,  
        }

    except Exception as e:
        logger.error(f"Error summarizing conversation: {str(e)}")
        print(f" Summarization error: {str(e)}")
        
        # Continue without updating summary
        return {
            **state,
            "user_input": user_input,
        }