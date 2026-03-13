"""Tool: Execute controlled technical actions (allowlist-based)."""

import asyncio
from typing import Optional
from langchain_core.tools import tool
import structlog

logger = structlog.get_logger()

# Allowlist of permitted actions and their simulated responses
ALLOWED_ACTIONS = {
    "get_logs": {
        "description": "Obtener logs de un servicio",
        "params": ["service", "interval"],
    },
    "check_status": {
        "description": "Verificar estado de un servicio",
        "params": ["service"],
    },
    "restart_service": {
        "description": "Reiniciar un servicio aprobado",
        "params": ["service"],
    },
    "check_connectivity": {
        "description": "Verificar conectividad de red",
        "params": ["service"],
    },
}


async def _simulate_action(action: str, params: dict) -> str:
    """Simulate action execution for pilot. Replace with real implementations."""
    await asyncio.sleep(0.5)  # Simulate latency

    if action == "get_logs":
        service = params.get("service", "unknown")
        interval = params.get("interval", "1h")
        return (
            f"Logs de {service} (ultimas {interval}):\n"
            f"[2026-03-13 08:47:12] ERROR: Connection refused on port 5432\n"
            f"[2026-03-13 08:47:15] WARN: Retry attempt 1/3 failed\n"
            f"[2026-03-13 08:47:20] ERROR: Database service unreachable\n"
            f"[2026-03-13 09:00:01] INFO: Service health check failed\n"
        )
    elif action == "check_status":
        service = params.get("service", "unknown")
        return (
            f"Estado de {service}:\n"
            f"- Servicio: RUNNING\n"
            f"- CPU: 45%\n"
            f"- Memoria: 2.3GB/8GB\n"
            f"- Uptime: 4h 23m\n"
            f"- Conexiones activas: 12\n"
        )
    elif action == "restart_service":
        service = params.get("service", "unknown")
        return (
            f"Reinicio de {service}:\n"
            f"- Servicio detenido correctamente\n"
            f"- Limpieza de cache completada\n"
            f"- Servicio iniciado\n"
            f"- Estado: RUNNING\n"
            f"- Tiempo de reinicio: 45 segundos\n"
        )
    elif action == "check_connectivity":
        service = params.get("service", "unknown")
        return (
            f"Conectividad de {service}:\n"
            f"- Ping: OK (12ms)\n"
            f"- Puerto 443: OPEN\n"
            f"- Puerto 5432: OPEN\n"
            f"- DNS: OK\n"
        )

    return f"Accion '{action}' ejecutada correctamente"


@tool
async def execute_action(
    action: str,
    service: str,
    interval: str = "1h",
) -> str:
    """Ejecuta una accion tecnica controlada sobre un servicio.

    Acciones permitidas:
    - get_logs: Obtener logs de un servicio (params: service, interval)
    - check_status: Verificar estado de un servicio (params: service)
    - restart_service: Reiniciar un servicio (params: service)
    - check_connectivity: Verificar conectividad (params: service)

    Args:
        action: Nombre de la accion a ejecutar
        service: Nombre o identificador del servicio objetivo
        interval: Intervalo de tiempo para logs (default: 1h)
    """
    # Validate action is in allowlist
    if action not in ALLOWED_ACTIONS:
        allowed = ", ".join(ALLOWED_ACTIONS.keys())
        return (
            f"Accion '{action}' NO PERMITIDA. "
            f"Acciones disponibles: {allowed}"
        )

    params = {"service": service, "interval": interval}

    logger.info(
        "action_executed",
        action=action,
        service=service,
        params=params,
    )

    # Log to audit via app_state
    try:
        from ..main import app_state
        db = app_state.get("db")
        if db:
            await db.add_audit_log(
                operator_id="operator",
                action=f"execute_action:{action}",
                ticket_mapping_id=0,
                details=f"service={service}, interval={interval}",
            )
    except Exception:
        pass

    result = await _simulate_action(action, params)
    return result
