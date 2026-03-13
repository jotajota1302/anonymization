"""PII detection and anonymization service with RegexDetector."""

import re
import json
import base64
import os
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
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
    """PII detection and anonymization using regex patterns."""

    # Regex patterns for PII detection
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

    # Pattern for potential proper names (capitalized words)
    NAME_PATTERN = re.compile(r'\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,}\b')

    def detect_pii(self, text: str) -> List[PiiEntity]:
        """Detect PII entities in text using regex patterns."""
        entities = []

        # Detect regex-based PII
        for entity_type, pattern in self.PATTERNS.items():
            for match in pattern.finditer(text):
                entities.append(PiiEntity(
                    text=match.group(),
                    entity_type=entity_type,
                    start=match.start(),
                    end=match.end(),
                ))

        # Detect potential names (heuristic: capitalized words matching name dictionary)
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

        # Merge consecutive name parts (e.g., "Juan Garcia" -> single PERSONA)
        entities.extend(self._merge_name_candidates(name_candidates, text))

        # Sort by position and remove overlaps
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

            # Look ahead for consecutive name parts separated by spaces
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

    # --- Encryption for substitution map persistence ---

    @staticmethod
    def generate_key() -> bytes:
        """Generate a new AES-256-GCM key."""
        return AESGCM.generate_key(bit_length=256)

    @staticmethod
    def encrypt_map(substitution_map: Dict[str, str], key: bytes) -> bytes:
        """Encrypt substitution map with AES-256-GCM."""
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        plaintext = json.dumps(substitution_map).encode("utf-8")
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        return nonce + ciphertext  # prepend nonce for decryption

    @staticmethod
    def decrypt_map(encrypted_data: bytes, key: bytes) -> Dict[str, str]:
        """Decrypt substitution map from AES-256-GCM."""
        aesgcm = AESGCM(key)
        nonce = encrypted_data[:12]
        ciphertext = encrypted_data[12:]
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return json.loads(plaintext.decode("utf-8"))

    @staticmethod
    def key_from_string(key_str: str) -> bytes:
        """Convert base64-encoded key string to bytes."""
        if not key_str:
            # Generate and log a warning for development
            logger.warning("no_encryption_key_set, generating ephemeral key")
            return Anonymizer.generate_key()
        return base64.b64decode(key_str)
