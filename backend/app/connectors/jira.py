"""Jira connector - Real Jira REST API v2 implementation."""

from typing import List, Dict, Optional
import structlog

from .base import TicketConnector

logger = structlog.get_logger()


class JiraConnector(TicketConnector):
    """Real Jira connector using REST API v2."""

    def __init__(self, base_url: str, email: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.token = token
        self._headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        self._auth = (email, token)

    async def get_ticket(self, ticket_id: str) -> Dict:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/rest/api/2/issue/{ticket_id}",
                headers=self._headers,
                auth=self._auth,
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
                "reporter": fields.get("reporter", {}).get("displayName", ""),
                "assignee": fields.get("assignee", {}).get("displayName", ""),
                "attachments": attachments,
            }

    async def get_comments(self, ticket_id: str) -> List[Dict]:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/rest/api/2/issue/{ticket_id}/comment",
                headers=self._headers,
                auth=self._auth,
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

    async def update_status(self, ticket_id: str, status: str) -> bool:
        logger.warning("jira_update_status_not_impl", ticket_id=ticket_id)
        return False

    async def add_comment(self, ticket_id: str, comment: str) -> bool:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/rest/api/2/issue/{ticket_id}/comment",
                headers=self._headers,
                auth=self._auth,
                json={"body": comment},
            )
            return resp.is_success

    async def download_attachment(self, attachment_url: str) -> bytes:
        import httpx
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(
                attachment_url,
                headers=self._headers,
                auth=self._auth,
            )
            resp.raise_for_status()
            return resp.content

    async def delete_ticket(self, ticket_id: str) -> bool:
        logger.warning("jira_delete_ticket: not implemented for real Jira")
        return False

    async def create_ticket(
        self, summary: str, description: str, priority: str = "Medium", **kwargs
    ) -> tuple[Optional[str], Optional[str]]:
        logger.warning("jira_create_ticket: use KOSIN connector for creating tickets")
        return None, "Not implemented for real Jira"
