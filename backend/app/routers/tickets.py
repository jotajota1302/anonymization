"""Ticket management API endpoints."""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
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
async def list_board_tickets(
    max_results: int = Query(50, ge=1, le=200),
    date_from: Optional[str] = Query(None, description="Created since (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Created until (YYYY-MM-DD)"),
    priority: Optional[str] = Query(None, description="Comma-separated priorities"),
    status: Optional[str] = Query(None, description="Comma-separated statuses"),
    issue_type: Optional[str] = Query(None, description="Comma-separated issue types"),
):
    """List live tickets from all active source systems (safe metadata only, no PII).

    Uses ConnectorRouter to aggregate from all registered systems.
    Filters out [ANON] tickets and the VOLCADO parent.
    Crosses with DB to flag already-ingested tickets.
    """
    from ..connectors.base import BoardFilters

    filters = BoardFilters(
        max_results=max_results,
        date_from=date_from,
        date_to=date_to,
        priority=[p.strip() for p in priority.split(",")] if priority else None,
        status=[s.strip() for s in status.split(",")] if status else None,
        issue_type=[t.strip() for t in issue_type.split(",")] if issue_type else None,
    )

    state = _get_state()
    db = state["db"]
    connector_router = state.get("connector_router")

    # Get board issues from all sources via router
    if connector_router:
        issues = await connector_router.get_all_board_issues(filters=filters)
    else:
        dest = state.get("destination_connector")
        if dest:
            issues = await dest.get_board_issues(filters=filters)
            for issue in issues:
                issue["source_system"] = "destination"
        else:
            issues = []

    # Get already-ingested keys from DB
    ingested_keys = await db.get_ingested_ticket_keys()

    # Get parent key to filter it out
    from ..config import settings as cfg
    parent_key = cfg.kosin_parent_key

    # Known prefixes from connector router — only show tickets from registered projects
    known_prefixes = tuple(connector_router._prefixes.keys()) if connector_router and connector_router._prefixes else ()
    logger.info("board_filter", known_prefixes=known_prefixes, total_issues=len(issues))

    board_tickets = []
    for issue in issues:
        key = issue.get("key", "")
        fields = issue.get("fields", {})
        summary = fields.get("summary", "")
        source_system = issue.get("source_system", "unknown")

        # Filter out tickets from unknown projects (e.g. GDNESPAIN-74)
        if known_prefixes and not key.startswith(known_prefixes):
            continue

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
async def ingest_confirm(kosin_key: str, client_id: Optional[str] = Query(None)):
    """Operator confirms they want to attend this ticket.

    1. Reads full ticket + comments from source (with PII)
    2. Detects PII with breakdown (regex, presidio, composite)
    3. Anonymizes and creates VOLCADO sub-task in destination
    4. Saves mapping in DB
    5. Returns local ticket_id for chat

    Sends real-time progress via WebSocket if client_id is provided.
    """
    state = _get_state()
    db = state["db"]
    anonymizer = state["anonymizer"]
    destination = state.get("destination_connector")
    ws_manager = state.get("ws_manager")

    TOTAL_STEPS = 4  # reading_source, detecting_pii, creating_destination, completed

    async def _progress(step: str, step_index: int, status: str = "in_progress",
                        detail: str = None, detectors: dict = None):
        if not (client_id and ws_manager and ws_manager.is_connected(client_id)):
            return
        payload = {
            "step": step, "step_index": step_index,
            "total_steps": TOTAL_STEPS, "status": status,
            "source_key": kosin_key,
        }
        if detail is not None:
            payload["detail"] = detail
        if detectors is not None:
            payload["detectors"] = detectors
        await ws_manager.send_message(client_id, {"type": "ingest_progress", "data": payload})

    # Resolve source connector via router
    connector_router = state.get("connector_router")
    source_system_name = "unknown"
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

    # Check if [ANON] ticket already exists in destination (DB was cleaned but destination wasn't)
    if destination:
        existing_anon = await destination.find_anon_ticket(kosin_key)
        if existing_anon:
            logger.warning(
                "anon_exists_no_db",
                source_key=kosin_key,
                existing_anon=existing_anon,
            )
            await _progress("reading_source", 0, status="error",
                            detail=f"Ya existe ticket anonimizado ({existing_anon})")
            raise HTTPException(
                status_code=409,
                detail=f"Ya existe un ticket anonimizado ({existing_anon}) para {kosin_key}. "
                       f"Eliminalo desde Configuracion antes de re-ingestar.",
            )

    # --- Step 0: Reading source ---
    await _progress("reading_source", 0)

    try:
        source_ticket = await source_connector.get_ticket(kosin_key)
    except Exception as e:
        await _progress("reading_source", 0, status="error", detail=str(e))
        raise HTTPException(status_code=404, detail=f"No se pudo leer {kosin_key}: {str(e)}")

    summary = source_ticket.get("summary", "")
    description = source_ticket.get("description", "") or ""
    priority = source_ticket.get("priority", "Medium")

    try:
        comments = await source_connector.get_comments(kosin_key)
    except Exception:
        comments = []

    await _progress("reading_source", 0, status="completed")

    # --- Step 1: Detecting PII (with per-detector breakdown) ---
    full_text = anonymizer.assemble_ingest_text(summary, description, comments)
    source_text_hash = anonymizer.compute_text_hash(full_text)

    # Build detector list dynamically based on what's configured
    breakdown = anonymizer.detect_breakdown(full_text)
    has_regex = breakdown.get("regex") is not None
    has_presidio = breakdown.get("presidio") is not None

    det_state: dict = {}
    if has_regex:
        det_state["regex"] = {"status": "pending", "count": None}
    if has_presidio:
        det_state["presidio"] = {"status": "pending", "count": None}
    # LLM agent detector — only if LLM is configured
    agent = state.get("agent")
    has_llm = agent is not None and hasattr(agent, "llm")
    if has_llm:
        det_state["agente"] = {"status": "pending", "count": None}
    det_state["anonymize"] = {"status": "pending", "count": None}

    await _progress("detecting_pii", 1, detectors=det_state)

    # Report each active detector result
    if has_regex:
        det_state["regex"] = {"status": "completed", "count": breakdown["regex"]}
        await _progress("detecting_pii", 1, detectors=det_state)

    if has_presidio:
        det_state["presidio"] = {"status": "completed", "count": breakdown["presidio"]}
        await _progress("detecting_pii", 1, detectors=det_state)

    # LLM agent pass — review what regex/presidio found and catch missed PII
    llm_entities = []
    if has_llm:
        det_state["agente"] = {"status": "in_progress", "count": None}
        await _progress("detecting_pii", 1, detectors=det_state)
        try:
            from ..services.llm_detector import llm_detect_pii
            already = anonymizer.detect_pii(full_text)
            # Tell LLM if regex/presidio are active so it knows whether to do full detection
            detectors_active = has_regex or has_presidio
            llm_entities = await llm_detect_pii(full_text, already, agent.llm, detectors_active=detectors_active)
            det_state["agente"] = {"status": "completed", "count": len(llm_entities)}
        except Exception as e:
            logger.warning("llm_detector_failed", error=str(e))
            det_state["agente"] = {"status": "completed", "count": 0}
        await _progress("detecting_pii", 1, detectors=det_state)

    # Run actual anonymization (merging LLM extra entities)
    anonymized_text, sub_map = anonymizer.anonymize(full_text, extra_entities=llm_entities or None)
    det_state["anonymize"] = {"status": "completed", "count": len(sub_map)}
    await _progress("detecting_pii", 1, status="completed", detectors=det_state)

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

    # --- Step 2: Creating anonymized copy in destination ---
    await _progress("creating_destination", 2)

    from ..config import settings as cfg
    parent_key = cfg.kosin_parent_key

    volcado_description = f"--- Copia anonimizada de {kosin_key} ---\n\n{anon_description}"
    if anon_comments_section:
        volcado_description += f"\n\n--- COMENTARIOS ANONIMIZADOS ---{anon_comments_section}"

    # Jira limits summary to 255 characters
    full_summary = f"[ANON] {anon_summary}"
    if len(full_summary) > 255:
        full_summary = full_summary[:252] + "..."

    if not destination:
        await _progress("creating_destination", 2, status="error",
                        detail="No hay conector destino configurado")
        raise HTTPException(status_code=503, detail="No hay conector destino configurado. Configura uno en Integraciones.")

    kosin_id, create_error = await destination.create_ticket(
        summary=full_summary,
        description=volcado_description,
        priority=priority,
        parent_key=parent_key if parent_key else None,
    )

    if not kosin_id:
        await _progress("creating_destination", 2, status="error", detail=create_error)
        raise HTTPException(status_code=500, detail=f"Error creando ticket anonimizado en destino: {create_error}")

    # Save to local DB (with rollback if it fails)
    try:
        ticket_id = await db.create_ticket_mapping(
            source_system=source_system_name,
            source_ticket_id=kosin_key,
            kosin_ticket_id=kosin_id,
            summary=anon_summary,
            anonymized_description=anon_description,
            priority=priority.lower() if isinstance(priority, str) else "medium",
            source_text_hash=source_text_hash,
        )
    except Exception as e:
        logger.error("db_save_failed_rolling_back", dest_id=kosin_id, error=str(e))
        await destination.delete_ticket(kosin_id)
        await _progress("creating_destination", 2, status="error", detail=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Error guardando en DB (ticket {kosin_id} eliminado como rollback): {str(e)}",
        )

    await _progress("creating_destination", 2, status="completed",
                    detail=kosin_id)

    # --- Step 3: Completed ---
    pii_total = len(sub_map)
    completed_detail = (
        f"{kosin_id} — {pii_total} entidades PII anonimizadas"
        if pii_total else f"{kosin_id} — Sin PII detectado"
    )
    await _progress("completed", 3, status="completed",
                    detail=completed_detail, detectors=det_state)

    # Audit log
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

    # If closing, invalidate any cached map in the agent
    if update.status.value == "closed":
        agent = state.get("agent")
        if agent:
            agent.invalidate_map_cache(ticket_id)
        logger.info("ticket_closed_cache_invalidated", ticket_id=ticket_id)

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
    anonymizer = state["anonymizer"]

    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if ticket["status"] == "closed":
        raise HTTPException(
            status_code=409,
            detail="El ticket esta cerrado",
        )

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

    # Reconstruct substitution map on-the-fly from source
    try:
        source_ticket = await source_connector.get_ticket(source_ticket_id)
        comments = await source_connector.get_comments(source_ticket_id)
        full_text = Anonymizer.assemble_ingest_text(
            source_ticket.get("summary", ""),
            source_ticket.get("description", "") or "",
            comments,
        )
        sub_map = anonymizer.reconstruct_map(full_text)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"No se pudo reconstruir el mapa desde el origen: {str(e)}",
        )

    # De-anonymize the comment
    real_comment = Anonymizer.de_anonymize(body.comment, sub_map)

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


@router.post("/{ticket_id}/destination-comment")
async def add_destination_comment(ticket_id: int, body: dict):
    """Register an action as a comment in the destination (VOLCADO) ticket."""
    state = _get_state()
    db = state["db"]
    destination = state.get("destination_connector")

    if not destination:
        raise HTTPException(status_code=503, detail="No hay conector destino configurado")

    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    action_text = body.get("action", "")
    if not action_text:
        raise HTTPException(status_code=400, detail="action is required")

    dest_key = ticket["kosin_ticket_id"]
    comment = f"[ACCION OPERADOR] {action_text}"

    success = await destination.add_comment(dest_key, comment)

    await db.add_audit_log(
        operator_id="operator",
        action="destination_comment",
        ticket_mapping_id=ticket_id,
        details=f"dest={dest_key}, action={action_text}, success={success}",
    )

    logger.info("destination_comment_added", ticket_id=ticket_id, dest=dest_key, action=action_text)

    return {"message": f"Comentario registrado en {dest_key}", "success": success}


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
