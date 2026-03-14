"""MockRemedyConnector: Mock Remedy ITSM connector with realistic Spanish insurance tickets."""

from typing import List, Dict, Optional
from datetime import datetime
import structlog

from .base import TicketConnector

logger = structlog.get_logger()

MOCK_REMEDY_TICKETS = {
    "INC000001": {
        "key": "INC000001",
        "summary": "Caida SAP modulo FI - Elena Torres no puede generar facturas",
        "description": (
            "La usuaria Elena Torres (elena.torres@seguros-iberica.es, tel: +34 615 234 891, "
            "DNI: 45678912F) reporta que el modulo SAP FI no responde desde las 08:30. "
            "El servidor sap-prod-fin01 (IP: 10.20.30.40) devuelve timeout en todas las "
            "transacciones. Elena trabaja desde la oficina central en Madrid, "
            "Calle Alcala 45, 28014. Su cuenta corporativa para reembolsos: "
            "ES6621000418401234567891. Matricula del vehiculo de empresa: 4521 BKF. "
            "Impacto critico: no se pueden procesar polizas de auto ni hogar."
        ),
        "status": "Open",
        "priority": "Critical",
        "created": "2026-03-13T08:35:00Z",
        "reporter": "Elena Torres",
        "assignee": "Equipo Soporte SAP",
        "issue_type": "Incident",
    },
    "INC000002": {
        "key": "INC000002",
        "summary": "Error autenticacion LDAP para Rafael Moreno en oficina Zaragoza",
        "description": (
            "Rafael Moreno (rafael.moreno@seguros-iberica.es, tel: +34 676 543 210, "
            "DNI: 23456789G) no puede autenticarse en el dominio corporativo desde "
            "esta manana. Su equipo portatil (IP: 10.50.60.15) muestra error "
            "'LDAP bind failed'. Rafael esta en la delegacion de Zaragoza, "
            "Paseo Independencia 32, 50001. Ha intentado resetear la contrasena "
            "sin exito. Necesita acceso urgente al sistema de gestion de siniestros."
        ),
        "status": "Open",
        "priority": "High",
        "created": "2026-03-13T09:10:00Z",
        "reporter": "Rafael Moreno",
        "assignee": "Equipo Soporte Infraestructura",
        "issue_type": "Incident",
    },
    "CHG000001": {
        "key": "CHG000001",
        "summary": "Migracion base de datos Oracle a PostgreSQL - entorno pre-produccion",
        "description": (
            "Responsable del cambio: Laura Navarro (laura.navarro@seguros-iberica.es, "
            "tel: +34 691 876 543, DNI: 67890123H). Migracion planificada del esquema "
            "de polizas desde Oracle 19c (IP: 10.10.5.20) a PostgreSQL 16 "
            "(IP: 10.10.5.25). Ventana de mantenimiento: sabado 15/03 de 22:00 a 06:00. "
            "Laura coordina desde la sede central en Barcelona, "
            "Avenida Diagonal 612, 08021. Cuenta del proyecto: ES4901280010000123456789. "
            "Requiere aprobacion del CAB antes de ejecucion."
        ),
        "status": "Open",
        "priority": "Medium",
        "created": "2026-03-12T14:20:00Z",
        "reporter": "Laura Navarro",
        "assignee": "Equipo DBA",
        "issue_type": "Change",
    },
    "PRB000001": {
        "key": "PRB000001",
        "summary": "VPN intermitente para agentes comerciales en zona sur",
        "description": (
            "Investigadora: Monica Alvarez (monica.alvarez@seguros-iberica.es, "
            "tel: +34 654 321 987, DNI: 34567890J). Se han recibido 15 incidencias "
            "en la ultima semana de agentes comerciales en Malaga, Granada y Almeria "
            "reportando desconexiones VPN cada 20-30 minutos. El concentrador VPN "
            "(IP: 85.120.45.200) muestra logs de renegociacion TLS frecuente. "
            "Monica trabaja desde la oficina de Malaga, Plaza de la Marina 5, 29001. "
            "Los agentes afectados no pueden acceder al cotizador de polizas. "
            "IBAN para gastos de investigacion: ES7630060000001234567890. "
            "Matricula vehiculo de peritaje: 7834 GHT."
        ),
        "status": "Open",
        "priority": "High",
        "created": "2026-03-11T16:45:00Z",
        "reporter": "Monica Alvarez",
        "assignee": "Equipo Redes",
        "issue_type": "Problem",
    },
}


class MockRemedyConnector(TicketConnector):
    """Mock Remedy ITSM connector with realistic Spanish insurance PII data."""

    def __init__(self):
        self.tickets = dict(MOCK_REMEDY_TICKETS)
        self.comments: Dict[str, List[Dict]] = {k: [] for k in self.tickets}
        logger.info("mock_remedy_initialized", tickets=len(self.tickets))

    async def get_ticket(self, ticket_id: str) -> Dict:
        ticket = self.tickets.get(ticket_id)
        if not ticket:
            raise ValueError(f"Remedy ticket {ticket_id} not found")
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
        self.tickets[f"INC{len(self.tickets)+1:06d}"] = {
            "key": f"INC{len(self.tickets)+1:06d}",
            "summary": summary,
            "description": description,
            "status": "Open",
            "priority": priority,
            "created": datetime.utcnow().isoformat(),
            "reporter": kwargs.get("reporter", "system"),
            "assignee": "Equipo Soporte",
            "issue_type": "Incident",
        }
        key = f"INC{len(self.tickets):06d}"
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
                    "issuetype": {"name": ticket.get("issue_type", "Incident")},
                },
            })
        return issues
