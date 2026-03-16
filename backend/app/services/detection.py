"""Abstract detection service and regex-based implementation."""

import re
from abc import ABC, abstractmethod
from typing import List

from .anonymizer import PiiEntity, SPANISH_NAMES


class DetectionService(ABC):
    """Abstract interface for PII detection."""

    @abstractmethod
    def detect(self, text: str) -> List[PiiEntity]:
        """Detect PII entities in text."""
        ...


class RegexDetector(DetectionService):
    """PII detection using regex patterns and Spanish name heuristics."""

    PATTERNS = {
        "EMAIL": re.compile(r'[\w.\-+]+@[\w.\-]+\.\w{2,}', re.IGNORECASE),
        "TELEFONO": re.compile(
            r'(?<!\d)(?:\+34|0034)?\s?[6-9]\d{2}[\s.\-]?\d{3}[\s.\-]?\d{3}(?!\d)'
        ),
        "DNI": re.compile(r'\b[0-9XYZxyz]\d{7}[A-Za-z]\b'),
        "IP": re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'),
        "IPV6": re.compile(
            r'(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}'
            r'|(?:[0-9a-fA-F]{1,4}:){1,7}:'
            r'|(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}'
            r'|::(?:[0-9a-fA-F]{1,4}:){0,5}[0-9a-fA-F]{1,4}'
            r'|::',
        ),
        "IBAN": re.compile(
            r'\bES\d{2}[\s]?\d{4}[\s]?\d{4}[\s]?\d{2}[\s]?\d{10}\b',
            re.IGNORECASE
        ),
        "DIRECCION": re.compile(
            r'\b(?:Calle|C/|Avenida|Avda\.?|Av\.?|Plaza|Pl\.?|Paseo|Ronda|Camino|Travesía|Carretera|Ctra\.?)'
            r'\s+[A-ZÁÉÍÓÚÑa-záéíóúñ\s]+\s*,?\s*\d{1,4}',
            re.IGNORECASE
        ),
        "CODIGO_POSTAL": re.compile(
            r'(?:C\.?P\.?|[Cc]ódigo\s*[Pp]ostal|[Cc]odigo\s*[Pp]ostal)\s*:?\s*(?<!\d)((?:0[1-9]|[1-4]\d|5[0-2])\d{3})(?!\d)'
        ),
        "MATRICULA": re.compile(
            r'\b\d{4}[\s\-]?[B-DF-HJ-NP-TV-Z]{3}\b',
            re.IGNORECASE
        ),
    }

    NAME_PATTERN = re.compile(r'\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,}\b')

    def detect(self, text: str) -> List[PiiEntity]:
        """Detect PII entities in text using regex patterns."""
        entities = []

        for entity_type, pattern in self.PATTERNS.items():
            for match in pattern.finditer(text):
                entities.append(PiiEntity(
                    text=match.group(),
                    entity_type=entity_type,
                    start=match.start(),
                    end=match.end(),
                ))

        name_candidates = []
        for match in self.NAME_PATTERN.finditer(text):
            word = match.group()
            if word.lower() in SPANISH_NAMES:
                name_candidates.append(PiiEntity(
                    text=word,
                    entity_type="PERSONA",
                    start=match.start(),
                    end=match.end(),
                ))

        entities.extend(self._merge_name_candidates(name_candidates, text))

        entities.sort(key=lambda e: e.start)
        entities = self._remove_overlaps(entities)

        return entities

    def _merge_name_candidates(
        self, candidates: List[PiiEntity], text: str
    ) -> List[PiiEntity]:
        """Merge consecutive name candidates into full names."""
        if not candidates:
            return []

        merged = []
        i = 0
        while i < len(candidates):
            current = candidates[i]
            full_name = current.text
            end = current.end

            j = i + 1
            while j < len(candidates):
                between = text[end:candidates[j].start]
                if between.strip() == "" and len(between) <= 2:
                    full_name += between + candidates[j].text
                    end = candidates[j].end
                    j += 1
                else:
                    break

            merged.append(PiiEntity(
                text=full_name,
                entity_type="PERSONA",
                start=current.start,
                end=end,
            ))
            i = j

        return merged

    def _remove_overlaps(self, entities: List[PiiEntity]) -> List[PiiEntity]:
        """Remove overlapping entities, keeping the longer one."""
        if not entities:
            return []

        result = [entities[0]]
        for entity in entities[1:]:
            if entity.start >= result[-1].end:
                result.append(entity)
            elif len(entity.text) > len(result[-1].text):
                result[-1] = entity
        return result


