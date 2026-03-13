"""Abstract base class for ticket system connectors."""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional


class TicketConnector(ABC):
    """Abstract interface for ticket system connectors (Jira, KOSIN, Remedy, etc.)."""

    @abstractmethod
    async def get_ticket(self, ticket_id: str) -> Dict:
        """Get full ticket details by ID."""
        ...

    @abstractmethod
    async def get_comments(self, ticket_id: str) -> List[Dict]:
        """Get comments for a ticket."""
        ...

    @abstractmethod
    async def update_status(self, ticket_id: str, status: str) -> bool:
        """Update ticket status. Returns True on success."""
        ...

    @abstractmethod
    async def add_comment(self, ticket_id: str, comment: str) -> bool:
        """Add a comment to a ticket. Returns True on success."""
        ...

    @abstractmethod
    async def create_ticket(
        self, summary: str, description: str, priority: str = "Medium",
        **kwargs
    ) -> Optional[str]:
        """Create a new ticket. Returns the ticket key/ID."""
        ...
