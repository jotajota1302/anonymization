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
        "IBAN": re.compile(
            r'\bES\d{2}[\s]?\d{4}[\s]?\d{4}[\s]?\d{2}[\s]?\d{10}\b',
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


class AttachmentDetector(DetectionService):
    """Delegates to RegexDetector for text already extracted from attachments."""

    def __init__(self):
        self._regex = RegexDetector()

    def detect(self, text: str) -> List[PiiEntity]:
        return self._regex.detect(text)
