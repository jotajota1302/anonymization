"""Pydantic models for API request/response schemas."""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class TicketStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class Priority(str, Enum):
    VERY_LOW = "very low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very high"
    CRITICAL = "critical"


# --- Ticket Schemas ---

class TicketSummary(BaseModel):
    id: int
    kosin_id: str
    source_system: str
    source_ticket_id: str
    summary: str
    status: TicketStatus = TicketStatus.OPEN
    priority: Priority = Priority.MEDIUM
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatMessageSchema(BaseModel):
    role: str  # "operator" or "agent"
    content: str
    timestamp: datetime


class TicketDetail(BaseModel):
    id: int
    kosin_id: str
    source_system: str
    source_ticket_id: str
    summary: str
    anonymized_description: str
    status: TicketStatus
    priority: Priority
    created_at: datetime
    closed_at: Optional[datetime] = None
    chat_history: List[ChatMessageSchema] = []

    model_config = {"from_attributes": True}


# --- Chat Schemas ---

class ChatRequest(BaseModel):
    ticket_id: int
    message: str


class ChatResponse(BaseModel):
    role: str = "agent"
    content: str
    timestamp: datetime


class WSMessage(BaseModel):
    """WebSocket message format."""
    type: str  # "token", "complete", "error", "info"
    data: str
    ticket_id: Optional[int] = None


# --- Substitution Map ---

class SubstitutionEntry(BaseModel):
    token: str  # e.g., "[PERSONA_1]"
    original_value: str
    entity_type: str  # e.g., "PERSONA", "EMAIL", "TELEFONO"


# --- Ticket Ingest ---

class TicketIngestRequest(BaseModel):
    source_system: str = Field(default="jira-piloto")
    source_ticket_id: str
    summary: str
    description: str
    priority: Priority = Priority.MEDIUM


class TicketStatusUpdate(BaseModel):
    status: TicketStatus


class SyncToClientRequest(BaseModel):
    comment: str = Field(..., min_length=1)


class CloseTicketRequest(BaseModel):
    """Request body for unified ticket close (destination + source + worklog)."""
    time_spent: Optional[str] = Field(None, description="Jira time format e.g. '2h 30m'. If empty, estimated by LLM.")
    summary: Optional[str] = Field(None, description="Resolution summary. If empty, uses last agent message.")


class BoardTicket(BaseModel):
    """A ticket from the KOSIN board - only safe metadata, no PII."""
    key: str
    priority: str
    status: str
    issue_type: str
    already_ingested: bool = False
    source_system: str = "kosin"


class IngestConfirmResponse(BaseModel):
    """Response after confirming ingestion of a board ticket."""
    ticket_id: int
    kosin_key: str
    source_key: str
    pii_entities_found: int
    pii_warning: Optional[str] = None


# --- Audit ---

class AuditEntry(BaseModel):
    operator_id: str
    action: str
    ticket_mapping_id: int
    details: Optional[str] = None
    created_at: datetime
