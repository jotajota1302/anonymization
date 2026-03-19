"""LLM-based PII detection — finds all personal data the structured detectors miss."""

import json
import re
from typing import List

import structlog

from .anonymizer import PiiEntity

logger = structlog.get_logger()

# The LLM's job: find ALL person names regardless of what regex/presidio found.
# Structured data (DNI, email, phone) is already well covered by regex.
DETECTION_PROMPT = """Analiza este texto y extrae TODOS los nombres de persona que aparezcan.

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


async def llm_detect_pii(
    text: str,
    already_detected: List[PiiEntity],
    llm,
) -> List[PiiEntity]:
    """Use LLM to find person names that regex/presidio missed.

    The LLM finds ALL names. We then filter out what's already detected
    at the same position, keeping only genuinely new entities or
    reclassifying mistyped ones (e.g. ORGANIZACION -> PERSONA).
    """
    prompt = DETECTION_PROMPT.format(text=text[:6000])

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
    detected_persona_texts = {
        e.text for e in already_detected if e.entity_type == "PERSONA"
    }
    # Types that the LLM can reclassify as PERSONA (Presidio often confuses these)
    RECLASSIFIABLE_TYPES = {"ORGANIZACION", "UBICACION"}

    new_entities = []
    reclassified = []

    for item in items:
        if not isinstance(item, dict):
            continue
        entity_text = item.get("text", "").strip()
        if not entity_text or len(entity_text) < 2:
            continue

        # Skip if already detected as PERSONA with this exact text
        if entity_text in detected_persona_texts:
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
                    entity_type="PERSONA",
                    start=pos,
                    end=end,
                ))
            elif covering_entity.entity_type in RECLASSIFIABLE_TYPES:
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
        llm_found=len(items),
        new_entities=len(new_entities),
        reclassified=len(reclassified),
    )
    return new_entities + reclassified
