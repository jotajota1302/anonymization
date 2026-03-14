"""Delete all POC test tickets from KOSIN and clean local DB.

Deletes:
1. Source tickets created by create_source_tickets.py
2. Anonymized copies ([ANON]) created by the platform during ingestion
3. The VOLCADO parent ticket

Usage: python cleanup_tickets.py
"""

import asyncio
import json
import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import httpx
from app.config import settings

API_BASE = f"{settings.kosin_url}/rest/api/2"
HEADERS = {
    "Authorization": f"Bearer {settings.kosin_token}",
    "Accept": "application/json",
}

CREATED_KEYS_FILE = "created_source_tickets.json"
ENV_FILE = ".env"


async def cleanup():
    keys_to_delete = []
    parent_key = None

    # 1. Load tickets from tracking file
    if os.path.exists(CREATED_KEYS_FILE):
        with open(CREATED_KEYS_FILE) as f:
            data = json.load(f)

        # Support both old format (list) and new format (dict)
        if isinstance(data, list):
            keys_to_delete.extend([t["key"] for t in data])
        elif isinstance(data, dict):
            parent_key = data.get("parent_key")
            keys_to_delete.extend([t["key"] for t in data.get("source_tickets", [])])

        print(f"Tickets fuente a borrar: {keys_to_delete}")
        if parent_key:
            print(f"Ticket padre VOLCADO: {parent_key}")
    else:
        print("No se encontro created_source_tickets.json")

    # 2. Load anonymized copies from local DB
    from app.services.database import DatabaseService
    db = DatabaseService(settings.db_path)
    await db.init()
    all_tickets = await db.get_all_tickets()
    anon_keys = [
        t["kosin_ticket_id"]
        for t in all_tickets
        if not t["kosin_ticket_id"].startswith("KOS-")  # Skip mock keys
    ]
    if anon_keys:
        print(f"Copias anon en BD local: {anon_keys}")
        keys_to_delete.extend(anon_keys)

    # Deduplicate, remove parent (deleted last with subtasks)
    keys_to_delete = list(set(keys_to_delete))
    if parent_key and parent_key in keys_to_delete:
        keys_to_delete.remove(parent_key)

    if not keys_to_delete and not parent_key:
        print("\nNo hay tickets que borrar.")
        return

    # 3. Delete individual tickets first
    print(f"\n=== Borrando {len(keys_to_delete)} tickets de KOSIN ===\n")

    async with httpx.AsyncClient(timeout=30) as client:
        for key in keys_to_delete:
            try:
                resp = await client.delete(
                    f"{API_BASE}/issue/{key}",
                    headers=HEADERS,
                    params={"deleteSubtasks": "true"},
                )
                if resp.status_code == 204:
                    print(f"  BORRADO: {key}")
                elif resp.status_code == 404:
                    print(f"  NO EXISTE: {key} (ya borrado)")
                else:
                    print(f"  {key}: HTTP {resp.status_code} - {resp.text[:100]}")
            except httpx.HTTPError as e:
                print(f"  ERROR {key}: {e}")

        # 4. Delete parent ticket last (with remaining subtasks)
        if parent_key:
            print(f"\n--- Borrando ticket padre {parent_key} (con subtareas) ---")
            try:
                resp = await client.delete(
                    f"{API_BASE}/issue/{parent_key}",
                    headers=HEADERS,
                    params={"deleteSubtasks": "true"},
                )
                if resp.status_code == 204:
                    print(f"  BORRADO: {parent_key}")
                elif resp.status_code == 404:
                    print(f"  NO EXISTE: {parent_key}")
                else:
                    print(f"  {parent_key}: HTTP {resp.status_code} - {resp.text[:100]}")
            except httpx.HTTPError as e:
                print(f"  ERROR {parent_key}: {e}")

    # 5. Clean local files
    if os.path.exists(CREATED_KEYS_FILE):
        os.remove(CREATED_KEYS_FILE)
        print(f"\nEliminado {CREATED_KEYS_FILE}")

    db_path = settings.db_path
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"Eliminado {db_path}")

    # 6. Clear KOSIN_PARENT_KEY in .env
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ENV_FILE)
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            content = f.read()
        content = re.sub(
            r"^KOSIN_PARENT_KEY=.*$",
            "KOSIN_PARENT_KEY=",
            content,
            flags=re.MULTILINE,
        )
        with open(env_path, "w") as f:
            f.write(content)
        print("Limpiado KOSIN_PARENT_KEY en .env")

    print("\n=== Cleanup completado ===")
    print("Para crear nuevo entorno de pruebas: python create_source_tickets.py")


if __name__ == "__main__":
    asyncio.run(cleanup())
