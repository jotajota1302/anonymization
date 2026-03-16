"""
Test de anonimizacion offline -- evalua la calidad del pipeline sobre tickets reales.

Descarga las 20 ultimas issues abiertas de STDVERT1 via Jira API,
las pasa por el pipeline de anonimizacion y evalua:
  1. Falsos positivos: terminos tecnicos/codigos que NO deberian anonimizarse
  2. Falsos negativos: PII real que deberia detectarse (test sintetico)
  3. Calidad general: el texto anonimizado conserva su sentido tecnico

Ejecutar:  python test_anonymization.py [--verbose]
"""

import asyncio
import sys
import io
import re
import httpx
from app.config import settings
from app.services.anonymizer import Anonymizer
from app.services.detection import CompositeDetector

# Fix Windows encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# ── ANSI colors ──────────────────────────────────────────────────────────────

def c(text, color):
    codes = {"g": "\033[92m", "r": "\033[91m", "y": "\033[93m", "b": "\033[94m",
             "0": "\033[0m", "B": "\033[1m", "d": "\033[2m"}
    return f"{codes.get(color, '')}{text}{codes['0']}"

# ── Known false-positive patterns (should NEVER be anonymized) ───────────────

# Regex patterns that match technical terms common in SAP/ITSM tickets
TECHNICAL_PATTERNS = [
    re.compile(r'\bRITM\d+\b'),                  # RITM1406827
    re.compile(r'\b[A-Z]{1,5}[-_]\d{1,5}\b'),    # MOD_09, PT03
    re.compile(r'\bZ[A-Z_]{3,}\b'),               # ZOPT_EDITOR_TEXTO, ZFBC
    re.compile(r'\b\d{10}\b'),                     # 2602503346 (doc numbers)
    re.compile(r'\b[A-Z]\d{3}\b'),                 # Z001, V001
    re.compile(r'\bVBBK\b|\bBASIS\b|\bSAP\b|\bSII\b|\bXML\b|\bDEC\b'),
    re.compile(r'\bMOD_\d+\b'),                    # MOD_09
    re.compile(r'\bPT\d{2}\b'),                    # PT03
]

# Words that should never be anonymized (field labels, common terms)
SAFE_WORDS = {
    "nombre", "dirección", "direccion", "campo", "centro", "servicio",
    "comentario", "factura", "pedido", "sociedad", "configuración",
    "retroactividad", "actualizaciones", "modificación", "gestión",
}


# ── Fetch tickets from STDVERT1 ─────────────────────────────────────────────

