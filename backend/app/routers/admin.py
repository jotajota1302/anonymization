"""Admin router for managing KOSIN tickets."""

from fastapi import APIRouter, HTTPException
import structlog

from ..main import app_state

logger = structlog.get_logger()

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/tickets")
async def list_admin_tickets():
    """List all ticket mappings with KOSIN info for admin management."""
    db = app_state.get("db")
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    return await db.get_all_ticket_mappings_with_kosin()


@router.delete("/tickets/{kosin_key}")
async def delete_admin_ticket(kosin_key: str):
    """Delete a ticket from DB and from KOSIN."""
    db = app_state.get("db")
    kosin = app_state.get("kosin_connector")
    if not db or not kosin:
        raise HTTPException(status_code=503, detail="Services not available")

    mapping = await db.get_ticket_by_kosin_key(kosin_key)
    if not mapping:
        raise HTTPException(status_code=404, detail=f"No mapping found for {kosin_key}")

    # Delete from KOSIN (with subtasks)
    deleted_from_kosin, kosin_error = await kosin.delete_ticket(kosin_key)

    # Delete from DB (always, even if KOSIN delete fails)
    await db.delete_ticket_mapping(mapping["id"])

    logger.info("admin_ticket_deleted", kosin_key=kosin_key, from_kosin=deleted_from_kosin, kosin_error=kosin_error)
    result = {
        "deleted": True,
        "kosin_key": kosin_key,
        "deleted_from_kosin": deleted_from_kosin,
    }
    if kosin_error:
        result["kosin_error"] = kosin_error
    return result
