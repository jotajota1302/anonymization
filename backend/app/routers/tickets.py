"""Ticket management API endpoints."""

from typing import List
from fastapi import APIRouter, HTTPException
import structlog

from ..models.schemas import (
    TicketSummary, TicketDetail, BoardTicket, IngestConfirmResponse,
    TicketStatusUpdate, ChatMessageSchema, SyncToClientRequest,
)
from ..services.anonymizer import Anonymizer

logger = structlog.get_logger()
router = APIRouter(prefix="/api/tickets", tags=["tickets"])


def _get_state():
    from ..main import app_state
    return app_state


@router.get("", response_model=List[TicketSummary])
async def list_tickets():
    """List all ingested (anonymized) tickets for the operator."""
    state = _get_state()
    db = state["db"]
    tickets = await db.get_all_tickets()

    return [
        TicketSummary(
            id=t["id"],
            kosin_id=t["kosin_ticket_id"],
            source_system=t["source_system"],
            source_ticket_id=t["source_ticket_id"],
            summary=t["summary"],
            status=t["status"],
            priority=t["priority"],
            created_at=t["created_at"],
        )
        for t in tickets
    ]


@router.get("/board", response_model=List[BoardTicket])
async def list_board_tickets():
    """List live tickets from all active source systems (safe metadata only, no PII).

    Uses ConnectorRouter to aggregate from all registered systems.
    Filters out [ANON] tickets and the VOLCADO parent.
    Crosses with DB to flag already-ingested tickets.
    """
    state = _get_state()
    db = state["db"]
    connector_router = state.get("connector_router")

    # Get board issues from all sources via router, or fallback to KOSIN only
    if connector_router:
        issues = await connector_router.get_all_board_issues()
    else:
        kosin = state["kosin_connector"]
        issues = await kosin.get_board_issues()
        for issue in issues:
            issue["source_system"] = "kosin"

    # Get already-ingested keys from DB
    ingested_keys = await db.get_ingested_ticket_keys()

    # Get parent key to filter it out
    from ..config import settings as cfg
    parent_key = cfg.kosin_parent_key

    board_tickets = []
    for issue in issues:
        key = issue.get("key", "")
        fields = issue.get("fields", {})
        summary = fields.get("summary", "")
        source_system = issue.get("source_system", "kosin")

        # Filter out [ANON] tickets and VOLCADO parent
        if "[ANON]" in summary:
            continue
        if parent_key and key == parent_key:
            continue

        # Filter out sub-tasks, epics, and non-incident types
        issue_type_raw = fields.get("issuetype", {})
        issue_type_name = issue_type_raw.get("name", "") if isinstance(issue_type_raw, dict) else str(issue_type_raw)
        if issue_type_name.startswith("Sub-") or issue_type_name in ("Epic", "Evolutive"):
            continue

        board_tickets.append(BoardTicket(
            key=key,
            priority=fields.get("priority", {}).get("name", "Medium") if isinstance(fields.get("priority"), dict) else str(fields.get("priority", "Medium")),
            status=fields.get("status", {}).get("name", "Open") if isinstance(fields.get("status"), dict) else str(fields.get("status", "Open")),
            issue_type=fields.get("issuetype", {}).get("name", "Support") if isinstance(fields.get("issuetype"), dict) else str(fields.get("issuetype", "Support")),
            already_ingested=key in ingested_keys,
            source_system=source_system,
        ))

    return board_tickets