async def fetch_board_tickets(max_results: int = 20):
    """Fetch the latest open issues from STDVERT1."""
    base = f"{settings.kosin_url}/rest/api/2"
    headers = {
        "Authorization": f"Bearer {settings.kosin_token}",
        "Accept": "application/json",
    }
    project = settings.source_project
    jql = (
        f'project={project} '
        f'AND status in (Open, "In Progress", "To Do") '
        f'ORDER BY created DESC'
    )

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{base}/search",
            headers=headers,
            params={
                "jql": jql,
                "maxResults": max_results,
                "fields": "summary,description,status,priority,issuetype,comment",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    tickets = []
    for issue in data.get("issues", []):
        fields = issue.get("fields", {})
        # Also grab comments text
        comments = fields.get("comment", {}).get("comments", [])
        comments_text = ""
        if comments:
            comments_text = "\n\n--- COMENTARIOS ---\n" + "\n---\n".join(
                f"{cm.get('author', {}).get('displayName', '?')}: {cm.get('body', '')}"
                for cm in comments
            )
        tickets.append({
            "key": issue["key"],
            "summary": fields.get("summary", ""),
            "description": (fields.get("description", "") or ""),
            "comments_text": comments_text,
            "status": fields.get("status", {}).get("name", "?"),
            "priority": fields.get("priority", {}).get("name", "?"),
            "issue_type": fields.get("issuetype", {}).get("name", "?"),
        })
    return tickets


# ── Evaluate one ticket ──────────────────────────────────────────────────────

def evaluate_ticket(ticket, anonymizer, verbose=False):
    """Anonymize a ticket and check for false positives.

    Returns dict with results.
    """
    full_text = f"{ticket['summary']}\n{ticket['description']}{ticket.get('comments_text', '')}"
    anonymized, sub_map = anonymizer.anonymize(full_text)

    false_positives = []
    warnings = []

    for token, original in sub_map.items():
        entity_type = token.split("_")[0].strip("[")
        is_fp = False
        reason = ""

        # Check against known technical patterns
        for pattern in TECHNICAL_PATTERNS:
            if pattern.search(original):
                is_fp = True
                reason = f"matches technical pattern {pattern.pattern}"
                break

        # Check if all words are safe/generic
        if not is_fp:
            words = re.split(r'[\s()\[\],;:\-/]+', original.lower())
            real_words = [w for w in words if w]
            if real_words and all(w in SAFE_WORDS for w in real_words):
                is_fp = True
                reason = "all words are generic field labels"

        # Short all-caps that look like codes
        if not is_fp and re.match(r'^[A-Z_]{2,15}$', original.strip()):
            is_fp = True
            reason = "looks like a code/acronym"

        # Numbers only (IDs, not PII)
        if not is_fp and re.match(r'^\d{4,10}$', original.strip()):
            # Could be an ID, employee number, etc. -- flag as warning not failure
            warnings.append((token, original, "numeric-only, might be ID or CP"))

        if is_fp:
            false_positives.append((token, original, reason))

    return {
        "key": ticket["key"],
        "summary": ticket["summary"][:80],
        "entities": len(sub_map),
        "sub_map": sub_map,
        "anonymized": anonymized,
        "false_positives": false_positives,
        "warnings": warnings,
    }


# ── Synthetic PII test ───────────────────────────────────────────────────────

SYNTHETIC_TICKETS = [
    {
        "key": "SYNTH-PII-001",
        "summary": "Error login para Juan Garcia Lopez",
        "description": (
            "El cliente Juan Garcia Lopez con DNI 12345678A y email "
            "juan.garcia@gmail.com vive en Calle Mayor 15, Madrid. "
            "Llamo desde el 612345678 reportando que no puede acceder."
        ),
        "comments_text": "",
        "status": "Open", "priority": "High", "issue_type": "Support",
        "must_anonymize": ["Juan Garcia Lopez", "12345678A", "juan.garcia@gmail.com", "612345678"],
    },
    {
        "key": "SYNTH-PII-002",
        "summary": "Cambio de cuenta bancaria - Maria Fernandez",
        "description": (
            "La empleada Maria Fernandez Ruiz con DNI 87654321B solicita "
            "el cambio de su IBAN ES6621000418401234567891 al nuevo "
            "ES7720385778983000760236. Su telefono de contacto es 654321987 "
            "y su correo mfernandez@empresa.com. Direccion: Avenida Diagonal 42, Barcelona."
        ),
        "comments_text": "",
        "status": "Open", "priority": "Medium", "issue_type": "Support",
        "must_anonymize": [
            "Maria Fernandez Ruiz", "87654321B", "654321987", "mfernandez@empresa.com",
        ],
    },
    {
        "key": "SYNTH-MIX-003",
        "summary": "[SANTA_LUCIA_AM] RITM9999999 - Error SAP transaccion VA01",
        "description": (
            "El usuario Pedro Martinez (DNI 11111111H, email pmartinez@nttdata.com) "
            "reporta que al ejecutar la transaccion VA01 en mandante 100 del sistema PRD, "
            "el programa SAPMV45A lanza un dump CONVT_NO_NUMBER en el campo VBAK-NETWR. "
            "El pedido afectado es 4500012345."
        ),
        "comments_text": "",
        "status": "Open", "priority": "Critical", "issue_type": "Support",
        "must_anonymize": ["Pedro Martinez", "11111111H", "pmartinez@nttdata.com"],
        "must_not_anonymize": ["VA01", "SAPMV45A", "CONVT_NO_NUMBER", "VBAK-NETWR", "4500012345", "RITM9999999"],
    },
]


# ── Main test runner ─────────────────────────────────────────────────────────

def run_tests(verbose=False):
    detector = CompositeDetector()
    anonymizer = Anonymizer(detector=detector)

    total_pass = 0
    total_fail = 0
    total_warn = 0
    total_entities = 0
    all_fps = []

    # ═══ Part 1: Real tickets from STDVERT1 ═══
    print(c("\n" + "=" * 70, "b"))
    print(c("  PARTE 1: 20 tickets reales de STDVERT1 (falsos positivos)", "b"))
    print(c("=" * 70, "b"))

    print(c("\n  Descargando tickets de STDVERT1...", "d"))
    tickets = asyncio.run(fetch_board_tickets(20))
    print(c(f"  Descargados {len(tickets)} tickets\n", "d"))

    for ticket in tickets:
        result = evaluate_ticket(ticket, anonymizer, verbose)
        total_entities += result["entities"]
        key = result["key"]
        has_error = False

        if result["false_positives"]:
            has_error = True
            total_fail += len(result["false_positives"])
            print(c(f"  FAIL  {key}", "r") + c(f"  [{result['entities']} entidades]", "d"))
            for token, original, reason in result["false_positives"]:
                print(c(f"        x FP: {token} -> \"{original}\" ({reason})", "r"))
                all_fps.append((key, token, original, reason))

        if result["warnings"]:
            total_warn += len(result["warnings"])
            if not has_error:
                print(c(f"  WARN  {key}", "y") + c(f"  [{result['entities']} entidades]", "d"))
            for token, original, reason in result["warnings"]:
                print(c(f"        ? {token} -> \"{original}\" ({reason})", "y"))

        if not result["false_positives"] and not result["warnings"]:
            total_pass += 1
            if result["entities"] == 0:
                print(c(f"  OK    {key}", "g") + c(f"  [limpio, 0 entidades]", "d"))
            else:
                print(c(f"  OK    {key}", "g") + c(f"  [{result['entities']} entidades detectadas]", "d"))
                if verbose:
                    for token, original in result["sub_map"].items():
                        print(c(f"        {token} -> \"{original}\"", "d"))

        if verbose and result["anonymized"]:
            preview = result["anonymized"][:150].replace('\n', ' ')
            print(c(f"        Preview: {preview}...", "d"))

    # ═══ Part 2: Synthetic PII tickets (false negatives) ═══
    print(c("\n" + "=" * 70, "b"))
    print(c("  PARTE 2: Tickets sinteticos con PII (falsos negativos)", "b"))
    print(c("=" * 70 + "\n", "b"))

    for ticket in SYNTHETIC_TICKETS:
        full_text = f"{ticket['summary']}\n{ticket['description']}"
        anonymized, sub_map = anonymizer.anonymize(full_text)
        key = ticket["key"]
        has_error = False

        # Check must_anonymize
        fn_errors = []
        for term in ticket.get("must_anonymize", []):
            if term in anonymized:
                fn_errors.append(term)

        # Check must_not_anonymize
        fp_errors = []
        for term in ticket.get("must_not_anonymize", []):
            if term not in anonymized and term in full_text:
                replaced_by = None
                for token, original in sub_map.items():
                    if term in original or original in term:
                        replaced_by = token
                        break
                fp_errors.append((term, replaced_by))

        if fn_errors or fp_errors:
            has_error = True
            print(c(f"  FAIL  {key}", "r") + c(f"  [{len(sub_map)} entidades]", "d"))
            for term in fn_errors:
                print(c(f"        x FN: \"{term}\" no fue anonimizado!", "r"))
                total_fail += 1
            for term, token in fp_errors:
                print(c(f"        x FP: \"{term}\" fue anonimizado como {token}", "r"))
                total_fail += 1
        else:
            total_pass += 1
            print(c(f"  OK    {key}", "g") + c(f"  [{len(sub_map)} entidades detectadas]", "d"))

        if verbose or has_error:
            for token, original in sub_map.items():
                marker = "  " if not has_error else "  "
                print(c(f"        {token} -> \"{original}\"", "d"))

    # ═══ Summary ═══
    print(c("\n" + "=" * 70, "b"))
    total_tickets = len(tickets) + len(SYNTHETIC_TICKETS)
    print(c(f"  {total_tickets} tickets evaluados | {total_entities} entidades detectadas en reales", "B"))
    parts = [c(f"  {total_pass} passed", "g")]
    if total_fail:
        parts.append(c(f"  {total_fail} failed", "r"))
    if total_warn:
        parts.append(c(f"  {total_warn} warnings", "y"))
    print("  " + " | ".join(parts))

    if all_fps:
        print(c(f"\n  Resumen falsos positivos ({len(all_fps)}):", "r"))
        for key, token, original, reason in all_fps:
            print(c(f"    {key}: {token} -> \"{original}\"", "r"))

    print()
    return total_fail == 0


if __name__ == "__main__":
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    ok = run_tests(verbose)
    sys.exit(0 if ok else 1)
