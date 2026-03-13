"""Seed script: Populate database with mock anonymized tickets for testing.

Usage: python seed.py
Run from the backend/ directory.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import settings
from app.services.database import DatabaseService
from app.services.anonymizer import Anonymizer


# Tickets realistas de una compania de seguros con PII sensible
MOCK_TICKETS = [
    {
        "source_system": "jira-seguros",
        "source_ticket_id": "PESESG-2001",
        "summary": "Poliza de hogar de Elena Ruiz Fernandez rechazada por error en sistema de tarificacion",
        "description": (
            "La asegurada Elena Ruiz Fernandez (elena.ruiz@gmail.com, tel: +34 654 321 987, "
            "DNI: 45678901F) ha contactado indicando que su poliza de hogar num. HG-2024-88012 "
            "fue rechazada al intentar renovarla a traves del portal web. Elena reside en "
            "Calle Alcala 145, 3B, Madrid 28009. Su cuenta bancaria para domiciliacion es "
            "ES6621000418401234567891. El sistema de tarificacion (IP: 10.50.20.15) devuelve "
            "error 500 al calcular la prima. El agente comercial asignado es Roberto Diaz "
            "(roberto.diaz@segurosacme.es, ext. 4521). Segun el log del servidor tarificador, "
            "el error se produce al validar el codigo postal contra la tabla de zonas de riesgo. "
            "La asegurada lleva 8 anos como cliente y tiene tambien una poliza de auto activa."
        ),
        "priority": "high",
    },
    {
        "source_system": "jira-seguros",
        "source_ticket_id": "PESESG-2002",
        "summary": "Siniestro auto - Miguel Angel Torres reclama danos no cubiertos tras accidente en A-6",
        "description": (
            "El tomador Miguel Angel Torres (miguelangel.torres@hotmail.com, tel: +34 698 112 233, "
            "DNI: 78901234G) ha presentado reclamacion por el siniestro SIN-2026-03401 ocurrido "
            "el 10/03/2026 en la autovia A-6 km 42. El vehiculo asegurado es un Seat Leon "
            "matricula 4521-BCD. Miguel Angel reside en Avenida de la Constitucion 78, Valencia 46009. "
            "Su IBAN para el pago de indemnizacion es ES4500491500051234567892. El perito asignado "
            "es Laura Gonzalez Martinez (laura.gonzalez@peritosya.com, tel: +34 611 444 555, "
            "DNI: 23456789H). El taller concertado Talleres Hernandez (IP sistema: 172.20.5.30) "
            "ha enviado presupuesto de 4.200 EUR pero el sistema de valoracion automatica "
            "(IP: 10.50.20.22) calcula solo 2.800 EUR. El cliente amenaza con acudir al "
            "Defensor del Asegurado."
        ),
        "priority": "critical",
    },
    {
        "source_system": "jira-seguros",
        "source_ticket_id": "PESESG-2003",
        "summary": "Error en emision de certificado de seguro de vida para Carmen Navarro",
        "description": (
            "Carmen Navarro Lopez (carmen.navarro@outlook.es, tel: +34 677 998 877, "
            "DNI: 34567890J) solicita urgentemente un certificado de su seguro de vida "
            "poliza VD-2025-55021 para presentar en su entidad bancaria (Banco Santander, "
            "sucursal de Sevilla, Plaza Nueva 8). Carmen vive en Calle Sierpes 44, "
            "Sevilla 41004. Su IBAN es ES8520953642981234567893. El sistema de emision "
            "de documentos (IP: 10.50.20.35) genera el PDF pero con la fecha de nacimiento "
            "incorrecta (muestra 15/03/1975 en lugar de 15/03/1985). El mediador asociado "
            "es Fernando Moreno (fernando.moreno@mediadores.org, tel: +34 622 333 444). "
            "Carmen necesita el certificado antes del viernes para la firma de su hipoteca."
        ),
        "priority": "high",
    },
    {
        "source_system": "jira-seguros",
        "source_ticket_id": "PESESG-2004",
        "summary": "Fraude potencial detectado en poliza de salud de Pablo Jimenez Garcia",
        "description": (
            "El sistema antifraude (IP: 10.50.20.40) ha generado alerta AF-2026-0891 sobre "
            "el asegurado Pablo Jimenez Garcia (pablo.jimenez@yahoo.es, tel: +34 666 777 888, "
            "DNI: 56789012K). Se han detectado 3 reclamaciones de salud en los ultimos 2 meses "
            "por un total de 12.500 EUR, todas en la clinica Salud Optima S.L. (CIF: B12345678). "
            "Pablo reside en Calle Mayor 22, Bilbao 48001. Su IBAN es ES1201280012000123456794. "
            "Las facturas presentan patron sospechoso: misma tipografia, numeracion correlativa, "
            "y el medico firmante Dr. Alvarez (colegiado 28/12345) no aparece en el registro "
            "del Colegio de Medicos de Vizcaya. El investigador asignado es Antonio Lopez "
            "(antonio.lopez@segurosacme.es, IP VPN: 83.50.44.12). Se recomienda bloquear "
            "la poliza SAL-2025-77034 hasta completar la investigacion."
        ),
        "priority": "critical",
    },
]


async def seed():
    print("=== Seeding database (Tickets Seguros con PII) ===\n")

    db = DatabaseService(settings.db_path)
    await db.init()

    anonymizer = Anonymizer()
    encryption_key = Anonymizer.key_from_string(settings.encryption_key)

    existing = await db.get_all_tickets()
    if existing:
        print(f"Database already has {len(existing)} tickets. Skipping seed.")
        print("To re-seed, delete data/ticketing.db and run again.")
        return

    for i, ticket_data in enumerate(MOCK_TICKETS, 1):
        print(f"\n--- Ticket {i}/{len(MOCK_TICKETS)}: {ticket_data['source_ticket_id']} ---")

        full_text = f"{ticket_data['summary']}\n{ticket_data['description']}"
        anonymized_text, sub_map = anonymizer.anonymize(full_text)

        parts = anonymized_text.split("\n", 1)
        anon_summary = parts[0]
        anon_description = parts[1] if len(parts) > 1 else anon_summary

        kosin_id = f"KOS-{i:03d}"

        ticket_id = await db.create_ticket_mapping(
            source_system=ticket_data["source_system"],
            source_ticket_id=ticket_data["source_ticket_id"],
            kosin_ticket_id=kosin_id,
            summary=anon_summary,
            anonymized_description=anon_description,
            priority=ticket_data["priority"],
        )

        if sub_map:
            encrypted = Anonymizer.encrypt_map(sub_map, encryption_key)
            await db.save_substitution_map(ticket_id, encrypted)

        await db.add_audit_log(
            operator_id="seed_script",
            action="seed_ticket",
            ticket_mapping_id=ticket_id,
            details=f"source={ticket_data['source_ticket_id']}",
        )

        print(f"  KOSIN ID: {kosin_id}")
        print(f"  Summary anonimizado: {anon_summary[:100]}...")
        print(f"  PII detectado: {len(sub_map)} entidades")
        for token, val in sub_map.items():
            print(f"    {token} -> {val}")

    print(f"\n=== Seeding complete: {len(MOCK_TICKETS)} tickets de seguros creados ===")
    print(f"Database: {settings.db_path}")


if __name__ == "__main__":
    asyncio.run(seed())