@router.post("/ingest-confirm/{kosin_key}", response_model=IngestConfirmResponse)
async def ingest_confirm(kosin_key: str):
    """Operator confirms they want to attend this ticket.

    1. Reads full ticket from KOSIN (with PII)
    2. Reads comments from KOSIN
    3. Anonymizes everything together
    4. Creates VOLCADO sub-task in KOSIN with anonymized data
    5. Saves mapping + encrypted substitution map in DB
    6. Returns local ticket_id for chat
    """
    state = _get_state()
    db = state["db"]
    anonymizer = state["anonymizer"]
    kosin = state["kosin_connector"]
    encryption_key = state["encryption_key"]

    # Resolve source connector via router
    connector_router = state.get("connector_router")
    source_system_name = "kosin"
    if connector_router:
        try:
            source_system_name, source_connector = connector_router.get_connector(kosin_key)
        except ValueError:
            source_connector = state["jira_connector"]
    else:
        source_connector = state["jira_connector"]

    # Check if already ingested in DB
    existing = await db.get_ticket_by_source_key(kosin_key)
    if existing:
        return IngestConfirmResponse(
            ticket_id=existing["id"],
            kosin_key=existing["kosin_ticket_id"],
            source_key=kosin_key,
            pii_entities_found=0,
        )

    # Check if [ANON] ticket already exists in KOSIN (DB was cleaned but KOSIN wasn't)
    existing_kosin = await kosin.find_anon_ticket(kosin_key)
    if existing_kosin:
        logger.warning(
            "kosin_anon_exists_no_db",
            source_key=kosin_key,
            existing_kosin=existing_kosin,
        )
        raise HTTPException(
            status_code=409,
            detail=f"Ya existe un ticket anonimizado en KOSIN ({existing_kosin}) para {kosin_key}. "
                   f"Elimínalo desde Configuración antes de re-ingestar.",
        )

    # 1. Read full ticket from source system
    try:
        source_ticket = await source_connector.get_ticket(kosin_key)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"No se pudo leer {kosin_key}: {str(e)}")

    summary = source_ticket.get("summary", "")
    description = source_ticket.get("description", "") or ""
    priority = source_ticket.get("priority", "Medium")

    # 2. Read comments
    try:
        comments = await source_connector.get_comments(kosin_key)
    except Exception:
        comments = []

    # 3. Anonymize everything together
    comments_text = ""
    if comments:
        comments_text = "\n\n--- COMENTARIOS ---\n" + "\n---\n".join(
            f"{c.get('author', 'Unknown')}: {c.get('body', '')}" for c in comments
        )

    full_text = f"{summary}\n{description}{comments_text}"
    anonymized_text, sub_map = anonymizer.anonymize(full_text)

    # Split back
    parts = anonymized_text.split("\n", 1)
    anon_summary = parts[0]
    anon_rest = parts[1] if len(parts) > 1 else ""

    # Separate description from comments in anonymized text
    if "--- COMENTARIOS ---" in anon_rest:
        anon_desc, anon_comments_section = anon_rest.split("--- COMENTARIOS ---", 1)
        anon_description = anon_desc.strip()
    else:
        anon_description = anon_rest.strip()
        anon_comments_section = ""

    # 4. Create VOLCADO sub-task in KOSIN
    from ..config import settings as cfg
    parent_key = cfg.kosin_parent_key

    volcado_description = f"--- Copia anonimizada de {kosin_key} ---\n\n{anon_description}"
    if anon_comments_section:
        volcado_description += f"\n\n--- COMENTARIOS ANONIMIZADOS ---{anon_comments_section}"

    # Jira limits summary to 255 characters
    full_summary = f"[ANON] {anon_summary}"
    if len(full_summary) > 255:
        full_summary = full_summary[:252] + "..."

    kosin_id, create_error = await kosin.create_ticket(
        summary=full_summary,
        description=volcado_description,
        priority=priority,
        parent_key=parent_key if parent_key else None,
    )

    if not kosin_id:
        raise HTTPException(status_code=500, detail=f"Error creando ticket anonimizado en KOSIN: {create_error}")

    # 5. Save to local DB (with rollback if it fails)
    try:
        ticket_id = await db.create_ticket_mapping(
            source_system=source_system_name,
            source_ticket_id=kosin_key,
            kosin_ticket_id=kosin_id,
            summary=anon_summary,
            anonymized_description=anon_description,
            priority=priority.lower() if isinstance(priority, str) else "medium",
        )

        if sub_map:
            encrypted = anonymizer.encrypt_map(sub_map, encryption_key)
            await db.save_substitution_map(ticket_id, encrypted)
    except Exception as e:
        # Rollback: delete the KOSIN ticket we just created
        logger.error("db_save_failed_rolling_back", kosin_id=kosin_id, error=str(e))
        await kosin.delete_ticket(kosin_id)
        raise HTTPException(
            status_code=500,
            detail=f"Error guardando en DB (ticket KOSIN {kosin_id} eliminado como rollback): {str(e)}",
        )

    # 6. Audit log
    await db.add_audit_log(
        operator_id="operator",
        action="ingest_confirmed",
        ticket_mapping_id=ticket_id,
        details=f"source={kosin_key}, anon_copy={kosin_id}, pii_entities={len(sub_map)}",
    )

    logger.info(
        "ticket_ingest_confirmed",
        source=kosin_key,
        anon_copy=kosin_id,
        pii_entities=len(sub_map),
        tokens=list(sub_map.keys()),
    )

    pii_warning = None
    if not sub_map:
        pii_warning = "No se detecto informacion sensible (PII) en este ticket. Se ha ingestado tal cual."

    return IngestConfirmResponse(
        ticket_id=ticket_id,
        kosin_key=kosin_id,
        source_key=kosin_key,
        pii_entities_found=len(sub_map),
        pii_warning=pii_warning,
    )


