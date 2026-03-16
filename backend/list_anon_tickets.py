"""List [ANON] tickets created in KOSIN in the last 2 days.

Shows tickets that are likely duplicates or test artifacts.
After reviewing, run with --delete to remove them.

Usage:
  python list_anon_tickets.py           # List only
  python list_anon_tickets.py --delete  # List and delete after confirmation
"""

import asyncio
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

DELETE_MODE = "--delete" in sys.argv


async def main():
    # JQL: all tickets in the project, we filter by key number in Python
    jql = (
        f'project={settings.kosin_project} '
        f'ORDER BY key DESC'
    )

    print(f"Buscando tickets [ANON] en {settings.kosin_project} (últimos 2 días)...\n")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{API_BASE}/search",
            headers=HEADERS,
            params={
                "jql": jql,
                "maxResults": 100,
                "fields": "summary,status,priority,issuetype,created,parent",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        issues = data.get("issues", [])

    # Filter: only keys >= PESESG-264
    MIN_KEY_NUM = 264
    filtered = []
    for issue in issues:
        key = issue["key"]
        try:
            num = int(key.split("-")[1])
            if num >= MIN_KEY_NUM:
                filtered.append(issue)
        except (IndexError, ValueError):
            pass
    issues = filtered

    if not issues:
        print(f"No se encontraron tickets con key >= PESESG-{MIN_KEY_NUM}.")
        return

    print(f"Encontrados {len(issues)} tickets (PESESG-{MIN_KEY_NUM}+):\n")
    print(f"{'#':<4} {'Key':<16} {'Tipo':<20} {'Estado':<15} {'Parent':<16} {'Creado':<22} {'Summary'}")
    print("-" * 140)

    for i, issue in enumerate(issues, 1):
        key = issue["key"]
        fields = issue["fields"]
        summary = fields.get("summary", "")[:60]
        status = fields.get("status", {}).get("name", "?")
        issue_type = fields.get("issuetype", {}).get("name", "?")
        created = fields.get("created", "?")[:19]
        parent = fields.get("parent", {}).get("key", "-") if fields.get("parent") else "-"
        print(f"{i:<4} {key:<16} {issue_type:<20} {status:<15} {parent:<16} {created:<22} {summary}")

    if not DELETE_MODE:
        print(f"\nPara borrar estos {len(issues)} tickets, ejecuta:")
        print("  python list_anon_tickets.py --delete")
        return

    # Confirm deletion
    print(f"\n¿Borrar los {len(issues)} tickets listados arriba? (s/N): ", end="", flush=True)
    answer = input().strip().lower()
    if answer not in ("s", "si", "sí", "y", "yes"):
        print("Cancelado.")
        return

    # Delete
    print(f"\n=== Borrando {len(issues)} tickets ===\n")
    deleted = 0
    async with httpx.AsyncClient(timeout=30) as client:
        for issue in issues:
            key = issue["key"]
            try:
                resp = await client.delete(
                    f"{API_BASE}/issue/{key}",
                    headers=HEADERS,
                    params={"deleteSubtasks": "true"},
                )
                if resp.status_code == 204:
                    print(f"  BORRADO: {key}")
                    deleted += 1
                elif resp.status_code == 404:
                    print(f"  NO EXISTE: {key}")
                else:
                    print(f"  ERROR {key}: HTTP {resp.status_code} - {resp.text[:100]}")
            except httpx.HTTPError as e:
                print(f"  ERROR {key}: {e}")

    print(f"\n=== Borrados {deleted}/{len(issues)} tickets ===")

    # Also clean local DB entries for deleted tickets
    if deleted > 0:
        print("\nLimpiando entradas en la DB local...")
        from app.services.database import DatabaseService
        db = DatabaseService(settings.db_path)
        await db.init()
        all_mappings = await db.get_all_ticket_mappings_with_kosin()
        deleted_kosin_keys = {issue["key"] for issue in issues}
        cleaned = 0
        for mapping in all_mappings:
            if mapping["kosin_ticket_id"] in deleted_kosin_keys:
                await db.execute(
                    "DELETE FROM substitution_map WHERE ticket_mapping_id = ?",
                    (mapping["id"],)
                )
                await db.execute(
                    "DELETE FROM chat_history WHERE ticket_mapping_id = ?",
                    (mapping["id"],)
                )
                await db.execute(
                    "DELETE FROM audit_log WHERE ticket_mapping_id = ?",
                    (mapping["id"],)
                )
                await db.execute(
                    "DELETE FROM ticket_mapping WHERE id = ?",
                    (mapping["id"],)
                )
                cleaned += 1
                print(f"  DB limpia: mapping #{mapping['id']} ({mapping['kosin_ticket_id']})")
        if cleaned:
            print(f"  Eliminadas {cleaned} entradas de la DB local.")
        else:
            print("  No había entradas en DB local para estos tickets.")


if __name__ == "__main__":
    asyncio.run(main())