class PresidioDetector(DetectionService):
    """PII detection using Microsoft Presidio with spaCy NER for Spanish."""

    # Map Presidio entity types → our internal types
    TYPE_MAP = {
        "PERSON": "PERSONA",
        "LOCATION": "UBICACION",
        "ORGANIZATION": "ORGANIZACION",
        "EMAIL_ADDRESS": "EMAIL",
        "PHONE_NUMBER": "TELEFONO",
        "IBAN_CODE": "IBAN",
        "IP_ADDRESS": "IP",
        "NRP": "DNI",  # National Registration/ID
        "CREDIT_CARD": "TARJETA_CREDITO",
        "DATE_TIME": "FECHA",
        "URL": "URL",
    }

    # Minimum text length per entity type to reduce false positives
    MIN_LENGTH = {
        "PERSONA": 4,
        "UBICACION": 5,
        "ORGANIZACION": 4,
    }

    # Patterns that look like technical codes, not PII
    _TECHNICAL_CODE = re.compile(
        r'^[A-Z]{1,5}[-_]?\d{1,5}$'      # MOD_09, PT03, ERR01, V2, etc.
        r'|^\d+\.\d+$'                     # 21.9, 3.14
        r'|^[A-Z]{1,3}\d{2,5}$'           # PT03, AB123
        r'|^[A-Z_]{2,10}$'                # XML, JSON, SI, NO, etc.
        r'|^RITM\d+$'                      # ServiceNow/ITSM ticket refs
        r'|^[A-Z]{2,10}\d{5,}$'           # RITM1406827, INC000001, etc.
    )

    # Common Spanish words that Presidio may misclassify as entities
    _FALSE_POSITIVE_WORDS = {
        # Determiners, prepositions, common words
        "no", "si", "es", "al", "el", "la", "los", "las", "un", "una",
        "del", "por", "para", "con", "sin", "que", "como", "bien", "mal",
        "año", "mes", "dia", "hoy", "ayer", "todo", "nada", "algo",
        # Generic field/form labels (not actual PII data)
        "nombre", "dirección", "direccion", "domicilio", "apellido", "apellidos",
        "teléfono", "telefono", "email", "correo", "fecha", "estado", "tipo",
        "campo", "código", "codigo", "centro", "servicio", "servicios",
        "empresa", "entidad", "cuenta", "número", "numero", "registro",
        "cliente", "usuario", "operador", "sistema", "proceso", "modelo",
        "descripción", "descripcion", "comentario", "observaciones", "nota",
        # Common business/technical terms often misclassified
        "gestión", "gestion", "actualizaciones", "actualizacion", "configuración",
        "configuracion", "modificación", "modificacion", "retroactividad",
        "factura", "facturación", "pedido", "sociedad", "convenio",
        "extra", "marzo", "enero", "febrero", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
        "navidad", "paga", "pagas", "importe", "tabla", "tablas",
        # Common Spanish verbs Presidio misclassifies
        "llamó", "llamo", "indicó", "indico", "solicitó", "solicito",
        "reportó", "reporto", "ejecutó", "ejecuto", "configuró", "configuro",
        # Tech terms
        "xml", "json", "html", "sql", "api", "url", "http", "https",
        "sap", "sii", "basis", "abap", "fiori",
    }

    # Regex for generic field references like "Nombre(Dirección)", "Nombre 1"
    _FIELD_LABEL_PATTERN = re.compile(
        r'^(?:Nombre|Dirección|Direccion|Campo|Tipo|Estado|Código|Codigo)'
        r'(?:\s*\d+|\s*\(.*\))?$',
        re.IGNORECASE
    )

    def __init__(self, model_name: str = "es_core_news_lg"):
        from presidio_analyzer import AnalyzerEngine
        from presidio_analyzer.nlp_engine import SpacyNlpEngine

        nlp_engine = SpacyNlpEngine(
            models=[{"lang_code": "es", "model_name": model_name}],
        )
        self._analyzer = AnalyzerEngine(
            nlp_engine=nlp_engine,
            supported_languages=["es"],
        )
        self._model_name = model_name

    def _is_false_positive(self, entity_text: str, entity_type: str) -> bool:
        """Filter out obvious false positives from Presidio NER."""
        stripped = entity_text.strip()
        text_lower = stripped.lower()

        # Common words that are never PII (check each word in the entity)
        words = re.split(r'[\s()\[\],;:\-/]+', text_lower)
        if all(w in self._FALSE_POSITIVE_WORDS or not w for w in words):
            return True

        # Field label patterns: "Nombre(Dirección)", "Nombre 1", etc.
        if self._FIELD_LABEL_PATTERN.match(stripped):
            return True

        # Technical codes (MOD_09, PT03, ERR01, etc.) — match whole string or substring
        if self._TECHNICAL_CODE.match(stripped):
            return True
        # Also check if entity contains a technical code (long phrases from Presidio)
        if self._TECHNICAL_CODE.search(stripped):
            return True

        # Long phrases (>40 chars) from Presidio NER are almost always wrong
        if entity_type in ("ORGANIZACION", "UBICACION", "PERSONA") and len(stripped) > 40:
            return True

        # Too short for NER-based types (PERSONA, UBICACION, ORGANIZACION)
        min_len = self.MIN_LENGTH.get(entity_type, 0)
        if min_len and len(stripped) < min_len:
            return True

        return False

    def detect(self, text: str) -> List[PiiEntity]:
        """Detect PII entities using Presidio NLP analysis."""
        results = self._analyzer.analyze(
            text=text,
            language="es",
            score_threshold=0.65,
        )

        entities = []
        for result in results:
            entity_type = self.TYPE_MAP.get(result.entity_type, result.entity_type)
            entity_text = text[result.start:result.end]

            if self._is_false_positive(entity_text, entity_type):
                continue

            entities.append(PiiEntity(
                text=entity_text,
                entity_type=entity_type,
                start=result.start,
                end=result.end,
            ))

        entities.sort(key=lambda e: e.start)
        return entities


