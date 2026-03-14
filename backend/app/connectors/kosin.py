"""KOSIN connector - Internal Jira (Jira API v2) for anonymized ticket management."""

from typing import List, Dict, Optional
import structlog
import httpx

from .base import TicketConnector
from ..config import settings

logger = structlog.get_logger()

# Transition IDs for KOSIN workflow
TRANSITIONS = {
    "in_progress": "11",
    "delivered": "31",
    "done": "31",
}


class KosinConnector(TicketConnector):
    """Connector for KOSIN (internal Jira instance) using REST API v2."""

    def __init__(
        self,
        base_url: str = None,
        token: str = None,
        project: str = None,
        issue_type_id: str = None,
    ):
        self.base_url = (base_url or settings.kosin_url).rstrip("/")
        self.token = token or settings.kosin_token
        self.project = project or settings.kosin_project
        self.issue_type_id = issue_type_id or settings.kosin_issue_type_id
        self._api_base = f"{self.base_url}/rest/api/2"
        self._headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def get_ticket(self, ticket_id: str) -> Dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._api_base}/issue/{ticket_id}",
                headers=self._headers,
            )
            resp.raise_for_status()
            data = resp.json()
            fields = data.get("fields", {})
            attachments = [
                {
                    "filename": a.get("filename", ""),
                    "content": a.get("content", ""),
                    "mimeType": a.get("mimeType", ""),
                    "size": a.get("size", 0),
                }
                for a in fields.get("attachment", [])
            ]
            return {
                "key": data["key"],
                "summary": fields.get("summary", ""),
                "description": fields.get("description", ""),
                "status": fields.get("status", {}).get("name", "Unknown"),
                "priority": fields.get("priority", {}).get("name", "Medium"),
                "created": fields.get("created", ""),
                "attachments": attachments,
            }

    async def download_attachment(self, attachment_url: str) -> bytes:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(
                attachment_url,
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.content

    async def get_comments(self, ticket_id: str) -> List[Dict]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._api_base}/issue/{ticket_id}/comment",
                headers=self._headers,
            )
            resp.raise_for_status()
            data = resp.json()
            return [
                {
                    "body": c.get("body", ""),
                    "author": c.get("author", {}).get("displayName", ""),
                    "created": c.get("created", ""),
                }
                for c in data.get("comments", [])
            ]

    async def create_ticket(
        self, summary: str, description: str, priority: str = "Medium", **kwargs
    ) -> tuple[Optional[str], Optional[str]]:
        """Create a ticket in KOSIN. If parent_key is given, creates a Sub-Requirements subtask.
        Returns (ticket_key, error_message). On success error_message is None."""
        parent_key = kwargs.get("parent_key")

        # Valid priorities in KOSIN
        valid_priorities = {"Critical", "High", "Medium", "Low", "Very Low"}
        if priority not in valid_priorities:
            priority = "Medium"

        if parent_key:
            # Sub-task under parent (Sub-Requirements type 15408)
            payload = {
                "fields": {
                    "project": {"key": self.project},
                    "summary": summary,
                    "description": description,
                    "issuetype": {"id": self.issue_type_id},  # 15408 Sub-Requirements
                    "priority": {"name": priority},
                    "parent": {"key": parent_key},
                }
            }
        else:
            # Standalone Support ticket (10601)
            payload = {
                "fields": {
                    "project": {"key": self.project},
                    "summary": summary,
                    "description": description,
                    "issuetype": {"id": "10601"},  # Support
                    "priority": {"name": priority},
                    "customfield_24800": {"id": "26801"},  # Billable: No
                    "customfield_12800": 1,  # Number of client requests
                }
            }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._api_base}/issue",
                    headers=self._headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                ticket_key = data.get("key", "")
                logger.info("kosin_ticket_created", key=ticket_key)
                return ticket_key, None
        except httpx.HTTPStatusError as e:
            body = e.response.text[:500] if e.response else "no response"
            logger.error("kosin_create_failed", status=e.response.status_code, body=body)
            return None, f"HTTP {e.response.status_code}: {body}"
        except httpx.HTTPError as e:
            logger.error("kosin_create_failed", error=str(e))
            return None, str(e)

    async def delete_ticket(self, ticket_id: str) -> bool:
        """Delete a ticket from KOSIN via REST API."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.delete(
                    f"{self._api_base}/issue/{ticket_id}",
                    headers=self._headers,
                )
                resp.raise_for_status()
                logger.info("kosin_ticket_deleted", key=ticket_id)
                return True
        except httpx.HTTPError as e:
            logger.error("kosin_delete_failed", key=ticket_id, error=str(e))
            return False

    async def update_status(self, ticket_id: str, status: str) -> bool:
        """Update ticket status via transitions."""
        transition_id = TRANSITIONS.get(status.lower())
        if not transition_id:
            logger.warning("kosin_unknown_transition", status=status)
            return False

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._api_base}/issue/{ticket_id}/transitions",
                    headers=self._headers,
                    json={"transition": {"id": transition_id}},
                )
                resp.raise_for_status()
                logger.info("kosin_status_updated", ticket=ticket_id, status=status)
                return True
        except httpx.HTTPError as e:
            logger.error("kosin_transition_failed", error=str(e))
            return False

    async def add_comment(self, ticket_id: str, comment: str) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._api_base}/issue/{ticket_id}/comment",
                    headers=self._headers,
                    json={"body": comment},
                )
                resp.raise_for_status()
                return True
        except httpx.HTTPError as e:
            logger.error("kosin_comment_failed", error=str(e))
            return False

    async def get_board_issues(self) -> List[Dict]:
        """Get open issues from the KOSIN project via JQL search."""
        jql = (
            f'project={self.project} '
            f'AND status in (Open, "In Progress", "To Do") '
            f'ORDER BY priority DESC, created DESC'
        )
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{self._api_base}/search",
                    headers=self._headers,
                    params={
                        "jql": jql,
                        "maxResults": 50,
                        "fields": "summary,status,priority,issuetype",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("issues", [])
        except httpx.HTTPError as e:
            logger.error("kosin_board_issues_failed", error=str(e))
            return []


class MockKosinConnector(TicketConnector):
    """Mock KOSIN connector for testing without real KOSIN access."""

    def __init__(self):
        self.tickets: Dict[str, Dict] = {}
        self.comments: Dict[str, List[Dict]] = {}
        self._counter = 0
        logger.info("mock_kosin_initialized")

    async def get_ticket(self, ticket_id: str) -> Dict:
        ticket = self.tickets.get(ticket_id)
        if not ticket:
            raise ValueError(f"KOSIN ticket {ticket_id} not found")
        return ticket

    async def get_comments(self, ticket_id: str) -> List[Dict]:
        return self.comments.get(ticket_id, [])

    async def create_ticket(
        self, summary: str, description: str, priority: str = "Medium", **kwargs
    ) -> tuple[Optional[str], Optional[str]]:
        self._counter += 1
        key = f"KOS-{self._counter:03d}"
        self.tickets[key] = {
            "key": key,
            "summary": summary,
            "description": description,
            "status": "Open",
            "priority": priority,
        }
        self.comments[key] = []
        logger.info("mock_kosin_ticket_created", key=key)
        return key, None

    async def delete_ticket(self, ticket_id: str) -> bool:
        if ticket_id in self.tickets:
            del self.tickets[ticket_id]
            self.comments.pop(ticket_id, None)
            logger.info("mock_kosin_ticket_deleted", key=ticket_id)
            return True
        return False

    async def update_status(self, ticket_id: str, status: str) -> bool:
        if ticket_id in self.tickets:
            self.tickets[ticket_id]["status"] = status
            return True
        return False

    async def download_attachment(self, attachment_url: str) -> bytes:
        return b""

    async def add_comment(self, ticket_id: str, comment: str) -> bool:
        if ticket_id not in self.comments:
            self.comments[ticket_id] = []
        self.comments[ticket_id].append({
            "body": comment,
            "author": "system",
        })
        return True

    async def get_board_issues(self) -> List[Dict]:
        """Mock board issues - returns all tickets in Jira API format."""
        issues = []
        for key, ticket in self.tickets.items():
            issues.append({
                "key": key,
                "fields": {
                    "summary": ticket.get("summary", ""),
                    "status": {"name": ticket.get("status", "Open")},
                    "priority": {"name": ticket.get("priority", "Medium")},
                    "issuetype": {"name": "Support"},
                },
            })
        return issues
