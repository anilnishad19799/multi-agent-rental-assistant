"""Streams LLM tokens and publishes events — provider agnostic."""
from backend.services.llm.llm_factory import LLMFactory
from backend.events.publisher import publish_event
from backend.events.types import EventType

async def stream_llm_response(session_id: str, messages: list, provider: str = None):
    """
    Streams tokens from configured LLM provider and emits events into system.
    Set LLM_PROVIDER env var to switch: openai | groq | gemini
    """  

    client = LLMFactory.get_llm_client(provider)
    async for token in client.stream(messages):
        await publish_event(
            session_id=session_id,
            event_type=EventType.LLM_TOKEN,
            data={"token": token}
        )
        yield token

    await publish_event(
        session_id=session_id,
        event_type=EventType.LLM_DONE,
        data={}
    )