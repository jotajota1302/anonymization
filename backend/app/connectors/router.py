"""ConnectorRouter: multi-source ticket system routing."""

from typing import Dict, List, Tuple, Optional
import structlog

from .base import TicketConnector

logger = structlog.get_logger()


class ConnectorRouter:
    """Routes ticket operations to the correct connector based on ticket ID prefix."""

    def __init__(self):
        self._connectors: Dict[str, TicketConnector] = {}
        self._prefixes: Dict[str, str] = {}  # prefix → system_name

    def register(self, system_name: str, connector: TicketConnector, prefixes: List[str]):
        """Register a connector with its ticket ID prefixes.

        Args:
            system_name: Unique name for this system (e.g., "kosin", "remedy")
            connector: The TicketConnector instance
            prefixes: List of ticket ID prefixes this connector handles
        """
        self._connectors[system_name] = connector
        for prefix in prefixes:
            self._prefixes[prefix] = system_name
        logger.info("connector_registered", system=system_name, prefixes=prefixes)

    def get_connector(self, ticket_id: str) -> Tuple[str, TicketConnector]:
        """Resolve connector by ticket ID prefix.

        Args:
            ticket_id: The ticket identifier (e.g., "INC000001", "SNOW-10001", "PESESG-123")

        Returns:
            Tuple of (system_name, connector)

        Raises:
            ValueError: If no connector matches the ticket ID prefix
        """
        # Try longest prefix match first
        for prefix in sorted(self._prefixes.keys(), key=len, reverse=True):
            if ticket_id.startswith(prefix):
                system_name = self._prefixes[prefix]
                return system_name, self._connectors[system_name]

        raise ValueError(
            f"No connector found for ticket '{ticket_id}'. "
            f"Known prefixes: {list(self._prefixes.keys())}"
        )

    def get_connector_by_name(self, system_name: str) -> Optional[TicketConnector]:
        """Get a connector by its system name."""
        return self._connectors.get(system_name)

    @property
    def systems(self) -> List[str]:
        """List all registered system names."""
        return list(self._connectors.keys())

    async def get_all_board_issues(self) -> List[Dict]:
        """Aggregate board issues from ALL registered systems.

        Each issue gets an additional 'source_system' field.
        """
        all_issues = []
        for system_name, connector in self._connectors.items():
            try:
                if hasattr(connector, 'get_board_issues'):
                    issues = await connector.get_board_issues()
                elif hasattr(connector, 'get_all_tickets'):
                    # Fallback for connectors without get_board_issues
                    tickets = await connector.get_all_tickets()
                    issues = [
                        {
                            "key": t.get("key", ""),
                            "fields": {
                                "summary": t.get("summary", ""),
                                "status": {"name": t.get("status", "Open")},
                                "priority": {"name": t.get("priority", "Medium")},
                                "issuetype": {"name": t.get("issue_type", "Support")},
                            },
                        }
                        for t in tickets
                    ]
                else:
                    continue

                # Tag each issue with source_system
                for issue in issues:
                    issue["source_system"] = system_name

                all_issues.extend(issues)
                logger.info("board_issues_fetched", system=system_name, count=len(issues))
            except Exception as e:
                logger.error("board_issues_failed", system=system_name, error=str(e))

        return all_issues
