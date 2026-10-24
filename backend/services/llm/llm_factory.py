# """LLM provider factory — same pattern as pubsub factory."""
# import os
# from backend.services.llm.base_client import BaseLLMClient
# from backend.services.llm.groq_client import GroqClient
# from backend.services.llm.gemini_client import GeminiClient
# from backend.services.llm.openai_client import OpenAIClient
            
# _llm_instance = None

# def get_llm_client() -> BaseLLMClient:
#     global _llm_instance

#     if _llm_instance:
#         return _llm_instance

#     provider = os.getenv("LLM_PROVIDER", "openai")

#     if provider == "groq":
#         _llm_instance = GroqClient()

#     elif provider == "gemini":
#         _llm_instance = GeminiClient()

#     else:
#         _llm_instance = OpenAIClient()

#     return _llm_instance


# llm_factory.py
import os
from typing import Type, Dict, Optional
from backend.services.llm.base_client import BaseLLMClient

class LLMFactory:

    _registry: Dict[str, Type[BaseLLMClient]] = {}

    @classmethod
    def register_llm(cls, name: str):
        def wrapper(client_cls: Type[BaseLLMClient]):
            cls._registry[name.lower()] = client_cls
            return client_cls
        return wrapper

    @classmethod
    def get_llm_client(cls, provider: Optional[str] = None) -> BaseLLMClient:
        provider = (provider or os.getenv("LLM_PROVIDER", "groq")).lower()
        client_cls = cls._registry.get(provider)
        if client_cls is None:
            available = list(cls._registry.keys())
            raise ValueError(
                f"LLM provider '{provider}' not found. "
                f"Available providers: {available}"
            )
        print(f"Using LLM client: {client_cls.__name__}")
        return client_cls()