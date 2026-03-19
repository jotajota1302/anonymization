"""Tools: Worklog management (add, get, delete) for Jira/KOSIN tickets."""

from langchain_core.tools import tool


@tool
async def add_worklog(ticket_id: str, time_spent: str, comment: str = "") -> str:
    """Imputa horas de trabajo en un ticket.

    Args:
        ticket_id: ID del ticket (ej: PESESG-123)
        time_spent: Tiempo en formato Jira (ej: '2h', '1h 30m', '3d')
        comment: Comentario opcional describiendo el trabajo realizado
    """
    from ..main import app_state

    kosin = app_state["destination_connector"]

    try:
        success = await kosin.add_worklog(ticket_id, time_spent, comment)
        if success:
            msg = f"Worklog registrado en {ticket_id}: {time_spent}"
            if comment:
                msg += f" ({comment})"
            return msg
        return f"Error al registrar worklog en {ticket_id}"
    except NotImplementedError:
        return "El conector actual no soporta worklogs."
    except Exception as e:
        return f"Error al registrar worklog: {str(e)}"


@tool
async def get_worklogs(ticket_id: str) -> str:
    """Consulta las horas imputadas en un ticket.

    Args:
        ticket_id: ID del ticket (ej: PESESG-123)
    """
    from ..main import app_state

    kosin = app_state["destination_connector"]

    try:
        worklogs = await kosin.get_worklogs(ticket_id)

        if not worklogs:
            return f"No hay worklogs registrados en {ticket_id}"

        total_seconds = sum(w.get("timeSpentSeconds", 0) for w in worklogs)
        total_hours = total_seconds / 3600

        lines = [f"Worklogs de {ticket_id} (total: {total_hours:.1f}h):\n"]
        for w in worklogs:
            line = (
                f"- ID: {w['id']} | {w.get('timeSpent', 'N/A')} | "
                f"{w.get('author', 'N/A')} | {w.get('started', '')[:10]}"
            )
            if w.get("comment"):
                line += f" | {w['comment']}"
            lines.append(line)

        return "\n".join(lines)
    except NotImplementedError:
        return "El conector actual no soporta worklogs."
    except Exception as e:
        return f"Error al consultar worklogs: {str(e)}"


@tool
async def delete_worklog(ticket_id: str, worklog_id: str) -> str:
    """Elimina una imputacion de horas de un ticket.

    Args:
        ticket_id: ID del ticket (ej: PESESG-123)
        worklog_id: ID del worklog a eliminar
    """
    from ..main import app_state

    kosin = app_state["destination_connector"]

    try:
        success = await kosin.delete_worklog(ticket_id, worklog_id)
        if success:
            return f"Worklog {worklog_id} eliminado de {ticket_id}"
        return f"Error al eliminar worklog {worklog_id} de {ticket_id}"
    except NotImplementedError:
        return "El conector actual no soporta worklogs."
    except Exception as e:
        return f"Error al eliminar worklog: {str(e)}"