class CompositeDetector(DetectionService):
    """Combines multiple detectors, deduplicating overlapping results.

    Default: PresidioDetector (NLP) + RegexDetector (structured patterns).
    Prefers longer entities when overlaps occur.
    """

    def __init__(self, detectors: List[DetectionService] = None):
        if detectors is not None:
            self._detectors = detectors
        else:
            # Default: try Presidio + Regex, fallback to Regex only
            try:
                self._detectors = [PresidioDetector(), RegexDetector()]
            except Exception:
                import structlog
                structlog.get_logger().warning(
                    "presidio_not_available",
                    hint="Install presidio-analyzer and spacy es_core_news_lg for NLP detection"
                )
                self._detectors = [RegexDetector()]

    def detect(self, text: str) -> List[PiiEntity]:
        """Run all detectors and merge results, preferring longer entities."""
        all_entities = []
        for detector in self._detectors:
            all_entities.extend(detector.detect(text))

        if not all_entities:
            return []

        # Sort by start position, then by length (longer first)
        all_entities.sort(key=lambda e: (e.start, -(e.end - e.start)))

        # Deduplicate overlaps: keep the longer entity
        merged = [all_entities[0]]
        for entity in all_entities[1:]:
            last = merged[-1]
            if entity.start >= last.end:
                # No overlap
                merged.append(entity)
            elif (entity.end - entity.start) > (last.end - last.start):
                # Current entity is longer, replace
                merged[-1] = entity
            # else: skip shorter overlapping entity

        return merged


class AttachmentDetector(DetectionService):
    """Delegates to RegexDetector for text already extracted from attachments."""

    def __init__(self):
        self._regex = RegexDetector()

    def detect(self, text: str) -> List[PiiEntity]:
        return self._regex.detect(text)