@router.get("/{ticket_id}", response_model=TicketDetail)
async def get_ticket(ticket_id: int):
    """Get ticket detail with anonymized description and chat history."""
    state = _get_state()
    db = state["db"]

    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    chat_history = await db.get_chat_history(ticket_id)

    await db.add_audit_log(
        operator_id="operator",
        action="view_ticket",
        ticket_mapping_id=ticket_id,
    )

    return TicketDetail(
        id=ticket["id"],
        kosin_id=ticket["kosin_ticket_id"],
        source_system=ticket["source_system"],
        source_ticket_id=ticket["source_ticket_id"],
        summary=ticket["summary"],
        anonymized_description=ticket["anonymized_description"],
        status=ticket["status"],
        priority=ticket["priority"],
        created_at=ticket["created_at"],
        closed_at=ticket.get("closed_at"),
        chat_history=[
            ChatMessageSchema(
                role=msg["role"],
                content=msg["message"],
                timestamp=msg["created_at"],
            )
            for msg in chat_history
        ],
    )


@router.put("/{ticket_id}/status")
async def update_ticket_status(ticket_id: int, update: TicketStatusUpdate):
    """Update ticket status (e.g., resolve, close)."""
    state = _get_state()
    db = state["db"]

    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    await db.update_ticket_status(ticket_id, update.status.value)

    # If closing, optionally delete substitution map
    if update.status.value == "closed":
        await db.delete_substitution_map(ticket_id)
        logger.info("substitution_map_destroyed", ticket_id=ticket_id)

    await db.add_audit_log(
        operator_id="operator",
        action="update_status",
        ticket_mapping_id=ticket_id,
        details=f"new_status={update.status.value}",
    )

    return {"message": f"Ticket {ticket_id} status updated to {update.status.value}"}


@router.post("/{ticket_id}/sync-to-client")
async def sync_to_client(ticket_id: int, body: SyncToClientRequest):
    """De-anonymize a comment and publish it to the source ticket."""
    state = _get_state()
    db = state["db"]
    encryption_key = state["encryption_key"]

    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if ticket["status"] == "closed":
        raise HTTPException(
            status_code=409,
            detail="El ticket está cerrado y el mapa de sustitución fue destruido",
        )

    # Load and decrypt substitution map
    encrypted = await db.get_substitution_map(ticket_id)
    if not encrypted:
        raise HTTPException(status_code=404, detail="No substitution map found")

    sub_map = Anonymizer.decrypt_map(encrypted, encryption_key)

    # De-anonymize the comment
    real_comment = Anonymizer.de_anonymize(body.comment, sub_map)

    # Resolve source connector via router
    source_ticket_id = ticket["source_ticket_id"]
    connector_router = state.get("connector_router")
    if connector_router:
        try:
            _, source_connector = connector_router.get_connector(source_ticket_id)
        except ValueError:
            source_connector = state["jira_connector"]
    else:
        source_connector = state["jira_connector"]

    # Publish to source ticket
    success = await source_connector.add_comment(source_ticket_id, real_comment)

    if not success:
        raise HTTPException(status_code=502, detail="Error publicando comentario en origen")

    await db.add_audit_log(
        operator_id="operator",
        action="sync_to_client",
        ticket_mapping_id=ticket_id,
        details=f"source={source_ticket_id}, comment_length={len(real_comment)}",
    )

    logger.info("sync_to_client", ticket_id=ticket_id, source=source_ticket_id)
    return {"message": f"Comentario sincronizado con {source_ticket_id}", "success": True}


