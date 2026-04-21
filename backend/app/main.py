"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import json
import structlog

from .config import settings
from .services.database import DatabaseService
from .services.anonymizer import Anonymizer
from .websocket.manager import ConnectionManager
from .connectors.kosin import KosinConnector
from .connectors.router import ConnectorRouter
from .middleware.rate_limiter import RateLimiterMiddleware

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
)

logger = structlog.get_logger()

# Global app state - shared across modules
app_state: dict = {}


async def _init_detector(db):
    """Initialize the PII detector from DB config (or env fallback)."""
    # Try to read saved config from DB
    anon_config = None
    try:
        row = await db.get_system_config("anonymization")
        if row and row.get("extra_config"):
            raw = row["extra_config"]
            if isinstance(raw, str):
                anon_config = json.loads(raw)
            elif isinstance(raw, dict):
                anon_config = raw
    except Exception:
        pass

    if anon_config:
        detector_type = anon_config.get("detector_type", settings.pii_detector).lower()
        presidio_cfg = {
            "score_threshold": anon_config.get("presidio_sensitivity", 65),
            "enabled_entities": anon_config.get("presidio_entities"),
            "excluded_words": anon_config.get("presidio_excluded_words"),
            "min_lengths": anon_config.get("presidio_min_lengths"),
            "model_name": anon_config.get("presidio_model", "es_core_news_lg"),
        }
    else:
        detector_type = settings.pii_detector.lower()
        presidio_cfg = {}

    if detector_type == "none":
        from .services.detection import NullDetector
        logger.info("pii_detector_initialized", type="none", source="db" if anon_config else "env")
        return NullDetector()

    if detector_type == "regex":
        from .services.detection import RegexDetector
        logger.info("pii_detector_initialized", type="regex", source="db" if anon_config else "env")
        return RegexDetector()

    if detector_type == "presidio":
        try:
            from .services.detection import PresidioDetector
            logger.info("pii_detector_initialized", type="presidio", source="db" if anon_config else "env")
            return PresidioDetector(**presidio_cfg)
        except Exception as e:
            logger.warning("presidio_not_available", error=str(e), fallback="regex")
            from .services.detection import RegexDetector
            return RegexDetector()

    # Default: composite
    try:
        from .services.detection import CompositeDetector
        detector = CompositeDetector(presidio_config=presidio_cfg)
        logger.info("pii_detector_initialized", type="composite", source="db" if anon_config else "env")
        return detector
    except Exception as e:
        logger.warning("composite_detector_failed", error=str(e), fallback="regex")
        from .services.detection import RegexDetector
        return RegexDetector()


def _create_connector_from_config(config: dict) -> "TicketConnector":
    """Create a real connector instance from a system_config DB row."""
    connector_type = config.get("connector_type", "jira")
    base_url = config.get("base_url", "")
    token = config.get("auth_token", "")
    project = config.get("project_key", "")
    extra = config.get("extra_config", "{}")
    if isinstance(extra, str):
        try:
            extra = json.loads(extra)
        except (json.JSONDecodeError, TypeError):
            extra = {}

    if connector_type == "jira":
        return KosinConnector(
            base_url=base_url,
            token=token,
            project=project,
            issue_type_id=extra.get("issue_type_id", settings.kosin_issue_type_id),
            extra_config=extra,
        )
    elif connector_type == "remedy":
        from .connectors.remedy import RemedyConnector
        return RemedyConnector(base_url=base_url, token=token, project=project)
    elif connector_type == "servicenow":
        from .connectors.servicenow import ServiceNowConnector
        return ServiceNowConnector(base_url=base_url, token=token, project=project)
    else:
        return KosinConnector(
            base_url=base_url,
            token=token,
            project=project,
        )


