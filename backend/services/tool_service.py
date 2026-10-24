"""Tool service — registry for callable tools used by agents."""
import logging
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)


class ToolService:
    """Registry for callable tools that agents can invoke."""

    _tools: Dict[str, Callable] = {}

    @classmethod
    def register_tool(cls, name: str):
        """Decorator to register a callable tool."""
        def wrapper(func: Callable):
            cls._tools[name] = func
            logger.info(f"Registered tool: {name}")
            return func
        return wrapper

    @classmethod
    async def execute_tool(cls, tool_name: str, **kwargs) -> dict:
        """Execute a registered tool by name."""
        tool = cls._tools.get(tool_name)
        if not tool:
            return {"error": f"Tool '{tool_name}' not found"}

        try:
            result = await tool(**kwargs) if callable(tool) else tool(**kwargs)
            return {"status": "success", "result": result}
        except Exception as e:
            logger.error(f"Tool '{tool_name}' execution failed: {e}")
            return {"status": "error", "error": str(e)}

    @classmethod
    def list_tools(cls) -> List[str]:
        return list(cls._tools.keys())
