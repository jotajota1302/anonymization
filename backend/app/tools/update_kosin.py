"""Tool: Create/update tickets in the ticket system (KOSIN/Jira)."""

from langchain_core.tools import tool


@tool
async def update_ticket(
    ticket_id: str,
    comment: str = "",
    status: str = "",
) -> str:
    """Actualiza un ticket en el sistema de tickets con informacion anonimizada.
    Puede anadir comentarios y/o cambiar el estado del ticket.

    Cuando status='done', cierra automaticamente tanto el ticket destino (KOSIN)
    como el ticket origen (Jira fuente).

    IMPORTANTE: Solo pasar datos anonimizados (con tokens como [PERSONA_1]).
    Nunca incluir datos personales reales.

    Args:
        ticket_id: ID del ticket destino (ej: PESESG-123)
        comment: Comentario anonimizado para anadir al ticket
        status: Nuevo estado (in_progress, delivered, done) - dejar vacio si no se cambia
    """
    from ..main import app_state

    kosin = app_state["destination_connector"]
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
                results.append(f"Estado de {ticket_id} (destino) actualizado a '{status}'")
            else:
                results.append(f"Error al actualizar estado de {ticket_id} (destino)")

            # When closing, also close the source (origin) ticket
            if status.lower() == "done":
                try:
                    db = app_state.get("db")
                    connector_router = app_state.get("connector_router")
                    source_connector = app_state.get("jira_connector")

                    if db:
                        mapping = await db.get_ticket_by_kosin_key(ticket_id)
                        if mapping:
                            source_key = mapping.get("source_ticket_id")
                            if source_key:
                                # Resolve connector by prefix if router available
                                if connector_router:
                                    try:
                                        source_connector = connector_router.get_connector(source_key)
                                    except Exception:
                                        pass
                                if source_connector:
                                    ok = await source_connector.update_status(source_key, "done")
                                    if ok:
                                        results.append(f"Ticket origen {source_key} cerrado")
                                    else:
                                        results.append(f"No se pudo cerrar ticket origen {source_key}")
                except Exception as e:
                    results.append(f"Aviso: error al cerrar origen: {str(e)}")

        return " | ".join(results) if results else "No se especifico ninguna accion"
    except Exception as e:
        return f"Error al actualizar ticket: {str(e)}"


@tool
async def create_ticket(
    summary: str,
    description: str,
    priority: str = "Medium",
) -> str:
    """Crea un nuevo ticket anonimizado en el sistema de tickets.

    IMPORTANTE: Solo pasar datos anonimizados (con tokens como [PERSONA_1]).

    Args:
        summary: Resumen anonimizado del ticket
        description: Descripcion anonimizada completa
        priority: Prioridad (Low, Medium, High, Critical)
    """
    from ..main import app_state

    kosin = app_state["destination_connector"]

    try:
        key = await kosin.create_ticket(summary, description, priority)
        if key:
            return f"Ticket creado: {key}"
        return "Error al crear ticket"
    except Exception as e:
        return f"Error al crear ticket: {str(e)}"
