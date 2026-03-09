from app.graph.chatstate import ChatState
from langchain_core.messages import HumanMessage, AIMessage


MAX_HISTORY_MESSAGES = 10
MESSAGES_TO_KEEP = 5
SUMMARY_EVERY_N_MESSAGES =8

async def check_message_length_node(state: ChatState) -> ChatState:
    print("check_message_length_node...")

    messages = state.get("messages", [])
    message_count = len(messages)

    needs_summary = message_count >= SUMMARY_EVERY_N_MESSAGES
    if needs_summary:

        old_messages = messages[:-MESSAGES_TO_KEEP]
        recent_messages = messages[-MESSAGES_TO_KEEP:]

        conversation_messages = []

        for msg in old_messages:
            if isinstance(msg, HumanMessage):
                role = "user"
            elif isinstance(msg, AIMessage):
                role = "assistant"
            else:
                continue

            conversation_messages.append(
                {
                    "role": role,
                    "content": msg.content
                }
            )

        return {
                **state,
                "messages": recent_messages,  
                "conversation_messages": conversation_messages, 
                "summary_type": "conversation",
                "need_conversation_summary": True, 
                "message_count": message_count,
            }
    else:
       
        
        return {
            **state,
            "need_conversation_summary": False,  
            "message_count": message_count,
        }