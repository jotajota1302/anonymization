"""ServiceNow connector — placeholder for real implementation."""

from typing import List, Dict, Optional
import structlog

from .base import TicketConnector

logger = structlog.get_logger()


class ServiceNowConnector(TicketConnector):
    """ServiceNow connector — requires real ServiceNow API integration."""

    def __init__(self, base_url: str = "", token: str = "", project: str = ""):
        self.base_url = base_url.rstrip("/") if base_url else ""
        self.token = token
        self.project = project
        logger.info("servicenow_connector_initialized", base_url=self.base_url)

    async def get_ticket(self, ticket_id: str) -> Dict:
        raise NotImplementedError("ServiceNow connector: real API integration pending")

    async def get_all_tickets(self) -> List[Dict]:
        return []

    async def get_comments(self, ticket_id: str) -> List[Dict]:
        return []

    async def update_status(self, ticket_id: str, status: str) -> bool:
        raise NotImplementedError("ServiceNow connector: real API integration pending")

    async def add_comment(self, ticket_id: str, comment: str) -> bool:
        raise NotImplementedError("ServiceNow connector: real API integration pending")

    async def delete_ticket(self, ticket_id: str) -> bool:
        raise NotImplementedError("ServiceNow connector: real API integration pending")

    async def download_attachment(self, attachment_url: str) -> bytes:
        return b""

    async def create_ticket(
        self, summary: str, description: str, priority: str = "Medium", **kwargs
    ) -> Optional[str]:
        raise NotImplementedError("ServiceNow connector: real API integration pending")

    async def get_board_issues(self) -> List[Dict]:
        return []
