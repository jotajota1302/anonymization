"""Create the VOLCADO parent ticket + source tickets with PII in KOSIN for POC testing.

This script:
1. Creates the [VOLCADO-ANON] parent ticket (container for anonymized copies)
2. Updates KOSIN_PARENT_KEY in .env with the new parent key
3. Creates 4 source tickets simulating real client tickets with PII

Usage: python create_source_tickets.py
Cleanup: python cleanup_tickets.py
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
ENV_FILE = ".env"


def update_env_parent_key(new_key: str):
    """Update KOSIN_PARENT_KEY in .env file."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ENV_FILE)
    if not os.path.exists(env_path):
        print(f"  AVISO: {env_path} no existe, no se puede actualizar KOSIN_PARENT_KEY")
        return

    with open(env_path, "r") as f:
        content = f.read()

    content = re.sub(
        r"^KOSIN_PARENT_KEY=.*$",
        f"KOSIN_PARENT_KEY={new_key}",
        content,
        flags=re.MULTILINE,
    )

    with open(env_path, "w") as f:
        f.write(content)

    print(f"  -> .env actualizado: KOSIN_PARENT_KEY={new_key}")


async def create_tickets():
    print(f"=== Preparando entorno de pruebas en KOSIN ({settings.kosin_project}) ===\n")

    # Check for existing test tickets
    if os.path.exists(CREATED_KEYS_FILE):
        with open(CREATED_KEYS_FILE) as f:
            existing = json.load(f)
        if existing.get("source_tickets") or (isinstance(existing, list) and existing):
            keys = [t["key"] for t in (existing.get("source_tickets", []) if isinstance(existing, dict) else existing)]
            print(f"ATENCION: Ya existen tickets de prueba: {keys}")
            print(f"Ejecuta 'python cleanup_tickets.py' primero.\n")
            return

    result = {"parent_key": None, "source_tickets": []}

    async with httpx.AsyncClient(timeout=30) as client:
        # Step 1: Create VOLCADO parent ticket
        print("--- Paso 1: Crear ticket padre [VOLCADO-ANON] ---")
        parent_payload = {
            "fields": {
                "project": {"key": settings.kosin_project},
                "summary": "[VOLCADO-ANON] Tickets anonimizados - POC Plataforma Anonimizacion",
                "description": (
                    "Ticket contenedor para las copias anonimizadas creadas por la "
                    "Plataforma de Anonimizacion. Las sub-tareas de este ticket son "
                    "copias anonimizadas de tickets reales, usadas por operadores offshore."
                ),
                "issuetype": {"id": "10200"},  # Evolutive
                "priority": {"name": "Medium"},
            }
        }

        try:
            resp = await client.post(f"{API_BASE}/issue", headers=HEADERS, json=parent_payload)
            resp.raise_for_status()
            parent_key = resp.json()["key"]
            result["parent_key"] = parent_key
            print(f"  -> CREADO: {parent_key}")

            # Update .env
            update_env_parent_key(parent_key)
        except httpx.HTTPError as e:
            print(f"  -> ERROR creando parent: {e}")
            if hasattr(e, "response") and e.response is not None:
                print(f"     {e.response.text[:300]}")
            print("\nNo se puede continuar sin el ticket padre.")
            return

        # Step 2: Create source tickets with PII
        print(f"\n--- Paso 2: Crear {len(SOURCE_TICKETS)} tickets fuente con PII ---")

        for i, ticket in enumerate(SOURCE_TICKETS, 1):
            prio_map = {"Highest": "Critical", "High": "High", "Medium": "Medium", "Low": "Low"}
            payload = {
                "fields": {
                    "project": {"key": settings.kosin_project},
                    "summary": ticket["summary"],
                    "description": ticket["description"],
                    "issuetype": {"id": "10601"},  # Support
                    "priority": {"name": prio_map.get(ticket["priority"], ticket["priority"])},
                    "customfield_24800": {"id": "26801"},
                    "customfield_12800": 1,
                }
            }

            print(f"  [{i}/{len(SOURCE_TICKETS)}] {ticket['summary'][:65]}...")

            try:
                resp = await client.post(f"{API_BASE}/issue", headers=HEADERS, json=payload)
                resp.raise_for_status()
                data = resp.json()
                key = data["key"]
                result["source_tickets"].append({
                    "key": key,
                    "id": data.get("id"),
                    "summary": ticket["summary"],
                    "priority": ticket["priority"],
                })
                print(f"       -> CREADO: {key}")
            except httpx.HTTPError as e:
                print(f"       -> ERROR: {e}")
                if hasattr(e, "response") and e.response is not None:
                    print(f"          {e.response.text[:300]}")

    # Save for cleanup
    with open(CREATED_KEYS_FILE, "w") as f:
        json.dump(result, f, indent=2)

    n = len(result["source_tickets"])
    print(f"\n{'='*60}")
    print(f" Entorno de pruebas creado:")
    print(f"   Parent VOLCADO: {result['parent_key']}")
    print(f"   Tickets fuente: {[t['key'] for t in result['source_tickets']]}")
    print(f"   Guardado en {CREATED_KEYS_FILE}")
    print(f"{'='*60}")
    print(f"\nSiguientes pasos:")
    print(f"  1. Arranca el backend:  python -m uvicorn app.main:app --port 8000")
    print(f"  2. Arranca el frontend: cd ../frontend && npm run dev")
    print(f"  3. Abre http://localhost:3000 y selecciona un ticket del board")
    print(f"\nPara limpiar:  python cleanup_tickets.py")


if __name__ == "__main__":
    asyncio.run(create_tickets())
