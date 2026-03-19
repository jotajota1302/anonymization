"""Admin router for managing tickets."""

from fastapi import APIRouter, HTTPException
import structlog

from ..main import app_state

logger = structlog.get_logger()

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/tickets")
async def list_admin_tickets():
    """List all ticket mappings for admin management."""
    db = app_state.get("db")
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    return await db.get_all_ticket_mappings_with_kosin()


@router.delete("/tickets/{ticket_key}")
async def delete_admin_ticket(ticket_key: str):
    """Delete a ticket from DB and from destination system."""
    db = app_state.get("db")
    destination = app_state.get("destination_connector")
    if not db:
        raise HTTPException(status_code=503, detail="Services not available")

    mapping = await db.get_ticket_by_kosin_key(ticket_key)
    if not mapping:
        raise HTTPException(status_code=404, detail=f"No mapping found for {ticket_key}")

    # Delete from destination (with subtasks)
    deleted_from_dest = False
    dest_error = None
    if destination:
        deleted_from_dest, dest_error = await destination.delete_ticket(ticket_key)

    # Delete from DB (always, even if destination delete fails)
    await db.delete_ticket_mapping(mapping["id"])

    logger.info("admin_ticket_deleted", ticket_key=ticket_key, from_dest=deleted_from_dest, dest_error=dest_error)
    result = {
        "deleted": True,
        "ticket_key": ticket_key,
        "deleted_from_destination": deleted_from_dest,
    }
    if dest_error:
        result["dest_error"] = dest_error
    return result
