"""KOSIN connector - Internal Jira (Jira API v2) for anonymized ticket management."""

from typing import List, Dict, Optional
import structlog
import httpx

from .base import TicketConnector, BoardFilters
from ..config import settings

logger = structlog.get_logger()


def _jql_escape(value: str) -> str:
    """Escape a string value for safe interpolation into JQL queries.

    Prevents JQL injection by escaping characters that have special meaning
    in Jira Query Language string literals.
    """
    # JQL string literals use backslash escaping inside double quotes
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("'", "\\'")

# Default transition IDs — override via extra_config.transitions per instance
_DEFAULT_TRANSITIONS = {
    "in_progress": "161",
    "delivered": "181",
    "done": "191",
    "closed": "191",
}

# Default standalone issue type — override via extra_config.standalone_issue_type_id
_DEFAULT_STANDALONE_ISSUE_TYPE_ID = "10601"

# Default custom fields for standalone tickets — override via extra_config.custom_fields
_DEFAULT_CUSTOM_FIELDS = {
    "customfield_24800": {"id": "26801"},  # Billable: No
    "customfield_12800": 1,               # Number of client requests
}


class KosinConnector(TicketConnector):
    """Connector for KOSIN (internal Jira instance) using REST API v2."""

    def __init__(
        self,
        base_url: str = None,
        token: str = None,
        project: str = None,
        issue_type_id: str = None,
        extra_config: dict = None,
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

        # Instance-specific config from extra_config (DB-driven, editable from UI)
        extra = extra_config or {}
        self._transitions = {**_DEFAULT_TRANSITIONS, **(extra.get("transitions") or {})}
        self._standalone_issue_type_id = extra.get("standalone_issue_type_id") or _DEFAULT_STANDALONE_ISSUE_TYPE_ID
        self._custom_fields = extra.get("custom_fields") or _DEFAULT_CUSTOM_FIELDS

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
            # Standalone ticket (issue type and custom fields from config)
            fields = {
                "project": {"key": self.project},
                "summary": summary,
                "description": description,
                "issuetype": {"id": self._standalone_issue_type_id},
                "priority": {"name": priority},
            }
            # Apply instance-specific custom fields
            for field_id, field_val in self._custom_fields.items():
                fields[field_id] = field_val
            payload = {"fields": fields}

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

    async def upload_attachment(
        self, ticket_id: str, filename: str, content: bytes,
        content_type: str = "application/octet-stream",
    ) -> tuple[bool, Optional[str]]:
        """Attach a file to a Jira/KOSIN issue via REST API.

        Jira requires:
          - multipart/form-data with file field named 'file'
          - X-Atlassian-Token: no-check header to bypass XSRF
          - No Content-Type header (httpx sets the multipart boundary).
        """
        upload_headers = {
            "Authorization": f"Bearer {self.token}",
            "X-Atlassian-Token": "no-check",
            "Accept": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self._api_base}/issue/{ticket_id}/attachments",
                    headers=upload_headers,
                    files={"file": (filename, content, content_type)},
                )
                resp.raise_for_status()
                logger.info("kosin_attachment_uploaded", key=ticket_id, filename=filename, size=len(content))
                return True, None
        except httpx.HTTPStatusError as e:
            body = e.response.text[:500] if e.response else "no response"
            logger.error("kosin_upload_attachment_failed", key=ticket_id, filename=filename,
                         status=e.response.status_code, body=body)
            return False, f"HTTP {e.response.status_code}: {body}"
        except httpx.HTTPError as e:
            error_msg = str(e) or f"{type(e).__name__}: {repr(e)}"
            logger.error("kosin_upload_attachment_failed", key=ticket_id, filename=filename, error=error_msg)
            return False, error_msg

    async def find_anon_ticket(self, source_key: str) -> Optional[str]:
        """Check if an [ANON] ticket already exists in KOSIN for the given source key.
        Returns the KOSIN key if found, None otherwise."""
        safe_key = _jql_escape(source_key)
        jql = (
            f'project={self.project} '
            f'AND summary ~ "ANON" AND summary ~ "{safe_key}"'
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
        transition_id = self._transitions.get(status.lower())
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
            status_str = ", ".join(f'"{_jql_escape(s)}"' for s in filters.status)
            jql_parts.append(f'status in ({status_str})')
        else:
            jql_parts.append('status in (Open, "In Progress", "To Do")')

        if filters.priority:
            priority_str = ", ".join(f'"{_jql_escape(p)}"' for p in filters.priority)
            jql_parts.append(f'priority in ({priority_str})')

        if filters.issue_type:
            type_str = ", ".join(f'"{_jql_escape(t)}"' for t in filters.issue_type)
            jql_parts.append(f'issuetype in ({type_str})')

        if filters.date_from:
            jql_parts.append(f'created >= "{_jql_escape(filters.date_from)}"')

        if filters.date_to:
            jql_parts.append(f'created <= "{_jql_escape(filters.date_to)}"')

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
        # Jira REST API v2 requires 'started' in worklog payload.
        # Default to current time if not provided.
        if not started:
            from datetime import datetime, timezone
            started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000+0000")
        payload = {"timeSpent": time_spent, "started": started}
        if comment:
            payload["comment"] = comment
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
            logger.error("kosin_worklog_add_failed", ticket=ticket_id, error=f"HTTP {e.response.status_code}: {body}")
            raise RuntimeError(f"HTTP {e.response.status_code} al registrar worklog en {ticket_id}: {body}")
        except httpx.HTTPError as e:
            error_msg = str(e) or f"{type(e).__name__}: {repr(e)}"
            logger.error("kosin_worklog_add_failed", ticket=ticket_id, error=error_msg)
            raise RuntimeError(f"Error de conexion al registrar worklog en {ticket_id}: {error_msg}")

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

    async def get_available_transitions(self, ticket_id: str) -> list[dict]:
        """Get available workflow transitions for a ticket."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"{self._api_base}/issue/{ticket_id}/transitions",
                    headers=self._headers,
                )
                resp.raise_for_status()
                return [
                    {"id": t["id"], "name": t.get("name", "")}
                    for t in resp.json().get("transitions", [])
                ]
        except httpx.HTTPError as e:
            logger.error("kosin_transitions_fetch_failed", ticket=ticket_id, error=str(e))
            return []

    async def get_ticket_status(self, ticket_id: str) -> str:
        """Get the current status name of a ticket."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"{self._api_base}/issue/{ticket_id}",
                    headers=self._headers,
                    params={"fields": "status"},
                )
                resp.raise_for_status()
                return resp.json().get("fields", {}).get("status", {}).get("name", "Unknown")
        except httpx.HTTPError as e:
            logger.error("kosin_status_fetch_failed", ticket=ticket_id, error=str(e))
            return "Unknown"

    async def walk_transitions_to(
        self, ticket_id: str, target: str, max_steps: int = 5
    ) -> tuple[bool, list[str]]:
        """Walk through Jira transitions until the ticket reaches the target status.

        Returns (success, steps_taken) where steps_taken lists the transition names applied.
        """
        DONE_KEYWORDS = ["done", "closed", "close", "resolved", "cerrado", "cerrar"]
        TARGET_KEYWORDS = {
            "done": DONE_KEYWORDS,
            "closed": DONE_KEYWORDS,
            "close": DONE_KEYWORDS,
            "delivered": ["delivered", "deliver", "entregado"],
            "in_progress": ["progress", "in progress", "en curso"],
        }
        keywords = TARGET_KEYWORDS.get(target.lower(), [target.lower()])
        steps_taken: list[str] = []

        for _ in range(max_steps):
            current = await self.get_ticket_status(ticket_id)
            if current.lower() in DONE_KEYWORDS and target.lower() in ("done", "closed", "close"):
                logger.info("walk_transitions_already_done", ticket=ticket_id, status=current)
                return True, steps_taken

            transitions = await self.get_available_transitions(ticket_id)
            if not transitions:
                logger.warning("walk_transitions_no_transitions", ticket=ticket_id)
                break

            # Try to find direct match to target
            chosen = None
            for t in transitions:
                name = t["name"].lower()
                if any(kw in name for kw in keywords):
                    chosen = t
                    break

            # If no direct match, try intermediate transitions (e.g., "in progress")
            if not chosen:
                for t in transitions:
                    name = t["name"].lower()
                    if any(kw in name for kw in ["progress", "in progress", "en curso"]):
                        chosen = t
                        break

            if not chosen:
                logger.warning(
                    "walk_transitions_no_match",
                    ticket=ticket_id,
                    target=target,
                    available=[t["name"] for t in transitions],
                )
                break

            # Apply the transition
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        f"{self._api_base}/issue/{ticket_id}/transitions",
                        headers=self._headers,
                        json={"transition": {"id": chosen["id"]}},
                    )
                    resp.raise_for_status()
                    steps_taken.append(chosen["name"])
                    logger.info("walk_transition_applied", ticket=ticket_id, transition=chosen["name"])
            except httpx.HTTPError as e:
                logger.error("walk_transition_failed", ticket=ticket_id, transition=chosen["name"], error=str(e))
                break

        # Check final status
        final = await self.get_ticket_status(ticket_id)
        success = final.lower() in [k for kws in [keywords, DONE_KEYWORDS] for k in kws]
        return success, steps_taken

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
            logger.error("kosin_worklog_delete_failed", ticket=ticket_id, error=f"HTTP {e.response.status_code}: {body}")
            raise RuntimeError(f"HTTP {e.response.status_code} al eliminar worklog de {ticket_id}: {body}")
        except httpx.HTTPError as e:
            error_msg = str(e) or f"{type(e).__name__}: {repr(e)}"
            logger.error("kosin_worklog_delete_failed", ticket=ticket_id, error=error_msg)
            raise RuntimeError(f"Error de conexion al eliminar worklog de {ticket_id}: {error_msg}")


