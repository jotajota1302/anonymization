"""Abstract base class for ticket system connectors."""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class BoardFilters:
    """Filters for board issue queries."""
    max_results: int = 50
    date_from: Optional[str] = None  # YYYY-MM-DD
    date_to: Optional[str] = None    # YYYY-MM-DD
    priority: Optional[List[str]] = None
    status: Optional[List[str]] = None
    issue_type: Optional[List[str]] = None


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
    async def download_attachment(self, attachment_url: str) -> bytes:
        """Download an attachment by its content URL. Returns raw bytes."""
        ...

    @abstractmethod
    async def delete_ticket(self, ticket_id: str) -> bool:
        """Delete a ticket by ID. Returns True on success."""
        ...

    @abstractmethod
    async def create_ticket(
        self, summary: str, description: str, priority: str = "Medium",
        **kwargs
    ) -> tuple[Optional[str], Optional[str]]:
        """Create a new ticket. Returns (ticket_key, error_message)."""
        ...

    # --- Optional methods (default: NotImplementedError) ---

    async def search_issues(self, jql: str, max_results: int = 50) -> List[Dict]:
        """Search issues using JQL query. Returns list of issue dicts."""
        raise NotImplementedError(f"{type(self).__name__} does not support search_issues")

    async def add_worklog(
        self, ticket_id: str, time_spent: str, comment: str = "", started: str = ""
    ) -> bool:
        """Add a worklog entry to a ticket. Returns True on success."""
        raise NotImplementedError(f"{type(self).__name__} does not support add_worklog")

    async def get_worklogs(self, ticket_id: str) -> List[Dict]:
        """Get all worklog entries for a ticket."""
        raise NotImplementedError(f"{type(self).__name__} does not support get_worklogs")

    async def delete_worklog(self, ticket_id: str, worklog_id: str) -> bool:
        """Delete a worklog entry. Returns True on success."""
        raise NotImplementedError(f"{type(self).__name__} does not support delete_worklog")

    async def get_available_transitions(self, ticket_id: str) -> List[Dict]:
        """Get available workflow transitions for a ticket. Returns list of {id, name}."""
        raise NotImplementedError(f"{type(self).__name__} does not support get_available_transitions")

    async def get_ticket_status(self, ticket_id: str) -> str:
        """Get the current status name of a ticket in the remote system."""
        raise NotImplementedError(f"{type(self).__name__} does not support get_ticket_status")

    async def upload_attachment(
        self, ticket_id: str, filename: str, content: bytes,
        content_type: str = "application/octet-stream",
    ) -> tuple[bool, Optional[str]]:
        """Upload an attachment to a ticket. Returns (success, error_message)."""
        raise NotImplementedError(f"{type(self).__name__} does not support upload_attachment")
