"""Tests for AttachmentProcessor: routing by extension, fallback, mocks."""

import pytest
from unittest.mock import patch, MagicMock
from app.services.attachment_processor import AttachmentProcessor


@pytest.fixture
def processor():
    return AttachmentProcessor()


class TestRouting:
    def test_plaintext_fallback(self, processor):
        content = "Texto simple sin formato especial".encode("utf-8")
        text, fmt = processor.extract_text(content, "readme.txt")
        assert fmt == "plaintext"
        assert "Texto simple" in text

    def test_unknown_extension_falls_to_plaintext(self, processor):
        content = "Contenido generico".encode("utf-8")
        text, fmt = processor.extract_text(content, "data.csv")
        assert fmt == "plaintext"
        assert "Contenido generico" in text

    def test_no_extension_falls_to_plaintext(self, processor):
        content = "Sin extension".encode("utf-8")
        text, fmt = processor.extract_text(content, "archivo")
        assert fmt == "plaintext"
        assert "Sin extension" in text

    def test_image_routes_to_ocr(self, processor):
        _, fmt = processor.extract_text(b"fake-image-data", "scan.jpg")
        assert fmt == "ocr"

    def test_pdf_routes_to_pdf(self, processor):
        _, fmt = processor.extract_text(b"fake-pdf-data", "document.pdf")
        assert fmt == "pdf"

    def test_docx_routes_to_docx(self, processor):
        _, fmt = processor.extract_text(b"fake-docx-data", "report.docx")
        assert fmt == "docx"

    def test_xlsx_routes_to_xlsx(self, processor):
        _, fmt = processor.extract_text(b"fake-xlsx-data", "data.xlsx")
        assert fmt == "xlsx"

    def test_pptx_routes_to_pptx(self, processor):
        _, fmt = processor.extract_text(b"fake-pptx-data", "slides.pptx")
        assert fmt == "pptx"


class TestPlaintext:
    def test_utf8(self, processor):
        text, _ = processor.extract_text("Café résumé".encode("utf-8"), "file.txt")
        assert "Café" in text

    def test_latin1_fallback(self, processor):
        content = "Datos con ñ".encode("latin-1")
        text, _ = processor.extract_text(content, "file.log")
        assert "Datos" in text


class TestImageOCR:
    def test_missing_dependency(self, processor):
        with patch.dict("sys.modules", {"PIL": None, "PIL.Image": None, "pytesseract": None}):
            # Even with bad data, it should handle the error
            text, fmt = processor.extract_text(b"not-an-image", "photo.png")
            assert fmt == "ocr"

    @patch("app.services.attachment_processor.AttachmentProcessor._extract_image")
    def test_ocr_mock(self, mock_ocr, processor):
        mock_ocr.return_value = "Texto extraido por OCR"
        text, fmt = processor.extract_text(b"image-bytes", "scan.tiff")
        assert fmt == "ocr"
        assert text == "Texto extraido por OCR"


class TestPDF:
    @patch("app.services.attachment_processor.AttachmentProcessor._extract_pdf")
    def test_pdf_mock(self, mock_pdf, processor):
        mock_pdf.return_value = "Contenido del PDF"
        text, fmt = processor.extract_text(b"pdf-bytes", "doc.pdf")
        assert fmt == "pdf"
        assert text == "Contenido del PDF"


class TestDocx:
    @patch("app.services.attachment_processor.AttachmentProcessor._extract_docx")
    def test_docx_mock(self, mock_docx, processor):
        mock_docx.return_value = "Contenido Word"
        text, fmt = processor.extract_text(b"docx-bytes", "file.docx")
        assert fmt == "docx"
        assert text == "Contenido Word"


class TestPresidioImageRedaction:
    """Tests for Presidio image redaction and analysis capabilities."""

    def test_redact_image_returns_none_without_presidio(self, processor):
        """When Presidio image engines fail to init, redact_image returns None."""
        with patch(
            "app.services.attachment_processor._get_presidio_image_engines",
            return_value=(None, None),
        ):
            result = processor.redact_image(b"fake-image")
            assert result is None

    def test_analyze_image_returns_empty_without_presidio(self, processor):
        """When Presidio image engines fail to init, analyze_image returns []."""
        with patch(
            "app.services.attachment_processor._get_presidio_image_engines",
            return_value=(None, None),
        ):
            result = processor.analyze_image(b"fake-image")
            assert result == []

    def test_redact_image_calls_presidio(self, processor):
        """When Presidio is available, redact_image calls the engine and returns PNG bytes."""
        mock_redactor = MagicMock()
        mock_redacted_img = MagicMock()
        mock_redactor.redact.return_value = mock_redacted_img

        # Mock the save method to write known bytes
        def fake_save(buf, format):
            buf.write(b"\x89PNG_redacted_content")
        mock_redacted_img.save.side_effect = fake_save

        with patch(
            "app.services.attachment_processor._get_presidio_image_engines",
            return_value=(mock_redactor, None),
        ):
            # Create a minimal valid PNG (1x1 pixel)
            from PIL import Image
            import io
            img = Image.new("RGB", (10, 10), "white")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            image_bytes = buf.getvalue()

            result = processor.redact_image(image_bytes)
            assert result is not None
            assert b"PNG" in result
            mock_redactor.redact.assert_called_once()

    def test_analyze_image_returns_entities(self, processor):
        """When Presidio is available, analyze_image returns entity dicts."""
        mock_result = MagicMock()
        mock_result.entity_type = "PERSON"
        mock_result.score = 0.85
        mock_result.left = 10
        mock_result.top = 20
        mock_result.width = 100
        mock_result.height = 30

        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = [mock_result]

        with patch(
            "app.services.attachment_processor._get_presidio_image_engines",
            return_value=(None, mock_analyzer),
        ):
            from PIL import Image
            import io
            img = Image.new("RGB", (10, 10), "white")
            buf = io.BytesIO()
            img.save(buf, format="PNG")

            entities = processor.analyze_image(buf.getvalue())
            assert len(entities) == 1
            assert entities[0]["entity_type"] == "PERSON"
            assert entities[0]["score"] == 0.85
            assert entities[0]["left"] == 10
