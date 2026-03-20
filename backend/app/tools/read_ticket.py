"""Tool: Read ticket from source system (Jira)."""

from langchain_core.tools import tool


@tool
async def read_ticket(ticket_id: str) -> str:
    """Lee el ticket completo del sistema origen (Jira) por su ID.
    Usa esta herramienta para obtener los detalles del ticket incluyendo
    descripcion, estado, prioridad y comentarios.

    Args:
        ticket_id: ID del ticket en el sistema origen (ej: PROJ-101)
    """
    from ..main import app_state

    # Use router to resolve connector by ticket prefix, fallback to jira_connector
    router = app_state.get("connector_router")
    if router:
        try:
            _, connector = router.get_connector(ticket_id)
        except ValueError:
            connector = app_state["jira_connector"]
    else:
        connector = app_state["jira_connector"]
    anonymizer = app_state["anonymizer"]

    try:
        ticket = await connector.get_ticket(ticket_id)
        comments = await connector.get_comments(ticket_id)

        # Build full text for context
        result = (
            f"Ticket: {ticket['key']}\n"
            f"Estado: {ticket['status']}\n"
            f"Prioridad: {ticket['priority']}\n"
            f"Resumen: {ticket['summary']}\n"
            f"Descripcion: {ticket['description']}\n"
        )

        if comments:
            result += "\nComentarios:\n"
            for c in comments:
                result += f"- [{c.get('author', 'unknown')}]: {c['body']}\n"

        # Apply active substitution map so the agent only ever sees anonymized content
        sub_map = app_state.get("active_sub_map", {})
        if sub_map:
            result = anonymizer.filter_output(result, sub_map)

        return result
    except Exception as e:
        return f"Error al leer ticket {ticket_id}: {str(e)}"
