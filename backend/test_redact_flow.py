"""One-shot test: download attachments from STDVERT1-28449 and run the
full Presidio redact pipeline locally (no writes to destination Jira).

Usage:
    python test_redact_flow.py
"""
import asyncio
import os
import sys

import aiosqlite

sys.path.insert(0, ".")
from app.connectors.kosin import KosinConnector
from app.services.attachment_processor import AttachmentProcessor


async def main():
    conn = await aiosqlite.connect("data/ticketing.db")
    conn.row_factory = aiosqlite.Row
    cur = await conn.execute(
        "SELECT base_url, auth_token, project_key FROM system_config "
        "WHERE system_name='stdvert1'"
    )
    row = await cur.fetchone()
    await conn.close()

    connector = KosinConnector(
        base_url=row["base_url"],
        token=row["auth_token"],
        project=row["project_key"],
    )

    key = "STDVERT1-28449"
    print(f"=== Leyendo {key} ===")
    ticket = await connector.get_ticket(key)
    print(f'Summary: {ticket["summary"]}')
    attachments = ticket.get("attachments", [])
    print(f"Total adjuntos: {len(attachments)}")
    for i, a in enumerate(attachments):
        print(
            f'  [{i}] {a["filename"]} '
            f'({a.get("mimeType", "?")}) '
            f'{a.get("size", 0)} bytes'
        )

    images = [
        (i, a) for i, a in enumerate(attachments)
        if a["filename"].rsplit(".", 1)[-1].lower() in ("jpg", "jpeg", "png", "bmp", "tiff", "tif")
    ]
    if not images:
        print("\n[INFO] El ticket no tiene imagenes adjuntas.")
        return

    processor = AttachmentProcessor()
    out_dir = "data/test_redact_out"
    os.makedirs(out_dir, exist_ok=True)

    print(f"\n=== Redactando {len(images)} imagen(es) ===")
    for i, a in images:
        fname = a["filename"]
        print(f"\n[{i}] {fname}")
        raw = await connector.download_attachment(a["content"])
        print(f"   descargados {len(raw)} bytes")

        ents = processor.analyze_image(raw)
        print(f"   Presidio detecto {len(ents)} entidades:")
        for e in ents[:15]:
            print(
                f'     - {e["entity_type"]:15s} '
                f'score={e["score"]:.2f}  '
                f'box=({e["left"]},{e["top"]},{e["width"]}x{e["height"]})'
            )

        redacted = processor.redact_image(raw)
        if redacted is None:
            print("   ERROR: redact_image devolvio None (Presidio no disponible?)")
            continue

        out_orig = f"{out_dir}/{fname}"
        out_red = f"{out_dir}/redacted_{fname.rsplit('.', 1)[0]}.png"
        with open(out_orig, "wb") as f:
            f.write(raw)
        with open(out_red, "wb") as f:
            f.write(redacted)
        print(f"   original  -> {out_orig} ({len(raw)} bytes)")
        print(f"   redactado -> {out_red} ({len(redacted)} bytes)")


if __name__ == "__main__":
    asyncio.run(main())
