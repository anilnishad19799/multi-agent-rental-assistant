"""Gemini LLM client with streaming and structured output."""
import json
import os
from typing import Type, TypeVar
from google import genai
from google.genai import types
from pydantic import BaseModel
from backend.services.llm.base_client import BaseLLMClient
from backend.services.llm.llm_factory import LLMFactory

T = TypeVar("T", bound=BaseModel)


@LLMFactory.register_llm("gemini")
class GeminiClient(BaseLLMClient):

    def __init__(self):
        self.client = genai.Client(
            api_key=os.getenv("GEMINI_API_KEY")
        )
        self.model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    def _convert_messages(self, messages: list) -> list:
        """Convert OpenAI message format to Gemini format."""
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        return contents

    async def stream(self, messages: list):
        contents = self._convert_messages(messages)

        response = self.client.models.generate_content_stream(
            model=self.model,
            contents=contents
        )

        for chunk in response:
            if chunk.text:
                yield chunk.text

    async def structured_output(self, messages: list, schema: Type[T]) -> T:
        """Use Gemini's native structured output with response_schema.

        Gemini accepts a Pydantic model as response_schema and returns
        JSON that conforms to the schema. We validate via Pydantic.
        """
        contents = self._convert_messages(messages)

        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )

        # Parse the JSON response and validate against the schema
        raw_json = json.loads(response.text)
        return schema.model_validate(raw_json)