async def reload_connectors(db=None):
    """Reload all connectors from DB configuration. Called at startup and on config change."""
    if db is None:
        db = app_state.get("db")
    if not db:
        return

    router = ConnectorRouter()
    configs = await db.get_all_system_configs()

    # Build connectors from active integrations.
    # Collect ALL active destinations so we can warn on duplicates and pick
    # one deterministically (instead of silently keeping the last one seen).
    destinations: list[tuple[str, object]] = []
    for cfg in configs:
        name = cfg.get("system_name", "")
        # Skip internal config entries
        if name in ("anonymization", "agent", "general", "anon_llm"):
            continue
        if not cfg.get("is_active"):
            continue

        try:
            connector = _create_connector_from_config(cfg)
            project_key = cfg.get("project_key", "")
            system_type = cfg.get("system_type", "source")

            if system_type == "destination":
                destinations.append((name, connector))
            if project_key and system_type != "destination":
                router.register(name, connector, [f"{project_key}-"])

            logger.info("connector_loaded", system=name, type=cfg.get("connector_type"),
                        project=project_key, system_type=system_type)
        except Exception as e:
            logger.error("connector_load_failed", system=name, error=str(e))

    # Pick a single destination. Prefer system_name='kosin' if present
    # (legacy alias), otherwise the alphabetically-first name so behaviour
    # is stable across restarts.
    destination_connector = None
    if destinations:
        destinations.sort(key=lambda x: (x[0] != "kosin", x[0]))
        destination_connector = destinations[0][1]
        if len(destinations) > 1:
            logger.warning(
                "multiple_destinations_configured",
                count=len(destinations),
                names=[d[0] for d in destinations],
                active=destinations[0][0],
                hint="Delete duplicate destination rows in system_config to keep one",
            )
        logger.info("active_destination_connector", system=destinations[0][0])

    app_state["connector_router"] = router
    app_state["destination_connector"] = destination_connector
    # jira_connector points to the first registered source
    first_source = router.systems[0] if router.systems else None
    app_state["jira_connector"] = (
        router.get_connector_by_name(first_source) if first_source else destination_connector
    )

    logger.info("connectors_reloaded", systems=router.systems)


