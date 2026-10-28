"""Groq LLM client — uses OpenAI-compatible API with structured output and fallback support."""
import logging
import os
from typing import List, Type, TypeVar
from openai import AsyncOpenAI
from pydantic import BaseModel
from backend.services.llm.base_client import BaseLLMClient
from backend.services.llm.llm_factory import LLMFactory

logger = logging.getLogger(__name__)

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
        primary_model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        # Candidate models list: primary first, followed by fallbacks for high resilience
        self.candidate_models: List[str] = [primary_model]
        for fallback in ["openai/gpt-oss-20b", "qwen/qwen3.8-27b"]:
            if fallback not in self.candidate_models:
                self.candidate_models.append(fallback)
        self.model = primary_model

    def _is_rate_limit(self, exc: Exception) -> bool:
        msg = str(exc).lower()
        return "429" in msg or "rate limit" in msg or "tokens per day" in msg or "tpd" in msg

    async def stream(self, messages: list):
        last_error = None
        for model_name in self.candidate_models:
            try:
                response = await self.client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    stream=True
                )
                async for chunk in response:
                    if chunk.choices and chunk.choices[0].delta:
                        token = chunk.choices[0].delta.content
                        if token:
                            yield token
                return
            except Exception as e:
                last_error = e
                if self._is_rate_limit(e) and model_name != self.candidate_models[-1]:
                    logger.warning(
                        f"Groq model '{model_name}' hit rate limit. Trying fallback model..."
                    )
                    continue
                raise e

        if last_error:
            raise last_error

    async def structured_output(self, messages: list, schema: Type[T]) -> T:
        """Use Groq's OpenAI-compatible structured output with fallback."""
        last_error = None
        for model_name in self.candidate_models:
            try:
                completion = await self.client.beta.chat.completions.parse(
                    model=model_name,
                    messages=messages,
                    response_format=schema,
                )
                return completion.choices[0].message.parsed
            except Exception as e:
                last_error = e
                if self._is_rate_limit(e) and model_name != self.candidate_models[-1]:
                    logger.warning(
                        f"Groq model '{model_name}' hit rate limit. Trying fallback model..."
                    )
                    continue
                raise e

        if last_error:
            raise last_error
