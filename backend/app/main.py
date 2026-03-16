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
from .connectors.jira import MockJiraConnector
from .connectors.kosin import MockKosinConnector, KosinConnector
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


def _init_detector():
    """Initialize the PII detector based on config."""
    detector_type = settings.pii_detector.lower()

    if detector_type == "regex":
        from .services.detection import RegexDetector
        logger.info("pii_detector_initialized", type="regex")
        return RegexDetector()

    if detector_type == "presidio":
        try:
            from .services.detection import PresidioDetector
            logger.info("pii_detector_initialized", type="presidio")
            return PresidioDetector()
        except Exception as e:
            logger.warning("presidio_not_available", error=str(e), fallback="regex")
            from .services.detection import RegexDetector
            return RegexDetector()

    # Default: composite
    try:
        from .services.detection import CompositeDetector
        detector = CompositeDetector()
        logger.info("pii_detector_initialized", type="composite")
        return detector
    except Exception as e:
        logger.warning("composite_detector_failed", error=str(e), fallback="regex")
        from .services.detection import RegexDetector
        return RegexDetector()


async def _seed_default_configs(db):
    """Seed system_config with defaults from .env if not already present."""
    defaults = [
        {
            "system_name": "kosin",
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
            "is_mock": int(settings.use_mock_jira),
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
            "is_mock": int(settings.use_mock_jira),
            "polling_interval_sec": 60,
        },
        {
            "system_name": "remedy",
            "display_name": "Remedy",
            "system_type": "source",
            "connector_type": "remedy",
            "base_url": "",
            "auth_token": "",
            "auth_email": "",
            "project_key": "",
            "extra_config": "{}",
            "is_active": int("remedy" in settings.active_sources),
            "is_mock": 1,
            "polling_interval_sec": 60,
        },
        {
            "system_name": "servicenow",
            "display_name": "ServiceNow",
            "system_type": "source",
            "connector_type": "servicenow",
            "base_url": "",
            "auth_token": "",
            "auth_email": "",
            "project_key": "",
            "extra_config": "{}",
            "is_active": int("servicenow" in settings.active_sources),
            "is_mock": 1,
            "polling_interval_sec": 60,
        },
    ]
    for cfg in defaults:
        existing = await db.get_system_config(cfg["system_name"])
        if not existing:
            name = cfg.pop("system_name")
            await db.upsert_system_config(name, **cfg)
            logger.info("seeded_system_config", system=name)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup, cleanup on shutdown."""
    logger.info("starting_application", app=settings.app_name)

    # Database
    db = DatabaseService(settings.db_path)
    await db.init()
    await _seed_default_configs(db)
    app_state["db"] = db

    # PII Detector
    detector = _init_detector()
    app_state["detector"] = detector

    # Anonymizer
    anonymizer = Anonymizer(detector=detector)
    app_state["anonymizer"] = anonymizer

    # Encryption key
    encryption_key = Anonymizer.key_from_string(settings.encryption_key)
    app_state["encryption_key"] = encryption_key

    # WebSocket manager
    ws_manager = ConnectionManager()
    app_state["ws_manager"] = ws_manager

    # Connectors + Router
    router = ConnectorRouter()
    active_sources = [s.strip().lower() for s in settings.active_sources.split(",") if s.strip()]

    if settings.use_mock_jira:
        # Mock mode: register mock connectors for each active source
        if "kosin" in active_sources:
            kosin_source = MockJiraConnector()
            router.register("kosin", kosin_source, ["PESESG-", "PROJ-"])

        if "remedy" in active_sources:
            from .connectors.remedy import MockRemedyConnector
            router.register("remedy", MockRemedyConnector(), ["INC", "CHG", "PRB"])

        if "servicenow" in active_sources:
            from .connectors.servicenow import MockServiceNowConnector
            router.register("servicenow", MockServiceNowConnector(), ["SNOW-"])

        kosin_connector = MockKosinConnector()
        logger.info("connectors_mode", mode="mock", sources=active_sources)
    else:
        # Real mode: separate source (STDVERT1) and destination (GDNESPAIN) connectors
        kosin_connector = KosinConnector(
            base_url=settings.kosin_url,
            token=settings.kosin_token,
            project=settings.kosin_project,
            issue_type_id=settings.kosin_issue_type_id,
        )

        if "stdvert1" in active_sources:
            source_connector = KosinConnector(
                base_url=settings.kosin_url,
                token=settings.kosin_token,
                project=settings.source_project,
            )
            router.register("stdvert1", source_connector, [f"{settings.source_project}-"])

        if "kosin" in active_sources:
            router.register("kosin", kosin_connector, [f"{settings.kosin_project}-"])

        if "remedy" in active_sources:
            from .connectors.remedy import MockRemedyConnector
            router.register("remedy", MockRemedyConnector(), ["INC", "CHG", "PRB"])

        if "servicenow" in active_sources:
            from .connectors.servicenow import MockServiceNowConnector
            router.register("servicenow", MockServiceNowConnector(), ["SNOW-"])

        logger.info("connectors_mode", mode="real", url=settings.kosin_url,
                     source_project=settings.source_project,
                     dest_project=settings.kosin_project, sources=active_sources)

    app_state["connector_router"] = router
    app_state["kosin_connector"] = kosin_connector
    # Backward compat: jira_connector points to the first registered source
    first_source = active_sources[0] if active_sources else "kosin"
    app_state["jira_connector"] = router.get_connector_by_name(first_source) or kosin_connector

    # System prompt (stored in app_state for hot-reload)
    from .services.agent import DEFAULT_SYSTEM_PROMPT
    app_state["system_prompt"] = DEFAULT_SYSTEM_PROMPT

    # Agent (lazy init - requires LLM config)
    try:
        from .services.agent import AnonymizationAgent
        agent = AnonymizationAgent(
            anonymizer=anonymizer,
            db=db,
            ws_manager=ws_manager,
            encryption_key=encryption_key,
        )
        app_state["agent"] = agent
        logger.info("agent_initialized", provider=settings.llm_provider)
    except Exception as e:
        logger.warning("agent_init_failed", error=str(e),
                       hint="Set LLM provider env vars for agent functionality")
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
    return {
        "status": "healthy",
        "app": settings.app_name,
        "agent_ready": app_state.get("agent") is not None,
        "mock_mode": settings.use_mock_jira,
    }


@app.get("/api/status")
async def api_status():
    db = app_state.get("db")
    ticket_count = 0
    if db:
        tickets = await db.get_all_tickets()
        ticket_count = len(tickets)

    return {
        "tickets_total": ticket_count,
        "ws_connections": len(app_state.get("ws_manager", ConnectionManager())._connections),
        "mock_mode": settings.use_mock_jira,
    }