async def _seed_default_configs(db):
    """Seed system_config with defaults from .env if not already present."""
    defaults = [
        {
            "system_name": "gdnespain",
            "display_name": "GDNESPAIN (Destino)",
            "system_type": "destination",
            "connector_type": "jira",
            "base_url": settings.kosin_url,
            "auth_token": settings.kosin_token,
            "auth_email": "",
            "project_key": settings.kosin_project,
            "extra_config": json.dumps({
                "issue_type_id": settings.kosin_issue_type_id,
                "board_id": settings.kosin_board_id,
                "parent_key": settings.kosin_parent_key,
            }),
            "is_active": 1,
            "is_mock": 0,
            "polling_interval_sec": 60,
        },
        {
            "system_name": "stdvert1",
            "display_name": "STDVERT1 (Origen)",
            "system_type": "source",
            "connector_type": "jira",
            "base_url": settings.kosin_url,
            "auth_token": settings.kosin_token,
            "auth_email": "",
            "project_key": settings.source_project,
            "extra_config": "{}",
            "is_active": int("stdvert1" in settings.active_sources),
            "is_mock": 0,
            "polling_interval_sec": 60,
        },
    ]
    active_list = [s.strip().lower() for s in settings.active_sources.split(",") if s.strip()]
    for cfg in defaults:
        name = cfg.pop("system_name")
        existing = await db.get_system_config(name)
        if not existing:
            await db.upsert_system_config(name, **cfg)
            logger.info("seeded_system_config", system=name)
        else:
            # Always sync is_active with ACTIVE_SOURCES env var
            should_be_active = 1 if (name in active_list or cfg.get("system_type") == "destination") else 0
            if existing.get("is_active") != should_be_active:
                await db.upsert_system_config(name, is_active=should_be_active)
                logger.info("synced_is_active", system=name, is_active=should_be_active)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup, cleanup on shutdown."""
    logger.info("starting_application", app=settings.app_name)

    # Database
    db = DatabaseService(settings.db_path)
    await db.init()
    await _seed_default_configs(db)
    app_state["db"] = db

    # PII Detector (reads saved config from DB)
    detector = await _init_detector(db)
    app_state["detector"] = detector

    # Anonymizer
    anonymizer = Anonymizer(detector=detector)
    app_state["anonymizer"] = anonymizer

    # WebSocket manager
    ws_manager = ConnectionManager()
    app_state["ws_manager"] = ws_manager

    # Load connectors from DB config
    await reload_connectors(db)

    # System prompt (stored in app_state for hot-reload)
    from .services.agent import DEFAULT_SYSTEM_PROMPT
    app_state["system_prompt"] = DEFAULT_SYSTEM_PROMPT

    # Anonymization LLM (optional, small/fast model for PII filtering)
    anon_llm = None
    if settings.anon_llm_provider:
        try:
            from .services.agent import AnonymizationLLM
            anon_llm = AnonymizationLLM(
                provider=settings.anon_llm_provider,
                model=settings.anon_llm_model,
                temperature=settings.anon_llm_temperature,
            )
            app_state["anon_llm"] = anon_llm
            logger.info("anon_llm_initialized", provider=settings.anon_llm_provider, model=settings.anon_llm_model)
        except Exception as e:
            logger.warning("anon_llm_init_failed", error=str(e), hint="PII filtering will use regex/Presidio only")
            anon_llm = None

    # Resolution Agent (main LLM for chat + tools).
    # Agent config (provider / model / axet_project_id / axet_asset_id) lives
    # in the system_config table; propagate it into settings so that
    # AnonymizationAgent._create_llm() picks the right Axet project on startup
    # instead of failing because the .env has no axet_project_id.
    try:
        import json as _json
        agent_row = await db.get_system_config("agent")
        if agent_row and agent_row.get("extra_config"):
            raw = agent_row["extra_config"]
            cfg = _json.loads(raw) if isinstance(raw, str) else (raw or {})
            if cfg.get("axet_project_id"):
                settings.axet_project_id = cfg["axet_project_id"]
            if cfg.get("axet_asset_id"):
                settings.axet_asset_id = cfg["axet_asset_id"]
            if cfg.get("model"):
                settings.axet_model = cfg["model"]
    except Exception as e:
        logger.warning("agent_config_prewarm_failed", error=str(e))

    try:
        from .services.agent import AnonymizationAgent
        agent = AnonymizationAgent(
            anonymizer=anonymizer,
            db=db,
            ws_manager=ws_manager,
            anon_llm=anon_llm,
        )
        app_state["agent"] = agent
        logger.info("resolution_agent_initialized", provider=settings.llm_provider)
    except Exception as e:
        logger.warning("agent_init_failed", error=str(e),
                       hint="Inicia sesion OKTA en /config para obtener un token Axet valido")
        app_state["agent"] = None

    # Start Axet token auto-refresh background task
    from .routers.axet_auth import start_auto_refresh, stop_auto_refresh
    start_auto_refresh()

    logger.info("application_started")
    yield

    # Cleanup
    logger.info("shutting_down")
    stop_auto_refresh()
    app_state.clear()


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

# Rate limiter
app.add_middleware(RateLimiterMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
from .routers import tickets, chat, admin, config, axet_auth  # noqa: E402

app.include_router(tickets.router)
app.include_router(chat.router)
app.include_router(admin.router)
app.include_router(config.router)
app.include_router(axet_auth.router)


@app.get("/health")
async def health_check():
    router = app_state.get("connector_router")
    return {
        "status": "healthy",
        "app": settings.app_name,
        "agent_ready": app_state.get("agent") is not None,
        "active_systems": router.systems if router else [],
    }


@app.get("/api/status")
async def api_status():
    db = app_state.get("db")
    ticket_count = 0
    if db:
        tickets = await db.get_all_tickets()
        ticket_count = len(tickets)

    router = app_state.get("connector_router")
    return {
        "tickets_total": ticket_count,
        "ws_connections": len(app_state.get("ws_manager", ConnectionManager())._connections),
        "active_systems": router.systems if router else [],
    }
