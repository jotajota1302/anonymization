"""PII detection and anonymization service with pluggable DetectionService."""

import hashlib
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

import structlog

logger = structlog.get_logger()


@dataclass
class PiiEntity:
    """Represents a detected PII entity."""
    text: str
    entity_type: str  # PERSONA, EMAIL, TELEFONO, DNI, IP, IBAN, UBICACION, SISTEMA
    start: int
    end: int


# Common Spanish first names for heuristic name detection
SPANISH_NAMES = {
    "juan", "maria", "jose", "ana", "carlos", "laura", "antonio", "carmen",
    "francisco", "isabel", "pedro", "lucia", "miguel", "elena", "javier",
    "marta", "rafael", "rosa", "fernando", "pilar", "david", "teresa",
    "alejandro", "cristina", "jorge", "patricia", "alberto", "beatriz",
    "daniel", "andrea", "pablo", "sandra", "sergio", "raquel", "manuel",
    "monica", "ramon", "sara", "luis", "paula", "angel", "silvia",
    "gonzalez", "garcia", "martinez", "lopez", "hernandez", "rodriguez",
    "fernandez", "sanchez", "perez", "martin", "gomez", "ruiz", "diaz",
    "moreno", "alvarez", "romero", "torres", "navarro", "dominguez", "vazquez",
}


class Anonymizer:
    """PII detection and anonymization with pluggable DetectionService."""

    def __init__(self, detector=None):
        if detector is None:
            from .detection import RegexDetector
            detector = RegexDetector()
        self._detector = detector

    def detect_pii(self, text: str) -> List[PiiEntity]:
        """Detect PII entities in text using the configured DetectionService."""
        return self._detector.detect(text)

    def anonymize(self, text: str) -> Tuple[str, Dict[str, str]]:
        """
        Anonymize text by replacing PII with tokens.

        Returns:
            Tuple of (anonymized_text, substitution_map)
            where substitution_map maps token -> original_value
        """
        entities = self.detect_pii(text)

        if not entities:
            return text, {}

        # Count per entity type for incremental tokens
        type_counters: Dict[str, int] = {}
        # Map original values to tokens (to reuse tokens for same value)
        value_to_token: Dict[str, str] = {}
        substitution_map: Dict[str, str] = {}

        # Process entities from end to start to preserve positions
        anonymized = text
        for entity in reversed(entities):
            if entity.text in value_to_token:
                token = value_to_token[entity.text]
            else:
                type_counters[entity.entity_type] = type_counters.get(entity.entity_type, 0) + 1
                token = f"[{entity.entity_type}_{type_counters[entity.entity_type]}]"
                value_to_token[entity.text] = token
                substitution_map[token] = entity.text

            anonymized = anonymized[:entity.start] + token + anonymized[entity.end:]

        logger.info(
            "text_anonymized",
            entities_found=len(entities),
            types={k: v for k, v in type_counters.items()},
        )

        return anonymized, substitution_map

    def filter_output(self, text: str, substitution_map: Dict[str, str]) -> str:
        """
        Post-LLM filter: scan response for any leaked PII values
        and replace them with their corresponding tokens.
        """
        if not substitution_map:
            return text

        filtered = text
        for token, original_value in substitution_map.items():
            if original_value in filtered:
                filtered = filtered.replace(original_value, token)
                logger.warning(
                    "pii_leak_filtered",
                    token=token,
                    entity_type=token.split("_")[0].strip("["),
                )

        # Also run regex detection on the output as extra safety
        entities = self.detect_pii(filtered)
        for entity in reversed(entities):
            # Check if this is a known value
            known = False
            for token, val in substitution_map.items():
                if entity.text == val:
                    filtered = filtered[:entity.start] + token + filtered[entity.end:]
                    known = True
                    break
            if not known:
                # Unknown PII in output - replace with generic token
                replacement = f"[{entity.entity_type}_REDACTED]"
                filtered = filtered[:entity.start] + replacement + filtered[entity.end:]
                logger.warning("unknown_pii_in_output", entity_type=entity.entity_type)

        return filtered

    def detect_breakdown(self, text: str) -> Dict[str, Optional[int]]:
        """Run detection returning per-detector entity counts.

        Returns dict with keys 'regex', 'presidio', 'total'.
        Value is None when a detector is not available.
        """
        from .detection import CompositeDetector, RegexDetector, PresidioDetector

        result: Dict[str, Optional[int]] = {"regex": None, "presidio": None, "total": 0}

        if isinstance(self._detector, CompositeDetector):
            for det in self._detector._detectors:
                if isinstance(det, RegexDetector):
                    result["regex"] = len(det.detect(text))
                elif isinstance(det, PresidioDetector):
                    result["presidio"] = len(det.detect(text))
        elif isinstance(self._detector, RegexDetector):
            result["regex"] = len(self._detector.detect(text))

        all_entities = self._detector.detect(text)
        result["total"] = len(all_entities)
        return result

    @staticmethod
    def de_anonymize(text: str, substitution_map: Dict[str, str]) -> str:
        """Reemplaza tokens de anonimización por sus valores reales originales."""
        result = text
        for token, real_value in substitution_map.items():
            result = result.replace(token, real_value)
        return result

    def reconstruct_map(self, original_text: str) -> Dict[str, str]:
        """Reconstruct substitution map by re-anonymizing the original text.

        The anonymize() method is deterministic: same input → same entities
        in same order → same tokens. This allows reconstruction without
        persisting the map.
        """
        _, sub_map = self.anonymize(original_text)
        return sub_map

    @staticmethod
    def compute_text_hash(text: str) -> str:
        """Compute SHA-256 hash of text for change detection."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def assemble_ingest_text(
        summary: str, description: str, comments: List[Dict]
    ) -> str:
        """Assemble the full text exactly as done during ingest.

        This MUST match the assembly in ingest_confirm() to guarantee
        deterministic reconstruction of the substitution map.
        """
        comments_text = ""
        if comments:
            comments_text = "\n\n--- COMENTARIOS ---\n" + "\n---\n".join(
                f"{c.get('author', 'Unknown')}: {c.get('body', '')}" for c in comments
            )
        return f"{summary}\n{description}{comments_text}"
