"""Jira connector - Mock implementation for pilot, real implementation for production."""

from typing import List, Dict, Optional
from datetime import datetime
import structlog

from .base import TicketConnector

logger = structlog.get_logger()


# Mock ticket data with fake PII for testing
MOCK_TICKETS = {
    "PROJ-101": {
        "key": "PROJ-101",
        "summary": "Error de conectividad en servidor de produccion reportado por Juan Garcia",
        "description": (
            "El usuario Juan Garcia (juan.garcia@acme.com, tel: +34 612 345 678, "
            "DNI: 12345678A) reporta que el servidor servidor-prod-042 (IP: 192.168.1.50) "
            "no responde desde las 09:00 del dia de hoy. El servicio de base de datos "
            "PostgreSQL en el puerto 5432 parece estar caido. La cuenta bancaria para "
            "facturacion es ES7921000813610123456789. "
            "Ubicacion del centro de datos: Madrid, Calle Gran Via 28."
        ),
        "status": "Open",
        "priority": "High",
        "created": "2026-03-10T09:15:00Z",
        "reporter": "Juan Garcia",
        "assignee": "Equipo Soporte Offshore",
    },
    "PROJ-102": {
        "key": "PROJ-102",
        "summary": "Maria Lopez solicita reseteo de contrasena en sistema CRM",
        "description": (
            "La empleada Maria Lopez (maria.lopez@empresa.es, tel: +34 655 987 321, "
            "DNI: Y7654321B) necesita un reseteo de su contrasena en el sistema CRM. "
            "Su ultimo acceso fue desde la IP 10.0.0.25. Trabaja en la oficina de "
            "Barcelona, Avenida Diagonal 450. Su cuenta de facturacion: "
            "ES1234567890123456789012."
        ),
        "status": "Open",
        "priority": "Medium",
        "created": "2026-03-11T11:30:00Z",
        "reporter": "Maria Lopez",
        "assignee": "Equipo Soporte Offshore",
    },
    "PROJ-103": {
        "key": "PROJ-103",
        "summary": "Carlos Martinez reporta lentitud en aplicacion web interna",
        "description": (
            "Carlos Martinez (carlos.martinez@corp.com, tel: 0034 698 123 456, "
            "DNI: 98765432C) informa de lentitud extrema en la aplicacion web interna "
            "app-interna-web01. Los tiempos de respuesta superan los 30 segundos. "
            "El servidor afectado tiene IP 172.16.0.100. Carlos trabaja desde la "
            "oficina de Valencia, Plaza del Ayuntamiento 10."
        ),
        "status": "Open",
        "priority": "High",
        "created": "2026-03-11T14:00:00Z",
        "reporter": "Carlos Martinez",
        "assignee": "Equipo Soporte Offshore",
    },
    "PROJ-104": {
        "key": "PROJ-104",
        "summary": "Ana Fernandez necesita acceso VPN para teletrabajo",
        "description": (
            "Ana Fernandez (ana.fernandez@acme.com, tel: +34 611 222 333, "
            "DNI: X1234567D) solicita configuracion de VPN para acceso remoto. "
            "Su equipo tiene la IP publica 83.45.120.10. Ana trabaja desde su "
            "domicilio en Sevilla, Calle Sierpes 15. Necesita acceso al servidor "
            "file-server-central (IP: 192.168.10.5)."
        ),
        "status": "Open",
        "priority": "Medium",
        "created": "2026-03-12T08:45:00Z",
        "reporter": "Ana Fernandez",
        "assignee": "Equipo Soporte Offshore",
    },
    "PROJ-105": {
        "key": "PROJ-105",
        "summary": "Pedro Sanchez solicita revision de logs de seguridad",
        "description": (
            "El administrador Pedro Sanchez (pedro.sanchez@internal.net, "
            "tel: +34 677 888 999, DNI: 56789012E) detecta accesos sospechosos "
            "desde la IP 45.33.32.156 al servidor de autenticacion auth-server-01 "
            "(IP: 10.10.10.1). Se han registrado 500 intentos fallidos de login "
            "en las ultimas 2 horas. Pedro esta en la oficina de Bilbao, "
            "Gran Via 25."
        ),
        "status": "Open",
        "priority": "Critical",
        "created": "2026-03-12T16:20:00Z",
        "reporter": "Pedro Sanchez",
        "assignee": "Equipo Soporte Offshore",
    },
}


class MockJiraConnector(TicketConnector):
    """Mock Jira connector with fake PII data for pilot testing."""

    def __init__(self):
        self.tickets = dict(MOCK_TICKETS)
        self.comments: Dict[str, List[Dict]] = {k: [] for k in self.tickets}
        logger.info("mock_jira_initialized", tickets=len(self.tickets))

    async def get_ticket(self, ticket_id: str) -> Dict:
        ticket = self.tickets.get(ticket_id)
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found")
        return ticket

    async def get_all_tickets(self) -> List[Dict]:
        return list(self.tickets.values())

    async def get_comments(self, ticket_id: str) -> List[Dict]:
        return self.comments.get(ticket_id, [])

    async def update_status(self, ticket_id: str, status: str) -> bool:
        if ticket_id in self.tickets:
            self.tickets[ticket_id]["status"] = status
            return True
        return False

    async def add_comment(self, ticket_id: str, comment: str) -> bool:
        if ticket_id in self.comments:
            self.comments[ticket_id].append({
                "body": comment,
                "author": "system",
                "created": datetime.utcnow().isoformat(),
            })
            return True
        return False

    async def download_attachment(self, attachment_url: str) -> bytes:
        return b""

    async def create_ticket(
        self, summary: str, description: str, priority: str = "Medium", **kwargs
    ) -> Optional[str]:
        ticket_num = len(self.tickets) + 101
        key = f"PROJ-{ticket_num}"
        self.tickets[key] = {
            "key": key,
            "summary": summary,
            "description": description,
            "status": "Open",
            "priority": priority,
            "created": datetime.utcnow().isoformat(),
            "reporter": kwargs.get("reporter", "system"),
            "assignee": "Equipo Soporte Offshore",
        }
        self.comments[key] = []
        return key


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

    async def create_ticket(
        self, summary: str, description: str, priority: str = "Medium", **kwargs
    ) -> Optional[str]:
        logger.warning("jira_create_ticket: use KOSIN connector for creating tickets")
        return None
