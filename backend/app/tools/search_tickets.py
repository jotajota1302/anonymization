"""Tool: Search tickets using JQL queries across source systems."""

from langchain_core.tools import tool


@tool
async def search_tickets(jql_query: str, max_results: int = 20) -> str:
    """Busca tickets en los sistemas origen usando una consulta JQL (Jira Query Language).

    Busca en todos los conectores source registrados (ej: STDVERT1, Remedy, etc.)
    para encontrar tickets similares, resueltos, o que coincidan con la consulta.

    Args:
        jql_query: Consulta JQL (ej: 'status = Done AND text ~ "error login" ORDER BY created DESC')
        max_results: Numero maximo de resultados (default 20, max 50)
    """
    from ..main import app_state
    from ..services.anonymizer import Anonymizer
    from ..services.detection import CompositeDetector

    connector_router = app_state.get("connector_router")
    max_results = min(max_results, 50)

    all_issues = []

    # Search across all registered source connectors
    if connector_router:
        for system_name in connector_router.systems:
            connector = connector_router.get_connector_by_name(system_name)
            if connector and hasattr(connector, "search_issues"):
                try:
                    issues = await connector.search_issues(jql_query, max_results)
                    for issue in issues:
                        issue["source_system"] = system_name
                    all_issues.extend(issues)
                except Exception as e:
                    all_issues.append({"_error": f"{system_name}: {str(e)}"})

    # Fallback: also search in kosin_connector (destination) if no router results
    if not all_issues:
        connector = app_state.get("kosin_connector")
        if connector and hasattr(connector, "search_issues"):
            try:
                issues = await connector.search_issues(jql_query, max_results)
                for issue in issues:
                    issue["source_system"] = "kosin"
                all_issues.extend(issues)
            except Exception:
                pass

    # Filter out errors and format
    errors = [i for i in all_issues if "_error" in i]
    issues = [i for i in all_issues if "_error" not in i]

    if not issues and not errors:
        return f"No se encontraron tickets para la consulta: {jql_query}"

    # Anonymize summaries to prevent PII leaks in search results
    try:
        detector = app_state.get("detector") or CompositeDetector()
        anonymizer = Anonymizer(detector=detector)
    except Exception:
        from ..services.detection import RegexDetector
        anonymizer = Anonymizer(detector=RegexDetector())

    lines = [f"Resultados ({len(issues)} tickets):\n"]
    lines.append("| Ticket | Sistema | Estado | Prioridad | Resumen |")
    lines.append("|--------|---------|--------|-----------|---------|")
    for issue in issues[:max_results]:
        src = issue.get("source_system", "").upper()
        key = issue.get("key", "?")
        status = issue.get("status", "N/A")
        priority = issue.get("priority", "N/A")
        raw_summary = issue.get("summary", "Sin resumen")
        # Anonymize the summary — discard the sub_map (we don't need reverse mapping)
        safe_summary, _ = anonymizer.anonymize(raw_summary)
        safe_summary = safe_summary.replace("|", "-")
        lines.append(f"| **{key}** | {src} | {status} | {priority} | {safe_summary} |")

    if errors:
        lines.append(f"\n(Errores en {len(errors)} sistema(s): {', '.join(e['_error'] for e in errors)})")

    return "\n".join(lines)
