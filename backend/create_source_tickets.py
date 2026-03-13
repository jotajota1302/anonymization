"""Create 4 source tickets with PII in KOSIN (PESESG) for POC testing.

These simulate "real client tickets" that the platform will read and anonymize.
Run this ONCE, note the created keys, then use the platform to ingest them.

Usage: python create_source_tickets.py
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
    "Content-Type": "application/json",
}

SOURCE_TICKETS = [
    {
        "summary": "Poliza hogar Elena Ruiz Fernandez rechazada por error en tarificacion",
        "description": (
            "La asegurada Elena Ruiz Fernandez (elena.ruiz@gmail.com, tel: +34 654 321 987, "
            "DNI: 45678901F) ha contactado indicando que su poliza de hogar num. HG-2024-88012 "
            "fue rechazada al intentar renovarla a traves del portal web.\n\n"
            "Elena reside en Calle Alcala 145, 3B, Madrid 28009. Su cuenta bancaria para "
            "domiciliacion es ES6621000418401234567891.\n\n"
            "El sistema de tarificacion (IP: 10.50.20.15) devuelve error 500 al calcular la prima. "
            "El agente comercial asignado es Roberto Diaz (roberto.diaz@segurosacme.es, ext. 4521).\n\n"
            "Segun el log del servidor tarificador, el error se produce al validar el codigo postal "
            "contra la tabla de zonas de riesgo. La asegurada lleva 8 anos como cliente y tiene "
            "tambien una poliza de auto activa."
        ),
        "priority": "High",
    },
    {
        "summary": "Siniestro auto - Miguel Angel Torres reclama danos no cubiertos tras accidente A-6",
        "description": (
            "El tomador Miguel Angel Torres (miguelangel.torres@hotmail.com, tel: +34 698 112 233, "
            "DNI: 78901234G) ha presentado reclamacion por el siniestro SIN-2026-03401 ocurrido "
            "el 10/03/2026 en la autovia A-6 km 42.\n\n"
            "Vehiculo asegurado: Seat Leon matricula 4521-BCD. Miguel Angel reside en "
            "Avenida de la Constitucion 78, Valencia 46009. IBAN para indemnizacion: "
            "ES4500491500051234567892.\n\n"
            "Perito asignado: Laura Gonzalez Martinez (laura.gonzalez@peritosya.com, "
            "tel: +34 611 444 555, DNI: 23456789H).\n\n"
            "Taller concertado Talleres Hernandez (IP sistema: 172.20.5.30) ha enviado "
            "presupuesto de 4.200 EUR pero el sistema de valoracion automatica (IP: 10.50.20.22) "
            "calcula solo 2.800 EUR. El cliente amenaza con acudir al Defensor del Asegurado."
        ),
        "priority": "Highest",
    },
    {
        "summary": "Error emision certificado seguro vida Carmen Navarro Lopez - urgente",
        "description": (
            "Carmen Navarro Lopez (carmen.navarro@outlook.es, tel: +34 677 998 877, "
            "DNI: 34567890J) solicita urgentemente un certificado de su seguro de vida "
            "poliza VD-2025-55021 para presentar en su entidad bancaria.\n\n"
            "Carmen vive en Calle Sierpes 44, Sevilla 41004. IBAN: ES8520953642981234567893.\n\n"
            "El sistema de emision de documentos (IP: 10.50.20.35) genera el PDF pero con la "
            "fecha de nacimiento incorrecta (muestra 15/03/1975 en lugar de 15/03/1985).\n\n"
            "Mediador asociado: Fernando Moreno (fernando.moreno@mediadores.org, tel: +34 622 333 444). "
            "Carmen necesita el certificado antes del viernes para la firma de su hipoteca."
        ),
        "priority": "High",
    },
    {
        "summary": "Alerta fraude poliza salud Pablo Jimenez Garcia - bloqueo recomendado",
        "description": (
            "El sistema antifraude (IP: 10.50.20.40) ha generado alerta AF-2026-0891 sobre "
            "el asegurado Pablo Jimenez Garcia (pablo.jimenez@yahoo.es, tel: +34 666 777 888, "
            "DNI: 56789012K).\n\n"
            "Se han detectado 3 reclamaciones de salud en los ultimos 2 meses por un total de "
            "12.500 EUR, todas en la clinica Salud Optima S.L. (CIF: B12345678). "
            "Pablo reside en Calle Mayor 22, Bilbao 48001. IBAN: ES1201280012000123456794.\n\n"
            "Las facturas presentan patron sospechoso: misma tipografia, numeracion correlativa, "
            "y el medico firmante Dr. Alvarez (colegiado 28/12345) no aparece en el registro "
            "del Colegio de Medicos de Vizcaya.\n\n"
            "Investigador asignado: Antonio Lopez (antonio.lopez@segurosacme.es, IP VPN: 83.50.44.12). "
            "Se recomienda bloquear la poliza SAL-2025-77034 hasta completar la investigacion."
        ),
        "priority": "Highest",
    },
]

CREATED_KEYS_FILE = "created_source_tickets.json"


async def create_tickets():
    print(f"=== Creando 4 tickets fuente en KOSIN ({settings.kosin_project}) ===\n")
    print(f"URL: {API_BASE}")
    print(f"Proyecto: {settings.kosin_project}")
    print(f"Issue type ID: {settings.kosin_issue_type_id}\n")

    created = []

    async with httpx.AsyncClient(timeout=30) as client:
        for i, ticket in enumerate(SOURCE_TICKETS, 1):
            # Map priority names to valid KOSIN values
            prio_map = {"Highest": "Critical", "High": "High", "Medium": "Medium", "Low": "Low"}
            payload = {
                "fields": {
                    "project": {"key": settings.kosin_project},
                    "summary": ticket["summary"],
                    "description": ticket["description"],
                    "issuetype": {"id": "10601"},  # Support (non-subtask)
                    "priority": {"name": prio_map.get(ticket["priority"], ticket["priority"])},
                    "customfield_24800": {"id": "26801"},  # Billable to customer: No
                    "customfield_12800": 1,  # Number of client requests
                }
            }

            print(f"--- Ticket {i}/4: {ticket['summary'][:60]}... ---")

            try:
                resp = await client.post(
                    f"{API_BASE}/issue",
                    headers=HEADERS,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                key = data["key"]
                created.append({
                    "key": key,
                    "id": data.get("id"),
                    "summary": ticket["summary"],
                    "priority": ticket["priority"],
                })
                print(f"  CREADO: {key}")
            except httpx.HTTPError as e:
                print(f"  ERROR: {e}")
                if hasattr(e, 'response') and e.response is not None:
                    print(f"  Response: {e.response.text[:300]}")

    # Save created keys for later cleanup
    with open(CREATED_KEYS_FILE, "w") as f:
        json.dump(created, f, indent=2)

    print(f"\n=== {len(created)} tickets creados en KOSIN ===")
    print(f"Keys: {[t['key'] for t in created]}")
    print(f"\nGuardado en {CREATED_KEYS_FILE} para poder borrarlos luego.")
    print("\nPara ingestar en la plataforma:")
    for t in created:
        print(f"  curl -X POST http://localhost:8000/api/tickets/ingest-from-jira/{t['key']}")


if __name__ == "__main__":
    asyncio.run(create_tickets())
