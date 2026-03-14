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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup, cleanup on shutdown."""
    logger.info("starting_application", app=settings.app_name)

    # Database
    db = DatabaseService(settings.db_path)
    await db.init()
    app_state["db"] = db

    # Anonymizer
    anonymizer = Anonymizer()
    app_state["anonymizer"] = anonymizer

    # Encryption key
    encryption_key = Anonymizer.key_from_string(settings.encryption_key)
    app_state["encryption_key"] = encryption_key

    # WebSocket manager
    ws_manager = ConnectionManager()
    app_state["ws_manager"] = ws_manager

    # Connectors
    # POC: same JIRA instance as source AND destination
    if settings.use_mock_jira:
        jira_connector = MockJiraConnector()
        kosin_connector = MockKosinConnector()
        logger.info("connectors_mode", mode="mock")
    else:
        # Both connectors point to the same KOSIN Jira instance
        # Source: reads existing tickets from PESESG
        # Destination: creates anonymized copies in PESESG
        kosin_connector = KosinConnector(
            base_url=settings.kosin_url,
            token=settings.kosin_token,
            project=settings.kosin_project,
            issue_type_id=settings.kosin_issue_type_id,
        )
        # For POC, jira_connector IS the same kosin instance (read source tickets)
        jira_connector = kosin_connector
        logger.info("connectors_mode", mode="real_kosin", url=settings.kosin_url, project=settings.kosin_project)

    app_state["jira_connector"] = jira_connector
    app_state["kosin_connector"] = kosin_connector

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
