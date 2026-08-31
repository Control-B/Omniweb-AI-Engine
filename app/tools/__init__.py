"""Tool plane initialization for Omniweb Contact Center."""
from app.tools.base import BaseTool, ToolCategory, ToolResult, ToolRiskLevel
from app.tools.registry import ToolRegistry, get_tool_registry

# Import tool modules to trigger automatic registration
import app.tools.crm.tools
import app.tools.billing.tools
import app.tools.calendar.tools
import app.tools.ticketing.tools
import app.tools.knowledge.tools

__all__ = [
    "BaseTool",
    "ToolCategory",
    "ToolResult",
    "ToolRiskLevel",
    "ToolRegistry",
    "get_tool_registry",
]
