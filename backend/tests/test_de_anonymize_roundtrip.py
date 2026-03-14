"""Integration test: anonymize -> encrypt -> decrypt -> de_anonymize roundtrip."""

import pytest
from app.services.anonymizer import Anonymizer


REALISTIC_TICKET = (
    "El usuario Juan Garcia (juan.garcia@acme.com, tel: +34 612 345 678, "
    "DNI: 12345678A) reporta que el servidor servidor-prod-042 (IP: 192.168.1.50) "
    "no responde desde las 09:00 del dia de hoy. El servicio de base de datos "
    "PostgreSQL en el puerto 5432 parece estar caido. La cuenta bancaria para "
    "facturacion es ES7921000813610123456789. "
    "Ubicacion del centro de datos: Madrid, Calle Gran Via 28."
)


class TestRoundtrip:
    def test_full_roundtrip(self):
        anonymizer = Anonymizer()
        key = Anonymizer.generate_key()

        # 1. Anonymize
        anon_text, sub_map = anonymizer.anonymize(REALISTIC_TICKET)

        # Verify PII removed
        assert "Juan Garcia" not in anon_text
        assert "juan.garcia@acme.com" not in anon_text
        assert "12345678A" not in anon_text
        assert "192.168.1.50" not in anon_text
        assert "ES7921000813610123456789" not in anon_text

        # Verify tokens present
        assert "[PERSONA_1]" in anon_text
        assert "[EMAIL_1]" in anon_text

        # 2. Encrypt
        encrypted = Anonymizer.encrypt_map(sub_map, key)
        assert isinstance(encrypted, bytes)
        assert len(encrypted) > 12  # nonce + ciphertext

        # 3. Decrypt
        decrypted_map = Anonymizer.decrypt_map(encrypted, key)
        assert decrypted_map == sub_map

        # 4. De-anonymize
        restored = Anonymizer.de_anonymize(anon_text, decrypted_map)
        assert "Juan Garcia" in restored
        assert "juan.garcia@acme.com" in restored
        assert "12345678A" in restored
        assert "192.168.1.50" in restored
        assert "ES7921000813610123456789" in restored

    def test_roundtrip_preserves_technical_content(self):
        anonymizer = Anonymizer()
        key = Anonymizer.generate_key()

        anon_text, sub_map = anonymizer.anonymize(REALISTIC_TICKET)
        encrypted = Anonymizer.encrypt_map(sub_map, key)
        decrypted_map = Anonymizer.decrypt_map(encrypted, key)
        restored = Anonymizer.de_anonymize(anon_text, decrypted_map)

        # Technical content preserved through the roundtrip
        assert "servidor-prod-042" in restored
        assert "PostgreSQL" in restored
        assert "5432" in restored

    def test_roundtrip_no_pii(self):
        anonymizer = Anonymizer()
        key = Anonymizer.generate_key()

        text = "El servidor tiene un error de configuracion en el puerto 8080"
        anon_text, sub_map = anonymizer.anonymize(text)
        assert anon_text == text
        assert sub_map == {}

        # With empty map, de_anonymize is a no-op
        restored = Anonymizer.de_anonymize(anon_text, sub_map)
        assert restored == text

    def test_filter_then_de_anonymize(self):
        anonymizer = Anonymizer()

        _, sub_map = anonymizer.anonymize(REALISTIC_TICKET)

        # Simulate LLM leaking PII
        llm_response = "El usuario Juan Garcia tiene un problema con 192.168.1.50"
        filtered = anonymizer.filter_output(llm_response, sub_map)

        # PII should be replaced with tokens
        assert "Juan Garcia" not in filtered
        assert "192.168.1.50" not in filtered

        # De-anonymize the filtered response to get back real data
        restored = Anonymizer.de_anonymize(filtered, sub_map)
        assert "Juan Garcia" in restored
        assert "192.168.1.50" in restored
