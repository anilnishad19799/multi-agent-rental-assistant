"""Observability logger — enriches logs with trace_id, user_id, and agent context."""
import logging
from typing import Optional
from backend.observability.tracing import get_current_trace


class TraceLoggerAdapter(logging.LoggerAdapter):
    """LoggerAdapter that injects active trace context into log records."""

    def process(self, msg, kwargs):
        trace = get_current_trace()
        extra = kwargs.get("extra", {})
        if trace:
            extra.setdefault("trace_id", trace.trace_id)
            extra.setdefault("session_id", trace.session_id)
            extra.setdefault("user_id", trace.user_id)
            if trace.agents_invoked:
                extra.setdefault("agent", trace.agents_invoked[-1])
        kwargs["extra"] = extra
        return msg, kwargs


def get_logger(name: str) -> logging.LoggerAdapter:
    """Get a contextual logger enriched with trace and agent metadata."""
    logger = logging.getLogger(name)
    return TraceLoggerAdapter(logger, {})
