"""Delete all tickets created by create_source_tickets.py from KOSIN.

Usage: python cleanup_tickets.py
"""

import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import httpx
from app.config import settings

API_BASE = f"{settings.kosin_url}/rest/api/2"
HEADERS = {
    "Authorization": f"Bearer {settings.kosin_token}",
    "Accept": "application/json",
}

CREATED_KEYS_FILE = "created_source_tickets.json"


async def cleanup():
    # Load source tickets
    if os.path.exists(CREATED_KEYS_FILE):
        with open(CREATED_KEYS_FILE) as f:
            source_tickets = json.load(f)
        print(f"Tickets fuente a borrar: {[t['key'] for t in source_tickets]}")
    else:
        source_tickets = []
        print("No se encontro created_source_tickets.json")

    # Also load any anonymized copies from the local DB
    from app.config import settings as s
    from app.services.database import DatabaseService
    db = DatabaseService(s.db_path)
    await db.init()
    all_tickets = await db.get_all_tickets()
    anon_keys = [t["kosin_ticket_id"] for t in all_tickets if not t["kosin_ticket_id"].startswith("KOS-")]

    all_keys = [t["key"] for t in source_tickets] + anon_keys
    all_keys = list(set(all_keys))  # deduplicate

    if not all_keys:
        print("No hay tickets que borrar.")
        return

    print(f"\n=== Borrando {len(all_keys)} tickets de KOSIN ===")
    print(f"Keys: {all_keys}\n")

    async with httpx.AsyncClient(timeout=30) as client:
        for key in all_keys:
            try:
                resp = await client.delete(
                    f"{API_BASE}/issue/{key}",
                    headers=HEADERS,
                )
                if resp.status_code == 204:
                    print(f"  BORRADO: {key}")
                else:
                    print(f"  {key}: status {resp.status_code} - {resp.text[:100]}")
            except httpx.HTTPError as e:
                print(f"  ERROR borrando {key}: {e}")

    # Clean local DB
    if os.path.exists(CREATED_KEYS_FILE):
        os.remove(CREATED_KEYS_FILE)
        print(f"\nEliminado {CREATED_KEYS_FILE}")

    print("\n=== Cleanup completado ===")
    print("Para limpiar tambien la BD local: rm data/ticketing.db")


if __name__ == "__main__":
    asyncio.run(cleanup())
