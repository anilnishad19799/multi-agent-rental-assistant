"""OpenAI LLM client with streaming and structured output."""
import os
from typing import Type, TypeVar
from openai import AsyncOpenAI
from pydantic import BaseModel
from backend.services.llm.base_client import BaseLLMClient
from backend.services.llm.llm_factory import LLMFactory

T = TypeVar("T", bound=BaseModel)


@LLMFactory.register_llm("openai")
class OpenAIClient(BaseLLMClient):

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY")
        )
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

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
        """Use OpenAI's beta.chat.completions.parse() for structured output.

        This passes the Pydantic schema as response_format and returns
        a validated model instance — no manual JSON parsing needed.
        """
        completion = await self.client.beta.chat.completions.parse(
            model=self.model,
            messages=messages,
            response_format=schema,
        )
        return completion.choices[0].message.parsed
