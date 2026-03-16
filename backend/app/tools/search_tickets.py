"""Tool: Search tickets using JQL queries."""

from langchain_core.tools import tool


@tool
async def search_tickets(jql_query: str, max_results: int = 20) -> str:
    """Busca tickets usando una consulta JQL (Jira Query Language).

    Devuelve una lista de tickets que coinciden con la consulta,
    con sus datos anonimizados.

    Args:
        jql_query: Consulta JQL (ej: 'status = Open ORDER BY priority DESC')
        max_results: Numero maximo de resultados (default 20, max 50)
    """
    from ..main import app_state

    connector = app_state["kosin_connector"]

    max_results = min(max_results, 50)

    try:
        issues = await connector.search_issues(jql_query, max_results)

        if not issues:
            return f"No se encontraron tickets para la consulta: {jql_query}"

        lines = [f"Resultados ({len(issues)} tickets):\n"]
        for issue in issues:
            lines.append(
                f"- **{issue['key']}** | {issue.get('status', 'N/A')} | "
                f"{issue.get('priority', 'N/A')} | {issue.get('summary', 'Sin resumen')}"
            )

        return "\n".join(lines)
    except NotImplementedError:
        return "El conector actual no soporta busqueda JQL."
    except Exception as e:
        return f"Error al buscar tickets: {str(e)}"
