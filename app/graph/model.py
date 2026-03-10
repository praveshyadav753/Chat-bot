from enum import Enum
from typing import Annotated, Optional
import os
from dotenv import load_dotenv
from app.core.config import settings
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI


load_dotenv()

os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY")
os.environ["OPENAI_API_KEY"]  = os.getenv("OPENAI_API_KEY")
os.environ["GROQ_API_KEY"] =  os.getenv("GROQ_API_KEY")

class LLMProvider(str, Enum):
    OPENAI = "openai"
    GROQ = "groq"
    GEMINI = "gemini"


class LLMFactory:

    @staticmethod
    def create_llm(
        provider: Optional[LLMProvider] = None,          #str | None = None,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int | None = None,
        streaming:bool =False
    ):
        """
        Create LLM dynamically.
        If provider/model not passed → fallback to settings.
        """
        provider = provider if provider else settings.llm_provider

        if provider == "openai":
            model = model or settings.OPENAI_MODEL
            return ChatOpenAI(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                streaming=streaming,
            )

        elif provider == "groq":
            model = model or settings.GROQ_MODEL
            return ChatGroq(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                streaming=streaming,
            )

        elif provider == "gemini":
            model = model or settings.GEMINI_MODEL
            return ChatGoogleGenerativeAI(
                model=model,
                temperature=temperature,
                max_output_tokens=max_tokens,
                streaming=streaming,
                
            
            )

        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")
        

SYSTEM_PROMPT = """
You are an AI assistant.

Rules:
- Answer only using the provided context if available.
- If context is empty and question requires documents, say:
  "I don't have enough information."
- Do not hallucinate.
"""        