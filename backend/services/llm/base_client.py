"""Abstract base class for LLM clients with streaming and structured output."""
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Type, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class BaseLLMClient(ABC):

    @abstractmethod
    async def stream(self, messages: list) -> AsyncGenerator[str, None]:
        """Stream tokens from the LLM. Yields token strings."""
        pass

    @abstractmethod
    async def structured_output(self, messages: list, schema: Type[T]) -> T:
        """Get a structured response from the LLM, validated against a Pydantic schema.

        This uses each provider's native structured output / JSON mode:
        - OpenAI/Groq: beta.chat.completions.parse() with response_format
        - Gemini: generate_content() with response_schema

        Returns a validated Pydantic model instance.
        """
        pass
