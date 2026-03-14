"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup, cleanup on shutdown."""
    logger.info("starting_application", app=settings.app_name)

    # Database
    db = DatabaseService(settings.db_path)
    await db.init()
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
        # Real mode: KOSIN as source + destination
        kosin_connector = KosinConnector(
            base_url=settings.kosin_url,
            token=settings.kosin_token,
            project=settings.kosin_project,
            issue_type_id=settings.kosin_issue_type_id,
        )
        if "kosin" in active_sources:
            router.register("kosin", kosin_connector, ["PESESG-", "PROJ-"])

        if "remedy" in active_sources:
            from .connectors.remedy import MockRemedyConnector
            router.register("remedy", MockRemedyConnector(), ["INC", "CHG", "PRB"])

        if "servicenow" in active_sources:
            from .connectors.servicenow import MockServiceNowConnector
            router.register("servicenow", MockServiceNowConnector(), ["SNOW-"])

        logger.info("connectors_mode", mode="real_kosin", url=settings.kosin_url,
                     project=settings.kosin_project, sources=active_sources)

    app_state["connector_router"] = router
    app_state["kosin_connector"] = kosin_connector
    # Backward compat: jira_connector points to the first registered source
    first_source = active_sources[0] if active_sources else "kosin"
    app_state["jira_connector"] = router.get_connector_by_name(first_source) or kosin_connector

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

    logger.info("application_started")
    yield

    # Cleanup
    logger.info("shutting_down")
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
from .routers import tickets, chat  # noqa: E402

app.include_router(tickets.router)
app.include_router(chat.router)


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
