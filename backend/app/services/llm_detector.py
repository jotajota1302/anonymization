"""LLM-based PII detection — finds personal data the structured detectors miss.

When regex/Presidio are disabled, this becomes the PRIMARY detector and must
find ALL types of PII (names, emails, phones, IDs, addresses, etc.).
When regex/Presidio are active, it focuses on names (their weak spot).
"""

import json
import re
from typing import List

import structlog

from .anonymizer import PiiEntity

logger = structlog.get_logger()

# Prompt when regex/Presidio ARE active — focus on names (their weak spot)
DETECTION_PROMPT_NAMES_ONLY = """Analiza este texto y extrae TODOS los nombres de persona que aparezcan.

## Texto:
---
{text}
---

## Reglas:
1. Extrae cada nombre COMPLETO tal como aparece en el texto (respeta mayusculas/minusculas exactas).
2. Incluye nombres en cualquier formato: "APELLIDO APELLIDO, NOMBRE", "Nombre Apellido", "NOMBRE COMPLETO", nombres sueltos, etc.
3. Si hay un formato "APELLIDO(S), NOMBRE(S)", devuelve la cadena completa incluyendo la coma (ej: "MENOYO GONZALEZ, FRANCISCA").
4. Tambien extrae nombres sueltos (ej: "FRANCISCA", "David", "Ana Maria") que sean claramente nombres de persona.
5. NO incluyas cabeceras, etiquetas o texto generico (ej: "Número de personal", "N.I.F." no son nombres).
6. NO incluyas codigos, numeros de identificacion ni datos tecnicos.

## Contexto importante — apellidos vs organizaciones:
- En datos de RRHH/nominas, las entradas junto a NIF/DNI y numeros de personal son SIEMPRE nombres de persona, nunca organizaciones.
- Apellidos espanoles como "MORENO GRASA", "MONTORO MECERREYES", "TORRECILLA MARTINEZ" son nombres de persona, NO organizaciones ni ubicaciones.
- Si ves un patron tabular con NIF + numero + "APELLIDO(S), NOMBRE(S)", TODO el nombre es una persona.
- "ANDRES" como apellido (ej: "ANDRES CARDOSO, ELENA") es parte del nombre completo de una persona.

## Formato de respuesta — SOLO un JSON array:
[
  {{"text": "TEXTO_EXACTO", "entity_type": "PERSONA"}},
  ...
]

Si no hay nombres, responde: []
Responde SOLO el JSON."""


# Prompt when regex/Presidio are DISABLED — LLM must detect ALL PII types
DETECTION_PROMPT_FULL = """Eres el detector principal de datos personales (PII) de una plataforma GDPR.
Los detectores automaticos (regex y Presidio NLP) estan DESACTIVADOS. Tu eres la UNICA barrera
de proteccion. Debes encontrar TODOS los datos personales en el texto.

## Texto a analizar:
---
{text}
---

## Tipos de PII que DEBES detectar:

| Tipo | Ejemplos |
|------|----------|
| PERSONA | Nombres propios: "Juan Garcia", "LOPEZ MARTINEZ, ANA", "Sr. Perez", nombres sueltos como "Francisca" |
| EMAIL | Correos: "usuario@empresa.com", "juan.garcia [at] gmail.com" |
| TELEFONO | Telefonos: "+34 612 345 678", "912-345-678", "ext. 4521" |
| DNI | Documentos: "12345678Z", "X-1234567-W", "NIF: B12345678", "NIE: Y0123456H" |
| IBAN | Cuentas bancarias: "ES76 2100 0813 6101 2345 6789" |
| DIRECCION | Direcciones postales: "Calle Mayor 15, 3o B", "Avda. Constitucion s/n", "28001 Madrid" |
| UBICACION | Ciudades/pueblos mencionados como datos personales (NO como contexto tecnico): "vive en Sevilla", "oficina de Barcelona" |
| ORGANIZACION | Empresas/entidades vinculadas a personas: "trabaja en Telefonica", "cliente de BBVA" |
| TARJETA_CREDITO | Numeros de tarjeta: "4111 1111 1111 1111" |
| MATRICULA | Matriculas de vehiculos: "1234 BCD" |
## Reglas criticas:
1. Extrae el texto EXACTO como aparece (respeta mayusculas/minusculas).
2. Ante la duda, MARCA como PII. Un falso positivo es preferible a filtrar un dato real.
3. Los nombres en formatos tabulares (junto a NIF, numeros de personal) son SIEMPRE personas.

## QUE NO ES PII (no marcar):
- Tokens ya anonimizados: `[PERSONA_1]`, `[EMAIL_3]`, etc.
- Nombres de servidores, servicios, aplicaciones: `auth-server-01`, `PostgreSQL`, `SAP`
- IPs de redes internas: `10.x.x.x`, `192.168.x.x`
- Codigos de error: `ERR_CONNECTION_REFUSED`, `HTTP 500`, `ORA-12541`
- Nombres de productos, frameworks o tecnologias
- Fechas y timestamps (a menos que sean fecha de nacimiento)
- Etiquetas de campos: "Nombre:", "Email:", "Telefono:" (son etiquetas, no datos)
- Terminos tecnicos: SE38, SE80, Solution Manager, SharePoint, ALM
- Frases genericas de procedimiento: "lineas de actuacion", "verificar estado"

## Formato de respuesta — SOLO un JSON array:
[
  {{"text": "TEXTO_EXACTO", "entity_type": "TIPO"}},
  ...
]

Si no hay PII, responde: []
Responde SOLO el JSON."""


