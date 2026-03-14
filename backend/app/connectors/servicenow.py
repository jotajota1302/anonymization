"""MockServiceNowConnector: Mock ServiceNow connector with realistic Spanish insurance tickets."""

from typing import List, Dict, Optional
from datetime import datetime
import structlog

from .base import TicketConnector

logger = structlog.get_logger()

MOCK_SERVICENOW_TICKETS = {
    "SNOW-10001": {
        "key": "SNOW-10001",
        "summary": "Alta usuario Active Directory para Cristina Romero - nueva incorporacion",
        "description": (
            "Solicitud de alta en Active Directory para Cristina Romero "
            "(cristina.romero@seguros-nacional.com, tel: +34 622 456 789, "
            "DNI: 78901234K). Nueva incorporacion al departamento de Siniestros "
            "en la oficina de Madrid, Calle Serrano 85, 28006. "
            "Fecha de incorporacion: 17/03/2026. Necesita acceso a: "
            "sistema de gestion de polizas, correo corporativo y VPN. "
            "Equipo asignado: portatil Dell Latitude 5540 (IP asignada: 10.30.40.55). "
            "Su IBAN para nomina: ES2114650100722030876543."
        ),
        "status": "Open",
        "priority": "Medium",
        "created": "2026-03-13T10:00:00Z",
        "reporter": "RRHH Sistemas",
        "assignee": "Equipo Identidad",
        "issue_type": "Request",
    },
    "SNOW-10002": {
        "key": "SNOW-10002",
        "summary": "Sustitucion portatil averiado - Pablo Hernandez comercial Sevilla",
        "description": (
            "El comercial Pablo Hernandez (pablo.hernandez@seguros-nacional.com, "
            "tel: +34 687 654 321, DNI: 56789012L) necesita sustitucion urgente "
            "de su portatil HP EliteBook que no enciende. Pablo trabaja en la "
            "delegacion de Sevilla, Avenida de la Constitucion 20, 41004. "
            "Tiene reunion con cliente importante el jueves 16/03. "
            "IP del equipo averiado: 10.40.50.12. Matricula vehiculo empresa: "
            "2198 FNM. Necesita los datos migrados del disco duro si es posible."
        ),
        "status": "Open",
        "priority": "High",
        "created": "2026-03-13T11:30:00Z",
        "reporter": "Pablo Hernandez",
        "assignee": "Equipo Puesto de Trabajo",
        "issue_type": "Request",
    },
    "SNOW-10003": {
        "key": "SNOW-10003",
        "summary": "Rendimiento degradado app gestion de polizas - Sara Dominguez QA",
        "description": (
            "Sara Dominguez (sara.dominguez@seguros-nacional.com, tel: +34 698 111 222, "
            "DNI: 89012345M) del equipo de QA reporta que la aplicacion de gestion "
            "de polizas tiene tiempos de respuesta superiores a 15 segundos desde "
            "el despliegue del viernes. El servidor de aplicaciones app-polizas-01 "
            "(IP: 10.60.70.80) muestra uso de CPU al 95%. Sara esta en la oficina "
            "de Valencia, Plaza del Ayuntamiento 3, 46002. Los agentes de atencion "
            "al cliente reportan quejas por lentitud en la emision de polizas. "
            "Servidor de base de datos asociado: db-polizas-master (IP: 10.60.70.81)."
        ),
        "status": "Open",
        "priority": "Critical",
        "created": "2026-03-13T07:45:00Z",
        "reporter": "Sara Dominguez",
        "assignee": "Equipo Aplicaciones",
        "issue_type": "Incident",
    },
}


class MockServiceNowConnector(TicketConnector):
    """Mock ServiceNow connector with realistic Spanish insurance PII data."""

    def __init__(self):
        self.tickets = dict(MOCK_SERVICENOW_TICKETS)
        self.comments: Dict[str, List[Dict]] = {k: [] for k in self.tickets}
        logger.info("mock_servicenow_initialized", tickets=len(self.tickets))

    async def get_ticket(self, ticket_id: str) -> Dict:
        ticket = self.tickets.get(ticket_id)
        if not ticket:
            raise ValueError(f"ServiceNow ticket {ticket_id} not found")
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

    async def delete_ticket(self, ticket_id: str) -> bool:
        if ticket_id in self.tickets:
            del self.tickets[ticket_id]
            self.comments.pop(ticket_id, None)
            return True
        return False

    async def download_attachment(self, attachment_url: str) -> bytes:
        return b""

    async def create_ticket(
        self, summary: str, description: str, priority: str = "Medium", **kwargs
    ) -> Optional[str]:
        num = 10001 + len(self.tickets)
        key = f"SNOW-{num}"
        self.tickets[key] = {
            "key": key,
            "summary": summary,
            "description": description,
            "status": "Open",
            "priority": priority,
            "created": datetime.utcnow().isoformat(),
            "reporter": kwargs.get("reporter", "system"),
            "assignee": "Equipo Soporte",
            "issue_type": "Request",
        }
        self.comments[key] = []
        return key

    async def get_board_issues(self) -> List[Dict]:
        """Return tickets in Jira-compatible board format."""
        issues = []
        for key, ticket in self.tickets.items():
            issues.append({
                "key": key,
                "fields": {
                    "summary": ticket.get("summary", ""),
                    "status": {"name": ticket.get("status", "Open")},
                    "priority": {"name": ticket.get("priority", "Medium")},
                    "issuetype": {"name": ticket.get("issue_type", "Request")},
                },
            })
        return issues
