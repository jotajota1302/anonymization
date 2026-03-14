"""MCPConnector: Base class for future MCP-based ticket connectors.

Model Context Protocol (MCP) abstraction for ticket system integration.
When real MCP servers are available, connectors will inherit from this class
and map call_tool() → TicketConnector methods.

For now, mock connectors inherit directly from TicketConnector.
"""

from typing import Dict, Any
import structlog

from .base import TicketConnector

logger = structlog.get_logger()


class MCPConnector(TicketConnector):
    """Base for connectors that use MCP protocol.

    Provides a call_tool() method that maps to the MCP tool calling pattern.
    Subclasses implement the actual MCP transport.
    """

    def __init__(self, server_url: str = "", server_name: str = ""):
        self.server_url = server_url
        self.server_name = server_name

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> dict:
        """Call an MCP tool on the remote server.

        Args:
            tool_name: Name of the MCP tool to invoke
            arguments: Tool arguments as a dictionary

        Returns:
            Tool response as a dictionary
        """
        raise NotImplementedError(
            f"MCP transport not yet implemented for {self.server_name}. "
            "Use mock connectors for development."
        )

    # Default implementations that delegate to call_tool
    # Subclasses override these when MCP transport is ready

    async def get_ticket(self, ticket_id: str) -> Dict:
        return await self.call_tool("get_ticket", {"ticket_id": ticket_id})

    async def get_comments(self, ticket_id: str):
        result = await self.call_tool("get_comments", {"ticket_id": ticket_id})
        return result.get("comments", [])

    async def update_status(self, ticket_id: str, status: str) -> bool:
        result = await self.call_tool("update_status", {"ticket_id": ticket_id, "status": status})
        return result.get("success", False)

    async def add_comment(self, ticket_id: str, comment: str) -> bool:
        result = await self.call_tool("add_comment", {"ticket_id": ticket_id, "comment": comment})
        return result.get("success", False)

    async def download_attachment(self, attachment_url: str) -> bytes:
        return b""

    async def create_ticket(self, summary: str, description: str, priority: str = "Medium", **kwargs):
        result = await self.call_tool("create_ticket", {
            "summary": summary,
            "description": description,
            "priority": priority,
            **kwargs,
        })
        return result.get("key")
