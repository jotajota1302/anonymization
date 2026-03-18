"""KOSIN connector - Internal Jira (Jira API v2) for anonymized ticket management."""

from typing import List, Dict, Optional
import structlog
import httpx

from .base import TicketConnector, BoardFilters
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
        async with httpx.AsyncClient(timeout=30.0) as client:
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
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(
                attachment_url,
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.content

    async def get_comments(self, ticket_id: str) -> List[Dict]:
        async with httpx.AsyncClient(timeout=30.0) as client:
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
            async with httpx.AsyncClient(timeout=30.0) as client:
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
            error_msg = str(e) or f"{type(e).__name__}: {repr(e)}"
            logger.error("kosin_create_failed", error=error_msg, error_type=type(e).__name__)
            return None, error_msg

    async def find_anon_ticket(self, source_key: str) -> Optional[str]:
        """Check if an [ANON] ticket already exists in KOSIN for the given source key.
        Returns the KOSIN key if found, None otherwise."""
        jql = (
            f'project={self.project} '
            f'AND summary ~ "ANON" AND summary ~ "{source_key}"'
        )
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"{self._api_base}/search",
                    headers=self._headers,
                    params={"jql": jql, "maxResults": 5, "fields": "summary"},
                )
                resp.raise_for_status()
                issues = resp.json().get("issues", [])
                for issue in issues:
                    summary = issue.get("fields", {}).get("summary", "")
                    if "[ANON]" in summary and source_key in summary:
                        logger.info("kosin_anon_ticket_found", source_key=source_key, existing=issue["key"])
                        return issue["key"]
                return None
        except httpx.HTTPError as e:
            error_msg = str(e) or f"{type(e).__name__}: {repr(e)}"
            logger.error("kosin_find_anon_failed", source_key=source_key, error=error_msg)
            return None

    async def delete_ticket(self, ticket_id: str) -> tuple[bool, Optional[str]]:
        """Delete a ticket from KOSIN via REST API (with subtasks).
        Returns (success, error_message)."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.delete(
                    f"{self._api_base}/issue/{ticket_id}",
                    headers=self._headers,
                    params={"deleteSubtasks": "true"},
                )
                resp.raise_for_status()
                logger.info("kosin_ticket_deleted", key=ticket_id)
                return True, None
        except httpx.HTTPStatusError as e:
            body = e.response.text[:500] if e.response else "no response"
            error_msg = f"HTTP {e.response.status_code}: {body}"
            logger.error("kosin_delete_failed", key=ticket_id, error=error_msg)
            return False, error_msg
        except httpx.HTTPError as e:
            error_msg = str(e) or f"{type(e).__name__}: {repr(e)}"
            logger.error("kosin_delete_failed", key=ticket_id, error=error_msg, error_type=type(e).__name__)
            return False, error_msg

    async def update_status(self, ticket_id: str, status: str) -> bool:
        """Update ticket status via transitions."""
        transition_id = TRANSITIONS.get(status.lower())
        if not transition_id:
            logger.warning("kosin_unknown_transition", status=status)
            return False

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self._api_base}/issue/{ticket_id}/transitions",
                    headers=self._headers,
                    json={"transition": {"id": transition_id}},
                )
                resp.raise_for_status()
                logger.info("kosin_status_updated", ticket=ticket_id, status=status)
                return True
        except httpx.HTTPStatusError as e:
            body = e.response.text[:500] if e.response else "no response"
            logger.error("kosin_transition_failed", error=f"HTTP {e.response.status_code}: {body}")
            return False
        except httpx.HTTPError as e:
            error_msg = str(e) or f"{type(e).__name__}: {repr(e)}"
            logger.error("kosin_transition_failed", error=error_msg, error_type=type(e).__name__)
            return False

    async def add_comment(self, ticket_id: str, comment: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self._api_base}/issue/{ticket_id}/comment",
                    headers=self._headers,
                    json={"body": comment},
                )
                resp.raise_for_status()
                return True
        except httpx.HTTPStatusError as e:
            body = e.response.text[:500] if e.response else "no response"
            logger.error("kosin_comment_failed", error=f"HTTP {e.response.status_code}: {body}")
            return False
        except httpx.HTTPError as e:
            error_msg = str(e) or f"{type(e).__name__}: {repr(e)}"
            logger.error("kosin_comment_failed", error=error_msg, error_type=type(e).__name__)
            return False

    async def get_board_issues(self, filters: Optional[BoardFilters] = None) -> List[Dict]:
        """Get open issues from the KOSIN project via JQL search with optional filters."""
        filters = filters or BoardFilters()

        # Build JQL dynamically
        jql_parts = [f'project={self.project}']

        if filters.status:
            status_str = ", ".join(f'"{s}"' for s in filters.status)
            jql_parts.append(f'status in ({status_str})')
        else:
            jql_parts.append('status in (Open, "In Progress", "To Do")')

        if filters.priority:
            priority_str = ", ".join(f'"{p}"' for p in filters.priority)
            jql_parts.append(f'priority in ({priority_str})')

        if filters.issue_type:
            type_str = ", ".join(f'"{t}"' for t in filters.issue_type)
            jql_parts.append(f'issuetype in ({type_str})')

        if filters.date_from:
            jql_parts.append(f'created >= "{filters.date_from}"')

        if filters.date_to:
            jql_parts.append(f'created <= "{filters.date_to}"')

        jql = " AND ".join(jql_parts) + " ORDER BY created DESC"

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{self._api_base}/search",
                    headers=self._headers,
                    params={
                        "jql": jql,
                        "maxResults": filters.max_results,
                        "fields": "summary,status,priority,issuetype",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("issues", [])
        except httpx.HTTPStatusError as e:
            body = e.response.text[:500] if e.response else "no response"
            logger.error("kosin_board_issues_failed", error=f"HTTP {e.response.status_code}: {body}")
            return []
        except httpx.HTTPError as e:
            error_msg = str(e) or f"{type(e).__name__}: {repr(e)}"
            logger.error("kosin_board_issues_failed", error=error_msg, error_type=type(e).__name__)
            return []

    async def search_issues(self, jql: str, max_results: int = 50) -> List[Dict]:
        """Search issues using JQL query via REST API."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self._api_base}/search",
                    headers=self._headers,
                    json={
                        "jql": jql,
                        "maxResults": max_results,
                        "fields": ["summary", "status", "priority", "issuetype", "created", "assignee"],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                issues = []
                for item in data.get("issues", []):
                    fields = item.get("fields", {})
                    issues.append({
                        "key": item["key"],
                        "summary": fields.get("summary", ""),
                        "status": fields.get("status", {}).get("name", "Unknown"),
                        "priority": fields.get("priority", {}).get("name", "Medium"),
                        "issuetype": fields.get("issuetype", {}).get("name", ""),
                        "created": fields.get("created", ""),
                        "assignee": fields.get("assignee", {}).get("displayName", "") if fields.get("assignee") else "",
                    })
                return issues
        except httpx.HTTPStatusError as e:
            body = e.response.text[:500] if e.response else "no response"
            logger.error("kosin_search_failed", error=f"HTTP {e.response.status_code}: {body}")
            return []
        except httpx.HTTPError as e:
            error_msg = str(e) or f"{type(e).__name__}: {repr(e)}"
            logger.error("kosin_search_failed", error=error_msg, error_type=type(e).__name__)
            return []

    async def add_worklog(
        self, ticket_id: str, time_spent: str, comment: str = "", started: str = ""
    ) -> bool:
        """Add a worklog entry to a KOSIN ticket."""
        payload = {"timeSpent": time_spent}
        if comment:
            payload["comment"] = comment
        if started:
            payload["started"] = started
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self._api_base}/issue/{ticket_id}/worklog",
                    headers=self._headers,
                    json=payload,
                )
                resp.raise_for_status()
                logger.info("kosin_worklog_added", ticket=ticket_id, time_spent=time_spent)
                return True
        except httpx.HTTPStatusError as e:
            body = e.response.text[:500] if e.response else "no response"
            logger.error("kosin_worklog_add_failed", error=f"HTTP {e.response.status_code}: {body}")
            return False
        except httpx.HTTPError as e:
            error_msg = str(e) or f"{type(e).__name__}: {repr(e)}"
            logger.error("kosin_worklog_add_failed", error=error_msg, error_type=type(e).__name__)
            return False

    async def get_worklogs(self, ticket_id: str) -> List[Dict]:
        """Get all worklog entries for a KOSIN ticket."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"{self._api_base}/issue/{ticket_id}/worklog",
                    headers=self._headers,
                )
                resp.raise_for_status()
                data = resp.json()
                return [
                    {
                        "id": w.get("id", ""),
                        "author": w.get("author", {}).get("displayName", ""),
                        "timeSpent": w.get("timeSpent", ""),
                        "timeSpentSeconds": w.get("timeSpentSeconds", 0),
                        "started": w.get("started", ""),
                        "comment": w.get("comment", ""),
                    }
                    for w in data.get("worklogs", [])
                ]
        except httpx.HTTPStatusError as e:
            body = e.response.text[:500] if e.response else "no response"
            logger.error("kosin_worklogs_get_failed", error=f"HTTP {e.response.status_code}: {body}")
            return []
        except httpx.HTTPError as e:
            error_msg = str(e) or f"{type(e).__name__}: {repr(e)}"
            logger.error("kosin_worklogs_get_failed", error=error_msg, error_type=type(e).__name__)
            return []

    async def delete_worklog(self, ticket_id: str, worklog_id: str) -> bool:
        """Delete a worklog entry from a KOSIN ticket."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.delete(
                    f"{self._api_base}/issue/{ticket_id}/worklog/{worklog_id}",
                    headers=self._headers,
                )
                resp.raise_for_status()
                logger.info("kosin_worklog_deleted", ticket=ticket_id, worklog_id=worklog_id)
                return True
        except httpx.HTTPStatusError as e:
            body = e.response.text[:500] if e.response else "no response"
            logger.error("kosin_worklog_delete_failed", error=f"HTTP {e.response.status_code}: {body}")
            return False
        except httpx.HTTPError as e:
            error_msg = str(e) or f"{type(e).__name__}: {repr(e)}"
            logger.error("kosin_worklog_delete_failed", error=error_msg, error_type=type(e).__name__)
            return False


