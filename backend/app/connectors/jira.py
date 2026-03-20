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
        """Apply a Jira transition matching the requested status name.

        Queries available transitions and picks the first one whose name
        contains any of the target keywords (case-insensitive).
        """
        import httpx

        # Keywords to match against Jira transition names
        STATUS_KEYWORDS = {
            "done":       ["done", "closed", "close", "resolved", "resolve", "cerrado", "cerrar", "resuelto"],
            "in_progress": ["progress", "progress", "en curso", "in progress", "working"],
            "delivered":  ["delivered", "entregado", "pending", "waiting"],
        }
        keywords = STATUS_KEYWORDS.get(status.lower(), [status.lower()])

        async with httpx.AsyncClient() as client:
            # 1. Fetch available transitions
            resp = await client.get(
                f"{self.base_url}/rest/api/2/issue/{ticket_id}/transitions",
                headers=self._headers,
                auth=self._auth,
            )
            if not resp.is_success:
                logger.warning("jira_transitions_fetch_failed", ticket_id=ticket_id, status_code=resp.status_code)
                return False

            transitions = resp.json().get("transitions", [])
            transition_id = None
            for t in transitions:
                name = t.get("name", "").lower()
                if any(kw in name for kw in keywords):
                    transition_id = t["id"]
                    break

            if not transition_id:
                logger.warning(
                    "jira_transition_not_found",
                    ticket_id=ticket_id,
                    status=status,
                    available=[t.get("name") for t in transitions],
                )
                return False

            # 2. Apply the transition
            resp = await client.post(
                f"{self.base_url}/rest/api/2/issue/{ticket_id}/transitions",
                headers=self._headers,
                auth=self._auth,
                json={"transition": {"id": transition_id}},
            )
            success = resp.is_success
            logger.info("jira_status_updated", ticket_id=ticket_id, status=status, transition_id=transition_id, ok=success)
            return success

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

    async def get_available_transitions(self, ticket_id: str) -> list[dict]:
        """Get available workflow transitions for a ticket."""
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/rest/api/2/issue/{ticket_id}/transitions",
                headers=self._headers,
                auth=self._auth,
            )
            if not resp.is_success:
                logger.warning("jira_transitions_fetch_failed", ticket_id=ticket_id, status_code=resp.status_code)
                return []
            return [
                {"id": t["id"], "name": t.get("name", "")}
                for t in resp.json().get("transitions", [])
            ]

    async def get_ticket_status(self, ticket_id: str) -> str:
        """Get the current status name of a ticket."""
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/rest/api/2/issue/{ticket_id}",
                headers=self._headers,
                auth=self._auth,
                params={"fields": "status"},
            )
            if not resp.is_success:
                return "Unknown"
            return resp.json().get("fields", {}).get("status", {}).get("name", "Unknown")

    async def walk_transitions_to(
        self, ticket_id: str, target: str, max_steps: int = 5
    ) -> tuple[bool, list[str]]:
        """Walk through Jira transitions until reaching the target status."""
        import httpx

        DONE_KEYWORDS = ["done", "closed", "close", "resolved", "resolve", "cerrado", "cerrar", "resuelto"]
        STATUS_KEYWORDS = {
            "done": DONE_KEYWORDS,
            "closed": DONE_KEYWORDS,
            "delivered": ["delivered", "entregado", "pending", "waiting"],
            "in_progress": ["progress", "in progress", "en curso", "working"],
        }
        keywords = STATUS_KEYWORDS.get(target.lower(), [target.lower()])
        steps_taken: list[str] = []

        for _ in range(max_steps):
            current = await self.get_ticket_status(ticket_id)
            if current.lower() in DONE_KEYWORDS and target.lower() in ("done", "closed"):
                return True, steps_taken

            transitions = await self.get_available_transitions(ticket_id)
            if not transitions:
                break

            chosen = None
            for t in transitions:
                name = t["name"].lower()
                if any(kw in name for kw in keywords):
                    chosen = t
                    break

            if not chosen:
                for t in transitions:
                    name = t["name"].lower()
                    if any(kw in name for kw in ["progress", "in progress", "en curso"]):
                        chosen = t
                        break

            if not chosen:
                logger.warning(
                    "jira_walk_no_match",
                    ticket_id=ticket_id,
                    target=target,
                    available=[t["name"] for t in transitions],
                )
                break

            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.base_url}/rest/api/2/issue/{ticket_id}/transitions",
                    headers=self._headers,
                    auth=self._auth,
                    json={"transition": {"id": chosen["id"]}},
                )
                if not resp.is_success:
                    logger.error("jira_walk_transition_failed", ticket_id=ticket_id, transition=chosen["name"])
                    break
                steps_taken.append(chosen["name"])
                logger.info("jira_walk_transition_applied", ticket_id=ticket_id, transition=chosen["name"])

        final = await self.get_ticket_status(ticket_id)
        success = final.lower() in keywords or final.lower() in DONE_KEYWORDS
        return success, steps_taken

    async def delete_ticket(self, ticket_id: str) -> bool:
        logger.warning("jira_delete_ticket: not implemented for real Jira")
        return False

    async def create_ticket(
        self, summary: str, description: str, priority: str = "Medium", **kwargs
    ) -> tuple[Optional[str], Optional[str]]:
        logger.warning("jira_create_ticket: use KOSIN connector for creating tickets")
        return None, "Not implemented for real Jira"
