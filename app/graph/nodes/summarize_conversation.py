from langchain_core.messages import HumanMessage, AIMessage, RemoveMessage
from app.graph.chatstate import ChatState
from app.graph.model import LLMFactory
import logging

logger = logging.getLogger(__name__)

EXCHANGES_TO_KEEP = 5  # keep last 5 exchanges = last 10 messages in checkpoint


async def summarize_conversation(state: ChatState) -> ChatState:
    print("[summarize_conversation] running...")

    messages        = state.get("messages", [])
    current_summary = state.get("summary") or ""

    summarizable = [m for m in messages if isinstance(m, (HumanMessage, AIMessage))]

    if not summarizable:
        print("[summarize_conversation] nothing to summarize")
        return {**state, "need_conversation_summary": False}

    conversation_text = "\n".join(
        f"{'User' if isinstance(m, HumanMessage) else 'Assistant'}: {m.content}"
        for m in summarizable
    )

    if current_summary:
        summary_instruction = (
            f"This is the summary of the conversation so far:\n{current_summary}\n\n"
            "Extend the summary by taking into account the new messages above:"
        )
    else:
        summary_instruction = (
            "Create a concise summary of the conversation above.\n"
            "Include:\n"
            "- User's main goals and questions\n"
            "- Key decisions or conclusions\n"
            "- Important facts, names, or numbers mentioned\n"
            "- Any follow-up items\n"
            "Write in 3rd person. Skip small talk. Use bullet points."
        )

    messages_for_llm = summarizable + [HumanMessage(content=summary_instruction)]

    try:
        llm = LLMFactory.create_llm(
            provider="gemini",
            model="gemini-2.5-flash-lite",
            temperature=0.3,
            fallbacks=[{"provider": "groq", "model": "groq-1b-instant"}],
        )

        response      = await llm.ainvoke(messages_for_llm)
        new_summary   = response.content.strip()

        # RemoveMessage AFTER successful summary 
        keep_count = EXCHANGES_TO_KEEP * 2  # 5 exchanges = 10 messages
        messages_to_delete = messages[:-keep_count] if len(messages) > keep_count else []
        deletions = [RemoveMessage(id=m.id) for m in messages_to_delete]

        print(f"[summarize_conversation] summary={len(new_summary)} chars "
              f"removed={len(deletions)} kept={keep_count}")

        return {
            **state,
            "summary":new_summary,
            "messages":deletions,  
            "conversation_messages":[],         
            "need_conversation_summary": False,
        }

    except Exception as e:
        logger.error(f"[summarize_conversation] failed: {e}")
        return {
            **state,
            "need_conversation_summary": False,
        }