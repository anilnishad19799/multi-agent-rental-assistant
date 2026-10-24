"""Application settings."""
import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Settings:
    """Application configuration. Reads from environment variables."""

    # App
    APP_NAME: str = "Real Estate Rent Agent"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./rental_system.db")

    # LLM Providers
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "groq")
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    GROQ_API_KEY: Optional[str] = os.getenv("GROQ_API_KEY")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    # PubSub
    PUBSUB_BACKEND: str = os.getenv("PUBSUB_BACKEND", "memory")
    REDIS_URL: Optional[str] = os.getenv("REDIS_URL")

    # Agent settings
    DEFAULT_AGENT: str = "general"
    MAX_AGENT_HANDOFFS: int = 5

    # Memory
    SHORT_TERM_MAX_MESSAGES: int = 50
    CONVERSATION_CONTEXT_LIMIT: int = 20


_settings = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings