"""Tests for Anonymizer: detect_pii, anonymize, de_anonymize, filter_output, encrypt/decrypt."""

import pytest
from app.services.anonymizer import Anonymizer, PiiEntity


@pytest.fixture
def anonymizer():
    return Anonymizer()


class TestDetectPii:
    def test_detect_email(self, anonymizer):
        entities = anonymizer.detect_pii("Contactar a user@example.com para info")
        emails = [e for e in entities if e.entity_type == "EMAIL"]
        assert len(emails) == 1
        assert emails[0].text == "user@example.com"

    def test_detect_telefono(self, anonymizer):
        entities = anonymizer.detect_pii("Llamar al +34 612 345 678")
        telefonos = [e for e in entities if e.entity_type == "TELEFONO"]
        assert len(telefonos) == 1
        assert "612" in telefonos[0].text

    def test_detect_dni(self, anonymizer):
        entities = anonymizer.detect_pii("DNI del usuario: 12345678A")
        dnis = [e for e in entities if e.entity_type == "DNI"]
        assert len(dnis) == 1
        assert dnis[0].text == "12345678A"

    def test_detect_ip(self, anonymizer):
        entities = anonymizer.detect_pii("Servidor en 192.168.1.50")
        ips = [e for e in entities if e.entity_type == "IP"]
        assert len(ips) == 1
        assert ips[0].text == "192.168.1.50"

    def test_detect_iban(self, anonymizer):
        entities = anonymizer.detect_pii("Cuenta: ES7921000813610123456789")
        ibans = [e for e in entities if e.entity_type == "IBAN"]
        assert len(ibans) == 1
        assert ibans[0].text == "ES7921000813610123456789"

    def test_detect_persona(self, anonymizer):
        entities = anonymizer.detect_pii("El usuario Juan Garcia reporta un error")
        personas = [e for e in entities if e.entity_type == "PERSONA"]
        assert len(personas) == 1
        assert "Juan" in personas[0].text
        assert "Garcia" in personas[0].text

    def test_detect_multiple(self, anonymizer):
        text = "Juan Garcia (juan@test.com, DNI: 12345678A, IP: 10.0.0.1)"
        entities = anonymizer.detect_pii(text)
        types = {e.entity_type for e in entities}
        assert "PERSONA" in types
        assert "EMAIL" in types
        assert "DNI" in types
        assert "IP" in types


class TestAnonymize:
    def test_anonymize_replaces_pii(self, anonymizer):
        text = "Juan Garcia tiene email juan@test.com"
        anon_text, sub_map = anonymizer.anonymize(text)

        assert "Juan" not in anon_text
        assert "juan@test.com" not in anon_text
        assert "[PERSONA_1]" in anon_text
        assert "[EMAIL_1]" in anon_text
        assert len(sub_map) >= 2

    def test_anonymize_no_pii(self, anonymizer):
        text = "El servidor tiene un error de configuracion"
        anon_text, sub_map = anonymizer.anonymize(text)
        assert anon_text == text
        assert sub_map == {}

    def test_anonymize_reuses_tokens(self, anonymizer):
        text = "Juan Garcia dice algo. Juan Garcia repite."
        anon_text, sub_map = anonymizer.anonymize(text)
        # Same person should get same token
        assert anon_text.count("[PERSONA_1]") == 2


class TestDeAnonymize:
    def test_de_anonymize_basic(self):
        sub_map = {"[PERSONA_1]": "Juan Garcia", "[EMAIL_1]": "juan@test.com"}
        text = "El usuario [PERSONA_1] con email [EMAIL_1]"
        result = Anonymizer.de_anonymize(text, sub_map)
        assert result == "El usuario Juan Garcia con email juan@test.com"

    def test_de_anonymize_empty_map(self):
        text = "Sin tokens aqui"
        result = Anonymizer.de_anonymize(text, {})
        assert result == text


class TestFilterOutput:
    def test_filter_known_pii(self, anonymizer):
        sub_map = {"[PERSONA_1]": "Juan Garcia"}
        text = "El usuario Juan Garcia tiene un problema"
        filtered = anonymizer.filter_output(text, sub_map)
        assert "Juan Garcia" not in filtered
        assert "[PERSONA_1]" in filtered

    def test_filter_empty_map(self, anonymizer):
        text = "Sin PII aqui"
        filtered = anonymizer.filter_output(text, {})
        assert filtered == text


class TestEncryptDecrypt:
    def test_roundtrip(self):
        key = Anonymizer.generate_key()
        original = {"[PERSONA_1]": "Juan Garcia", "[EMAIL_1]": "juan@test.com"}
        encrypted = Anonymizer.encrypt_map(original, key)
        decrypted = Anonymizer.decrypt_map(encrypted, key)
        assert decrypted == original

    def test_different_keys_fail(self):
        key1 = Anonymizer.generate_key()
        key2 = Anonymizer.generate_key()
        original = {"[PERSONA_1]": "Test"}
        encrypted = Anonymizer.encrypt_map(original, key1)
        with pytest.raises(Exception):
            Anonymizer.decrypt_map(encrypted, key2)

    def test_key_from_string(self):
        import base64
        key = Anonymizer.generate_key()
        key_str = base64.b64encode(key).decode()
        restored = Anonymizer.key_from_string(key_str)
        assert restored == key
