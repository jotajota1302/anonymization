"""Tool: Create/update tickets in KOSIN (internal Jira)."""

from langchain_core.tools import tool


@tool
async def update_kosin(
    ticket_id: str,
    comment: str = "",
    status: str = "",
) -> str:
    """Actualiza un ticket en KOSIN (sistema interno) con informacion anonimizada.
    Puede anadir comentarios y/o cambiar el estado del ticket.

    IMPORTANTE: Solo pasar datos anonimizados (con tokens como [PERSONA_1]).
    Nunca incluir datos personales reales.

    Args:
        ticket_id: ID del ticket en KOSIN (ej: KOS-001)
        comment: Comentario anonimizado para anadir al ticket
        status: Nuevo estado (in_progress, delivered, done) - dejar vacio si no se cambia
    """
    from ..main import app_state

    kosin = app_state["kosin_connector"]
    results = []

    try:
        if comment:
            success = await kosin.add_comment(ticket_id, comment)
            if success:
                results.append(f"Comentario anadido a {ticket_id}")
            else:
                results.append(f"Error al anadir comentario a {ticket_id}")

        if status:
            success = await kosin.update_status(ticket_id, status)
            if success:
                results.append(f"Estado de {ticket_id} actualizado a '{status}'")
            else:
                results.append(f"Error al actualizar estado de {ticket_id}")

        return " | ".join(results) if results else "No se especifico ninguna accion"
    except Exception as e:
        return f"Error al actualizar KOSIN: {str(e)}"


@tool
async def create_kosin_ticket(
    summary: str,
    description: str,
    priority: str = "Medium",
) -> str:
    """Crea un nuevo ticket anonimizado en KOSIN.

    IMPORTANTE: Solo pasar datos anonimizados (con tokens como [PERSONA_1]).

    Args:
        summary: Resumen anonimizado del ticket
        description: Descripcion anonimizada completa
        priority: Prioridad (Low, Medium, High, Critical)
    """
    from ..main import app_state

    kosin = app_state["kosin_connector"]

    try:
        key = await kosin.create_ticket(summary, description, priority)
        if key:
            return f"Ticket creado en KOSIN: {key}"
        return "Error al crear ticket en KOSIN"
    except Exception as e:
        return f"Error al crear ticket en KOSIN: {str(e)}"
