from enum import Enum
from typing import Optional
import os
from dotenv import load_dotenv
from app.core.config import settings
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI


load_dotenv()

if key := os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = key
if key := os.getenv("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = key
if key := os.getenv("GROQ_API_KEY"):
    os.environ["GROQ_API_KEY"] = key


class LLMProvider(str, Enum):
    OPENAI = "openai"
    GROQ = "groq"
    GEMINI = "gemini"


class LLMFactory:

    @staticmethod
    def _build_single(
        provider: str,
        model: str | None,
        temperature: float,
        max_tokens: int | None,
        streaming: bool,
    ):
        """Build a single LLM instance without fallbacks."""
        if provider == "openai":
            return ChatOpenAI(
                model=model or settings.OPENAI_MODEL,
                temperature=temperature,
                max_tokens=max_tokens,
                streaming=streaming,
            )
        elif provider == "groq":
            return ChatGroq(
                model=model or settings.GROQ_MODEL,
                temperature=temperature,
                max_tokens=max_tokens,
                streaming=streaming,
            )
        elif provider == "gemini":
            return ChatGoogleGenerativeAI(
                model=model or settings.GEMINI_MODEL,
                temperature=temperature,
                max_output_tokens=max_tokens,
                streaming=streaming,
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")

    @staticmethod
    def create_llm(
        provider: Optional[LLMProvider] = None,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int | None = None,
        streaming: bool = False,
        fallbacks: list[dict] | None = None,
    ):
        """
        Create LLM dynamically with optional fallbacks.

        fallbacks: list of dicts with provider/model to try on failure.

        Example:
            LLMFactory.create_llm(
                provider="openai",
                fallbacks=[
                    {"provider": "groq", "model": "llama-3.1-8b-instant"},
                    {"provider": "gemini"},
                ]
            )
        """
        provider = provider or settings.llm_provider

        primary = LLMFactory._build_single(provider, model, temperature, max_tokens, streaming)

        if not fallbacks:
            return primary

        fallback_llms = [
            LLMFactory._build_single(
                fb.get("provider", settings.llm_provider),
                fb.get("model", None),
                fb.get("temperature", temperature),
                fb.get("max_tokens", max_tokens),
                fb.get("streaming", streaming),
            )
            for fb in fallbacks
        ]

        return primary.with_fallbacks(fallback_llms)


SYSTEM_PROMPT = """
You are an AI assistant.

Rules:
- Answer only using the provided context if available.
- If context is empty and question requires documents, say:
  "I don't have enough information."
- Do not hallucinate.
"""