"""Groq LLM client — uses OpenAI-compatible API with structured output."""
import os
from typing import Type, TypeVar
from openai import AsyncOpenAI
from pydantic import BaseModel
from backend.services.llm.base_client import BaseLLMClient
from backend.services.llm.llm_factory import LLMFactory

T = TypeVar("T", bound=BaseModel)


@LLMFactory.register_llm("groq")
class GroqClient(BaseLLMClient):

    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY is not set. Please add GROQ_API_KEY to your .env file."
            )
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1"
        )
        self.model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

    async def stream(self, messages: list):
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True
        )

        async for chunk in response:
            token = chunk.choices[0].delta.content
            if token:
                yield token

    async def structured_output(self, messages: list, schema: Type[T]) -> T:
        """Use Groq's OpenAI-compatible structured output.

        Groq supports response_format with JSON schema through the
        OpenAI-compatible API, using beta.chat.completions.parse().
        """
        completion = await self.client.beta.chat.completions.parse(
            model=self.model,
            messages=messages,
            response_format=schema,
        )
        return completion.choices[0].message.parsed
