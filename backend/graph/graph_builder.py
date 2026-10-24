"""Minimal graph builder — passthrough for POC.

Returns a simple graph that passes messages through unchanged.
This will be replaced with a full LangGraph implementation later.
"""


class SimpleGraph:
    """Minimal graph that just passes state through."""

    def invoke(self, state: dict) -> dict:
        return state


def build_graph():
    """Build and return the agent graph."""
    return SimpleGraph()