@router.post("/{ticket_id}/kosin-comment")
async def add_kosin_comment(ticket_id: int, body: dict):
    """Register an action as a comment in the KOSIN destination (VOLCADO) ticket."""
    state = _get_state()
    db = state["db"]
    kosin = state["kosin_connector"]

    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    action_text = body.get("action", "")
    if not action_text:
        raise HTTPException(status_code=400, detail="action is required")

    kosin_key = ticket["kosin_ticket_id"]
    comment = f"[ACCION OPERADOR] {action_text}"

    success = await kosin.add_comment(kosin_key, comment)

    await db.add_audit_log(
        operator_id="operator",
        action="kosin_comment",
        ticket_mapping_id=ticket_id,
        details=f"kosin={kosin_key}, action={action_text}, success={success}",
    )

    logger.info("kosin_comment_added", ticket_id=ticket_id, kosin=kosin_key, action=action_text)

    return {"message": f"Comentario registrado en {kosin_key}", "success": success}


@router.get("/{ticket_id}/attachment/{attachment_index}/redacted")
async def get_redacted_attachment(ticket_id: int, attachment_index: int = 0):
    """Download an image attachment with PII redacted using Presidio Image Redactor.

    Returns the image with PII regions blacked out as a PNG.
    Only works for image attachments (jpg, png, bmp, tiff).
    """
    from fastapi.responses import Response
    from ..services.attachment_processor import AttachmentProcessor

    state = _get_state()
    db = state["db"]

    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    source_ticket_id = ticket["source_ticket_id"]

    # Resolve source connector
    connector_router = state.get("connector_router")
    if connector_router:
        try:
            _, connector = connector_router.get_connector(source_ticket_id)
        except ValueError:
            connector = state["jira_connector"]
    else:
        connector = state["jira_connector"]

    try:
        source_ticket = await connector.get_ticket(source_ticket_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"No se pudo leer ticket origen: {e}")

    attachments = source_ticket.get("attachments", [])
    if not attachments:
        raise HTTPException(status_code=404, detail="El ticket no tiene adjuntos")
    if attachment_index < 0 or attachment_index >= len(attachments):
        raise HTTPException(status_code=400, detail=f"Indice fuera de rango (0-{len(attachments)-1})")

    attachment = attachments[attachment_index]
    filename = attachment.get("filename", "unknown")
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in ("jpg", "jpeg", "png", "bmp", "tiff", "tif"):
        raise HTTPException(status_code=400, detail=f"Solo se pueden redactar imagenes, no '{ext}'")

    content_url = attachment.get("content", "")
    if not content_url:
        raise HTTPException(status_code=404, detail="El adjunto no tiene URL de contenido")

    content_bytes = await connector.download_attachment(content_url)
    if not content_bytes:
        raise HTTPException(status_code=502, detail="No se pudo descargar el adjunto")

    processor = AttachmentProcessor()
    redacted_bytes = processor.redact_image(content_bytes)

    if redacted_bytes is None:
        raise HTTPException(
            status_code=501,
            detail="Presidio Image Redactor no disponible. Instalar: pip install presidio-image-redactor"
        )

    await db.add_audit_log(
        operator_id="operator",
        action="view_redacted_attachment",
        ticket_mapping_id=ticket_id,
        details=f"attachment={filename}, index={attachment_index}",
    )

    return Response(
        content=redacted_bytes,
        media_type="image/png",
        headers={"Content-Disposition": f'inline; filename="redacted_{filename}.png"'},
    )