# Valid entity types the LLM can return
VALID_ENTITY_TYPES = {
    "PERSONA", "EMAIL", "TELEFONO", "DNI", "IP", "IBAN",
    "DIRECCION", "UBICACION", "ORGANIZACION", "TARJETA_CREDITO",
    "MATRICULA", "DATO",
}


async def llm_detect_pii(
    text: str,
    already_detected: List[PiiEntity],
    llm,
    ner_active: bool = False,
) -> List[PiiEntity]:
    """Use LLM to find PII that regex/presidio missed.

    Args:
        text: Full text to analyze.
        already_detected: Entities already found by regex/Presidio.
        llm: LangChain LLM instance.
        ner_active: True ONLY when Presidio NER is running (detects names,
            orgs, locations). When False the LLM must detect ALL PII types.
            Regex alone does NOT count — it only handles structured patterns
            (emails, DNIs, phones, etc.) and cannot detect names/orgs/locations.
    """
    if ner_active and len(already_detected) > 0:
        # Presidio NER is running and found things — focus on names it missed
        prompt_template = DETECTION_PROMPT_NAMES_ONLY
    else:
        # No NER or nothing detected yet — LLM is the primary/full detector
        prompt_template = DETECTION_PROMPT_FULL
        logger.info(
            "llm_detector_full_mode",
            reason="no_ner" if not ner_active else "no_prior_detections",
            text_length=len(text),
        )

    prompt = prompt_template.format(text=text[:6000])

    try:
        from langchain_core.messages import HumanMessage
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        raw = response.content.strip()

        json_match = re.search(r'\[.*\]', raw, re.DOTALL)
        if not json_match:
            logger.info("llm_detector_no_json", raw_preview=raw[:200])
            return []

        items = json.loads(json_match.group())
        if not isinstance(items, list):
            return []

    except Exception as e:
        logger.error("llm_detector_error", error=str(e))
        return []

    # Build index of already-detected spans for overlap/reclassification check
    detected_spans = {(e.start, e.end, e.text): e for e in already_detected}
    detected_texts_by_type = {}
    for e in already_detected:
        detected_texts_by_type.setdefault(e.entity_type, set()).add(e.text)

    # Types that the LLM can reclassify as PERSONA (Presidio often confuses these)
    RECLASSIFIABLE_TYPES = {"ORGANIZACION", "UBICACION"}

    new_entities = []
    reclassified = []

    for item in items:
        if not isinstance(item, dict):
            continue
        entity_text = item.get("text", "").strip()
        entity_type = item.get("entity_type", "PERSONA").upper().strip()

        if not entity_text or len(entity_text) < 2:
            continue

        # Normalize entity type
        if entity_type not in VALID_ENTITY_TYPES:
            entity_type = "DATO"

        # Skip if already detected with same type and text
        if entity_text in detected_texts_by_type.get(entity_type, set()):
            continue

        # Find all occurrences in original text
        start = 0
        while True:
            pos = text.find(entity_text, start)
            if pos == -1:
                break

            end = pos + len(entity_text)

            # Check if this span overlaps with an already-detected entity
            covering_entity = None
            for (s, e, _), ent in detected_spans.items():
                if s <= pos and e >= end:
                    covering_entity = ent
                    break

            if covering_entity is None:
                # New entity not covered by any detector
                new_entities.append(PiiEntity(
                    text=entity_text,
                    entity_type=entity_type,
                    start=pos,
                    end=end,
                ))
            elif (
                entity_type == "PERSONA"
                and covering_entity.entity_type in RECLASSIFIABLE_TYPES
            ):
                # Presidio misclassified this as ORG/LOCATION — reclassify to PERSONA
                reclassified.append(PiiEntity(
                    text=covering_entity.text,
                    entity_type="PERSONA",
                    start=covering_entity.start,
                    end=covering_entity.end,
                ))

            start = end

    if reclassified:
        logger.info(
            "llm_detector_reclassified",
            count=len(reclassified),
            examples=[f"{e.text} ({e.entity_type})" for e in reclassified[:5]],
        )

    logger.info(
        "llm_detector_done",
        mode="full" if not ner_active or not already_detected else "names_only",
        llm_found=len(items),
        new_entities=len(new_entities),
        reclassified=len(reclassified),
    )
    return new_entities + reclassified
