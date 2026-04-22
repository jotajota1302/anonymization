"""Ticket management API endpoints."""

import json
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
import structlog

from ..models.schemas import (
    TicketSummary, TicketDetail, BoardTicket, IngestConfirmResponse,
    TicketStatusUpdate, ChatMessageSchema, SyncToClientRequest,
    CloseTicketRequest,
)
from ..services.anonymizer import Anonymizer
from ..services.time_estimator import normalize_jira_time, estimate_time_with_llm
from ..connectors.base import TicketConnector

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

    # Guard: agent must be configured with a FUNCTIONAL LLM to attend tickets.
    # LangChain creates LLM objects even with empty/expired credentials,
    # so we check actual readiness (valid API key, active OKTA token, etc.)
    agent = state.get("agent")
    if not agent or not getattr(agent, "llm", None):
        raise HTTPException(
            status_code=503,
            detail="El agente no tiene un modelo LLM configurado. "
                   "Ve a Configuracion → Agente y selecciona un modelo antes de atender tickets.",
        )
    llm_ready, llm_error = agent.check_llm_ready()
    if not llm_ready:
        raise HTTPException(status_code=503, detail=llm_error)

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

    # Check if already ingested in DB.
    # A mapping in status='closed' means the previous attention cycle finished;
    # if the source was reopened we let a fresh mapping be created while keeping
    # the historical one (and its chat/audit) intact.
    existing = await db.get_ticket_by_source_key(kosin_key)
    if existing and existing.get("status") != "closed":
        return IngestConfirmResponse(
            ticket_id=existing["id"],
            kosin_key=existing["kosin_ticket_id"],
            source_key=kosin_key,
            pii_entities_found=0,
        )
    if existing and existing.get("status") == "closed":
        logger.info(
            "reingest_after_close",
            source_key=kosin_key,
            previous_mapping_id=existing["id"],
            previous_dest=existing["kosin_ticket_id"],
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
            # ner_active = True ONLY when Presidio NER is part of the detector.
            # Regex alone doesn't count because it can't detect names/orgs/locations.
            # When ner_active=False, the LLM uses the full detection prompt
            # (all PII types) instead of just names.
            ner_active = has_presidio
            llm_entities = await llm_detect_pii(full_text, already, agent.llm, ner_active=ner_active)
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

    # --- Step 2.5: Redact image attachments and upload to destination ---
    redacted_count = 0
    source_attachments = source_ticket.get("attachments", []) or []
    image_attachments = [
        a for a in source_attachments
        if (a.get("filename", "").rsplit(".", 1)[-1].lower() in ("jpg", "jpeg", "png", "bmp", "tiff", "tif"))
    ]
    if image_attachments:
        anon_cfg_row = await db.get_system_config("anonymization")
        anon_cfg = {}
        if anon_cfg_row and anon_cfg_row.get("extra_config"):
            try:
                anon_cfg = json.loads(anon_cfg_row["extra_config"]) if isinstance(anon_cfg_row["extra_config"], str) else anon_cfg_row["extra_config"]
            except Exception:
                anon_cfg = {}
        auto_redact = anon_cfg.get("auto_redact_attachments_on_ingest", True)
        if auto_redact:
            import asyncio as _asyncio
            from ..services.attachment_processor import AttachmentProcessor
            from ..services import redacted_cache
            processor = AttachmentProcessor()

            # Fail early if the destination connector can't accept attachments
            # so we log a clear reason instead of a silent NotImplementedError.
            if not hasattr(destination, "upload_attachment") or type(destination).upload_attachment is TicketConnector.upload_attachment:
                logger.warning(
                    "redact_skipped_upload_unsupported",
                    connector=type(destination).__name__,
                    reason="destination does not implement upload_attachment — configure KosinConnector-based destination",
                )
            else:
                for attach in image_attachments:
                    filename = attach.get("filename", "unknown.png")
                    url = attach.get("content", "")
                    if not url:
                        continue
                    try:
                        raw = await source_connector.download_attachment(url)
                        if not raw:
                            continue
                        # redact_image runs OCR + Presidio locally and can
                        # take several seconds on big images; run off the
                        # event loop so concurrent WS/chat are not blocked.
                        redacted = await _asyncio.to_thread(processor.redact_image, raw)
                        if redacted is None:
                            logger.warning(
                                "redact_skipped_presidio_unavailable",
                                filename=filename,
                                hint="Install presidio-image-redactor + tesseract-ocr-spa",
                            )
                            # continue instead of break: try the remaining
                            # attachments (maybe Presidio recovers, maybe
                            # the next attachment is not an image).
                            continue
                        redacted_cache.put(kosin_key, filename, redacted)
                        out_name = filename.rsplit(".", 1)[0] + "_redacted.png"
                        ok, err = await destination.upload_attachment(kosin_id, out_name, redacted, "image/png")
                        if ok:
                            redacted_count += 1
                        else:
                            logger.warning("redacted_upload_failed", filename=filename, error=err)
                    except Exception as e:
                        logger.warning("redact_attachment_failed", filename=filename, error=str(e))

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


@router.post("/{ticket_id}/finalize-destination")
async def finalize_destination(ticket_id: int, client_id: Optional[str] = Query(None)):
    """Close the destination (anonymized) ticket in KOSIN by walking Jira transitions."""
    state = _get_state()
    db = state["db"]
    destination = state.get("destination_connector")
    ws_manager = state.get("ws_manager")

    if not destination:
        raise HTTPException(status_code=503, detail="No hay conector destino configurado")

    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if ticket["status"] in ("resolved", "closed"):
        raise HTTPException(status_code=409, detail="El ticket ya esta finalizado o cerrado")

    dest_key = ticket["kosin_ticket_id"]

    async def _progress(step: str, detail: str = ""):
        if not (client_id and ws_manager and ws_manager.is_connected(client_id)):
            return
        await ws_manager.send_message(client_id, {
            "type": "finalize_progress",
            "data": {"step": step, "detail": detail, "ticket_id": ticket_id},
        })

    await _progress("starting", f"Finalizando destino {dest_key}")

    # Try walk_transitions_to first
    success = False
    steps_taken = []
    try:
        success, steps_taken = await destination.walk_transitions_to(dest_key, "done")
        await _progress("transitions", f"Transiciones aplicadas: {', '.join(steps_taken) if steps_taken else 'ninguna'}")
    except Exception as e:
        logger.warning("finalize_walk_failed", dest_key=dest_key, error=str(e))

    # Fallback to update_status if walk didn't succeed
    if not success:
        try:
            success = await destination.update_status(dest_key, "done")
            if success:
                steps_taken.append("fallback:update_status")
        except Exception as e:
            logger.warning("finalize_fallback_failed", dest_key=dest_key, error=str(e))

    if not success:
        await _progress("error", "No se pudo transicionar el ticket destino a Done")
        raise HTTPException(
            status_code=502,
            detail=f"No se pudo cerrar el ticket destino {dest_key}. "
                   f"Transiciones intentadas: {steps_taken or 'ninguna'}. "
                   f"Verifica el workflow en KOSIN.",
        )

    # Update local DB
    await db.update_ticket_status(ticket_id, "resolved")

    await db.add_audit_log(
        operator_id="operator",
        action="finalize_destination",
        ticket_mapping_id=ticket_id,
        details=f"dest={dest_key}, transitions={steps_taken}",
    )

    await _progress("completed", f"Destino {dest_key} finalizado")
    logger.info("finalize_destination_ok", ticket_id=ticket_id, dest_key=dest_key, steps=steps_taken)

    return {
        "success": True,
        "message": f"Ticket destino {dest_key} finalizado correctamente",
        "dest_key": dest_key,
        "transition_steps": steps_taken,
    }


@router.post("/{ticket_id}/sync-and-close-source")
async def sync_and_close_source(ticket_id: int, client_id: Optional[str] = Query(None)):
    """Publish resolution to source ticket and close it."""
    state = _get_state()
    db = state["db"]
    anonymizer = state["anonymizer"]
    ws_manager = state.get("ws_manager")

    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if ticket["status"] != "resolved":
        raise HTTPException(
            status_code=409,
            detail="El ticket destino debe estar finalizado (resolved) antes de sincronizar con origen",
        )

    source_ticket_id = ticket["source_ticket_id"]

    async def _progress(step: str, detail: str = ""):
        if not (client_id and ws_manager and ws_manager.is_connected(client_id)):
            return
        await ws_manager.send_message(client_id, {
            "type": "sync_progress",
            "data": {"step": step, "detail": detail, "ticket_id": ticket_id},
        })

    await _progress("starting", f"Sincronizando con origen {source_ticket_id}")

    # Resolve source connector
    connector_router = state.get("connector_router")
    if connector_router:
        try:
            _, source_connector = connector_router.get_connector(source_ticket_id)
        except ValueError:
            source_connector = state["jira_connector"]
    else:
        source_connector = state["jira_connector"]

    # Get last agent message as resolution summary
    chat_history = await db.get_chat_history(ticket_id)
    agent_msgs = [m for m in chat_history if m["role"] == "agent"]
    if not agent_msgs:
        raise HTTPException(status_code=400, detail="No hay mensajes del agente para usar como resolucion")

    import re
    resolution = agent_msgs[-1]["message"]
    resolution = re.sub(r"\[CHIPS[:\s].*?\]", "", resolution, flags=re.DOTALL).strip()

    await _progress("deanonymizing", "De-anonimizando resolucion")

    # Reconstruct substitution map from source
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

    # De-anonymize
    real_comment = Anonymizer.de_anonymize(resolution, sub_map)
    comment_text = f"[RESOLUCION] {real_comment}"

    # Publish to source
    await _progress("publishing", f"Publicando resolucion en {source_ticket_id}")
    pub_success = await source_connector.add_comment(source_ticket_id, comment_text)
    if not pub_success:
        raise HTTPException(status_code=502, detail="Error publicando comentario de resolucion en origen")

    # Try to close source ticket (warning only if fails)
    await _progress("closing_source", f"Cerrando ticket origen {source_ticket_id}")
    source_closed = False
    source_steps = []
    try:
        source_closed, source_steps = await source_connector.walk_transitions_to(source_ticket_id, "done")
    except Exception as e:
        logger.warning("sync_source_walk_failed", source=source_ticket_id, error=str(e))

    if not source_closed:
        try:
            source_closed = await source_connector.update_status(source_ticket_id, "done")
            if source_closed:
                source_steps.append("fallback:update_status")
        except Exception as e:
            logger.warning("sync_source_fallback_failed", source=source_ticket_id, error=str(e))

    # Update local DB to closed
    await db.update_ticket_status(ticket_id, "closed")

    # Invalidate agent cache
    agent = state.get("agent")
    if agent:
        agent.invalidate_map_cache(ticket_id)

    await db.add_audit_log(
        operator_id="operator",
        action="sync_and_close_source",
        ticket_mapping_id=ticket_id,
        details=f"source={source_ticket_id}, source_closed={source_closed}, steps={source_steps}",
    )

    await _progress("completed", f"Origen {source_ticket_id} sincronizado y {'cerrado' if source_closed else 'comentario publicado (transicion manual requerida)'}")
    logger.info("sync_and_close_source_ok", ticket_id=ticket_id, source=source_ticket_id, source_closed=source_closed)

    warning = None if source_closed else (
        f"La resolucion se publico en {source_ticket_id} pero no se pudo transicionar a Done automaticamente. "
        f"Cierra el ticket origen manualmente."
    )

    return {
        "success": True,
        "message": f"Resolucion sincronizada con {source_ticket_id}" + (" y cerrado" if source_closed else ""),
        "source_key": source_ticket_id,
        "source_closed": source_closed,
        "warning": warning,
    }


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
    from ..services import redacted_cache

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

    # Try cache first
    redacted_bytes = redacted_cache.get(source_ticket_id, filename)
    cache_hit = redacted_bytes is not None

    if not cache_hit:
        content_url = attachment.get("content", "")
        if not content_url:
            raise HTTPException(status_code=404, detail="El adjunto no tiene URL de contenido")

        content_bytes = await connector.download_attachment(content_url)
        if not content_bytes:
            raise HTTPException(status_code=502, detail="No se pudo descargar el adjunto")

        import asyncio as _asyncio
        processor = AttachmentProcessor()
        redacted_bytes = await _asyncio.to_thread(processor.redact_image, content_bytes)

        if redacted_bytes is None:
            raise HTTPException(
                status_code=501,
                detail="Presidio Image Redactor no disponible. Instalar: pip install presidio-image-redactor"
            )
        redacted_cache.put(source_ticket_id, filename, redacted_bytes)

    await db.add_audit_log(
        operator_id="operator",
        action="view_redacted_attachment",
        ticket_mapping_id=ticket_id,
        details=f"attachment={filename}, index={attachment_index}, cache={'hit' if cache_hit else 'miss'}",
    )

    return Response(
        content=redacted_bytes,
        media_type="image/png",
        headers={
            "Content-Disposition": f'inline; filename="redacted_{filename}.png"',
            "X-Cache": "HIT" if cache_hit else "MISS",
        },
    )


# -------------------------------------------------------------
# Unified close: destination + source comment + worklog + source close
# All-or-nothing with best-effort rollback on failure.
# -------------------------------------------------------------

_CLOSE_KEYWORDS = (
    "done", "closed", "close", "resolved", "resolve", "resolver", "resolucion",
    "resuelto", "cerrado", "cerrar",
    "finalizar", "finalizado", "finalize",
    "completar", "completado", "complete", "completed",
    "terminar", "terminado",
)


async def _has_close_transition(connector, ticket_key: str) -> tuple[bool, list[str]]:
    """Pre-check: confirm the ticket has a transition whose name looks like 'done/close/resolve'."""
    try:
        transitions = await connector.get_available_transitions(ticket_key)
    except Exception as e:
        logger.warning("close_precheck_transitions_failed", ticket=ticket_key, error=str(e))
        return False, []
    names = [t.get("name", "") for t in transitions]
    if any(any(kw in n.lower() for kw in _CLOSE_KEYWORDS) for n in names):
        return True, names
    return False, names


@router.post("/{ticket_id}/close")
async def close_ticket(
    ticket_id: int,
    body: CloseTicketRequest,
    client_id: Optional[str] = Query(None),
):
    """Unified close: finalize destination + publish resolution + log work + close source.

    Atomic with best-effort rollback:
      1. Pre-check: source must have a visible close transition.
      2. Build summary (operator-provided or last agent message).
      3. Build time_spent (operator-provided or LLM-estimated).
      4. Close destination (skip if already resolved).
      5. Reconstruct sub_map from source; de-anonymize summary.
      6. Publish [RESOLUCION] comment in source.
      7. Add worklog in source.
      8. Close source via walk_transitions_to / update_status.
      9. Mark DB as closed, invalidate cache, audit.

    On failure at step 4+, attempts rollback in reverse: delete worklog, delete
    comment, reopen destination. Returns 5xx with details; DB stays at resolved/prior.
    """
    state = _get_state()
    db = state["db"]
    anonymizer = state["anonymizer"]
    destination = state.get("destination_connector")
    ws_manager = state.get("ws_manager")
    agent = state.get("agent")

    if not destination:
        raise HTTPException(status_code=503, detail="No hay conector destino configurado")

    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if ticket["status"] == "closed":
        raise HTTPException(status_code=409, detail="El ticket ya esta cerrado")

    source_id = ticket["source_ticket_id"]
    dest_key = ticket["kosin_ticket_id"]

    # Resolve source connector
    connector_router = state.get("connector_router")
    if connector_router:
        try:
            _, source_connector = connector_router.get_connector(source_id)
        except ValueError:
            source_connector = state["jira_connector"]
    else:
        source_connector = state["jira_connector"]

    async def _progress(step: str, detail: str = ""):
        if not (client_id and ws_manager and ws_manager.is_connected(client_id)):
            return
        await ws_manager.send_message(client_id, {
            "type": "sync_progress",
            "data": {"step": step, "detail": detail, "ticket_id": ticket_id},
        })

    # --- Step 1: Pre-check both destination and source can be closed ---
    await _progress("precheck", f"Verificando transiciones de {dest_key} y {source_id}")

    # Destination: only if it's not already in a resolved/closed-like state.
    # If ticket.status is 'resolved' we know destination is already closed, skip.
    dest_available: list[str] = []
    if ticket["status"] != "resolved":
        dest_can_close, dest_available = await _has_close_transition(destination, dest_key)
        if not dest_can_close:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"El ticket destino {dest_key} no tiene una transicion de cierre visible. "
                    f"Transiciones disponibles: {dest_available or 'ninguna'}. "
                    f"Revisa el workflow en el proyecto destino o los permisos del token."
                ),
            )

    src_can_close, src_available = await _has_close_transition(source_connector, source_id)
    if not src_can_close:
        raise HTTPException(
            status_code=409,
            detail=(
                f"El ticket origen {source_id} no tiene una transicion de cierre visible. "
                f"Transiciones disponibles: {src_available or 'ninguna'}. "
                f"Revisa el workflow en el proyecto origen o los permisos del token."
            ),
        )

    # --- Step 2: Build resolution summary ---
    chat_history = await db.get_chat_history(ticket_id)
    import re
    summary_anon = (body.summary or "").strip()
    if not summary_anon:
        agent_msgs = [m for m in chat_history if m["role"] == "agent"]
        if not agent_msgs:
            raise HTTPException(
                status_code=400,
                detail="No hay resumen ni mensajes del agente para usar como resolucion",
            )
        summary_anon = re.sub(r"\[CHIPS[:\s].*?\]", "", agent_msgs[-1]["message"], flags=re.DOTALL).strip()
    if not summary_anon:
        raise HTTPException(status_code=400, detail="El resumen de resolucion quedo vacio")

    # --- Step 3: Resolve time_spent (user → normalize; else LLM estimate) ---
    time_spent: Optional[str] = None
    time_source = "operator"
    time_rationale = ""
    if body.time_spent:
        time_spent = normalize_jira_time(body.time_spent)
        if not time_spent:
            raise HTTPException(
                status_code=400,
                detail=f"Formato de horas invalido: '{body.time_spent}'. Usa formato Jira (p.ej. '2h 30m', '45m', '1h').",
            )
    else:
        if not agent or not getattr(agent, "llm", None):
            raise HTTPException(
                status_code=503,
                detail="No hay LLM configurado para estimar horas. Indicalas manualmente.",
            )
        await _progress("estimating_time", "Estimando horas con IA")
        time_spent, time_rationale = await estimate_time_with_llm(chat_history, agent.llm)
        time_source = "llm"

    # --- Step 4: De-anonymize summary using source as ground truth ---
    await _progress("deanonymizing", "De-anonimizando resumen")
    try:
        source_ticket = await source_connector.get_ticket(source_id)
        comments = await source_connector.get_comments(source_id)
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

    real_summary = Anonymizer.de_anonymize(summary_anon, sub_map)
    comment_text = f"[RESOLUCION] {real_summary}"

    # --- State tracking for rollback ---
    destination_was_closed_here = False
    source_comment_id: Optional[str] = None
    source_worklog_id: Optional[str] = None

    async def _rollback(reason: str):
        logger.warning("close_rollback_start", ticket_id=ticket_id, reason=reason)
        if source_worklog_id:
            try:
                await source_connector.delete_worklog(source_id, source_worklog_id)
            except Exception as e:
                logger.error("rollback_worklog_failed", error=str(e))
        if source_comment_id and hasattr(source_connector, "delete_comment"):
            try:
                await source_connector.delete_comment(source_id, source_comment_id)
            except Exception as e:
                logger.error("rollback_comment_failed", error=str(e))
        if destination_was_closed_here:
            try:
                await destination.walk_transitions_to(dest_key, "open")
            except Exception as e:
                logger.warning("rollback_reopen_destination_failed", error=str(e))
        await db.add_audit_log(
            operator_id="operator",
            action="close_rollback",
            ticket_mapping_id=ticket_id,
            details=f"reason={reason}",
        )

    try:
        # --- Step 5: Close destination (if not already) ---
        if ticket["status"] != "resolved":
            await _progress("closing_destination", f"Cerrando destino {dest_key}")
            ok = False
            dest_steps: list[str] = []
            try:
                ok, dest_steps = await destination.walk_transitions_to(dest_key, "done")
            except Exception as e:
                logger.warning("close_walk_destination_failed", error=str(e))
            if not ok:
                try:
                    ok = await destination.update_status(dest_key, "done")
                    if ok:
                        dest_steps.append("fallback:update_status")
                except Exception as e:
                    logger.warning("close_update_destination_failed", error=str(e))
            if not ok:
                raise HTTPException(
                    status_code=502,
                    detail=(
                        f"No se pudo cerrar el ticket destino {dest_key}. "
                        f"Transiciones aplicadas: {dest_steps or 'ninguna'}. "
                        f"Transiciones disponibles ahora: {dest_available}. "
                        f"Revisa el workflow KOSIN."
                    ),
                )
            destination_was_closed_here = True

        # --- Step 6: Publish comment in source ---
        await _progress("publishing_comment", f"Publicando resolucion en {source_id}")
        if hasattr(source_connector, "add_comment_with_id"):
            c_ok, c_id = await source_connector.add_comment_with_id(source_id, comment_text)
        else:
            c_ok = await source_connector.add_comment(source_id, comment_text)
            c_id = None
        if not c_ok:
            raise HTTPException(status_code=502, detail="Error publicando comentario de resolucion en origen")
        source_comment_id = c_id

        # --- Step 7: Add worklog in source ---
        await _progress("logging_work", f"Registrando {time_spent} en {source_id}")
        worklog_comment = f"Resolucion ticket {dest_key}: {real_summary[:500]}"
        if time_source == "llm":
            worklog_comment = f"[Horas estimadas por IA] {worklog_comment}"
        try:
            if hasattr(source_connector, "add_worklog_with_id"):
                w_ok, w_id = await source_connector.add_worklog_with_id(
                    source_id, time_spent, worklog_comment
                )
            else:
                w_ok = await source_connector.add_worklog(source_id, time_spent, worklog_comment)
                w_id = None
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Error registrando worklog en {source_id}: {e}")
        if not w_ok:
            raise HTTPException(status_code=502, detail=f"No se pudo registrar worklog en {source_id}")
        source_worklog_id = w_id

        # --- Step 8: Close source ---
        await _progress("closing_source", f"Cerrando origen {source_id}")
        source_closed = False
        source_steps: list[str] = []
        try:
            source_closed, source_steps = await source_connector.walk_transitions_to(source_id, "done")
        except Exception as e:
            logger.warning("close_walk_source_failed", error=str(e))

        if not source_closed:
            try:
                source_closed = await source_connector.update_status(source_id, "done")
                if source_closed:
                    source_steps.append("fallback:update_status")
            except Exception as e:
                logger.warning("close_update_source_failed", error=str(e))

        if not source_closed:
            raise HTTPException(
                status_code=502,
                detail=(
                    f"No se pudo cerrar el ticket origen {source_id} despues del worklog. "
                    f"Se ha hecho rollback de comentario + worklog + destino. "
                    f"Pasos intentados: {source_steps or 'ninguno'}."
                ),
            )

    except HTTPException:
        await _rollback("close_step_failed")
        raise
    except Exception as e:
        await _rollback(f"unexpected:{e}")
        raise HTTPException(status_code=500, detail=f"Error inesperado al cerrar: {e}")

    # --- Step 9: Commit in DB ---
    await db.update_ticket_status(ticket_id, "closed")
    if agent:
        agent.invalidate_map_cache(ticket_id)

    await db.add_audit_log(
        operator_id="operator",
        action="close_ticket_unified",
        ticket_mapping_id=ticket_id,
        details=(
            f"source={source_id}, dest={dest_key}, time_spent={time_spent} ({time_source}), "
            f"source_steps={source_steps}"
        ),
    )

    await _progress("completed", f"Ticket cerrado — {time_spent} registradas en origen")
    logger.info(
        "close_ticket_unified_ok",
        ticket_id=ticket_id,
        source=source_id,
        dest=dest_key,
        time_spent=time_spent,
        time_source=time_source,
    )

    return {
        "success": True,
        "message": f"Ticket cerrado correctamente — {time_spent} registradas en {source_id}",
        "source_key": source_id,
        "dest_key": dest_key,
        "time_spent": time_spent,
        "time_source": time_source,
        "time_rationale": time_rationale,
        "source_transition_steps": source_steps,
    }
