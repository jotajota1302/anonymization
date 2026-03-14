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
            r'(?:\+34|0034)?\s?[6-9]\d{2}[\s.\-]?\d{3}[\s.\-]?\d{3}'
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
            r'\b(?:0[1-9]|[1-4]\d|5[0-2])\d{3}\b'
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

    def detect(self, text: str) -> List[PiiEntity]:
        """Detect PII entities using Presidio NLP analysis."""
        results = self._analyzer.analyze(
            text=text,
            language="es",
            score_threshold=0.4,
        )

        entities = []
        for result in results:
            entity_type = self.TYPE_MAP.get(result.entity_type, result.entity_type)
            entities.append(PiiEntity(
                text=text[result.start:result.end],
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
