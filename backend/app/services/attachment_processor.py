"""Attachment text extraction service supporting PDF, images (LLM vision), and Office formats.

Supports optional Presidio Image Redactor for PII detection/redaction directly on images.
Uses LLM vision (OpenAI GPT-4o) for image text extraction instead of Tesseract OCR.
"""

import io
import base64
from typing import Tuple, Optional

import structlog

logger = structlog.get_logger()

# Lazy-initialized Presidio image engines (expensive to create)
_image_redactor_engine = None
_image_analyzer_engine = None


def _get_presidio_image_engines():
    """Lazy-init Presidio image engines with Spanish NLP support."""
    global _image_redactor_engine, _image_analyzer_engine

    if _image_redactor_engine is not None:
        return _image_redactor_engine, _image_analyzer_engine

    try:
        from presidio_image_redactor import ImageRedactorEngine, ImageAnalyzerEngine
        from presidio_analyzer import AnalyzerEngine
        from presidio_analyzer.nlp_engine import SpacyNlpEngine

        # Use Spanish spaCy model for NER in images
        nlp_engine = SpacyNlpEngine(
            models=[{"lang_code": "es", "model_name": "es_core_news_lg"}],
        )
        analyzer = AnalyzerEngine(
            nlp_engine=nlp_engine,
            supported_languages=["es"],
        )
        _image_analyzer_engine = ImageAnalyzerEngine(analyzer_engine=analyzer)
        _image_redactor_engine = ImageRedactorEngine(
            image_analyzer_engine=_image_analyzer_engine,
        )
        logger.info("presidio_image_engines_initialized")
        return _image_redactor_engine, _image_analyzer_engine
    except (ImportError, OSError) as e:
        logger.warning("presidio_image_not_available", error=str(e))
        return None, None


class AttachmentProcessor:
    """Extracts text from attachment files by routing on file extension.

    When presidio-image-redactor is installed, images can also be redacted
    (PII regions blacked out) and analyzed (PII entities with bounding boxes).
    """

    def extract_text(self, content: bytes, filename: str) -> Tuple[str, str]:
        """Extract text from attachment content.

        Args:
            content: Raw file bytes.
            filename: Original filename (used to determine format).

        Returns:
            Tuple of (extracted_text, format_used).
        """
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        if ext in ("jpg", "jpeg", "png", "bmp", "tiff", "tif"):
            return self._extract_image(content), "ocr"
        elif ext == "pdf":
            return self._extract_pdf(content), "pdf"
        elif ext == "docx":
            return self._extract_docx(content), "docx"
        elif ext == "xlsx":
            return self._extract_xlsx(content), "xlsx"
        elif ext == "pptx":
            return self._extract_pptx(content), "pptx"
        else:
            return self._extract_plaintext(content), "plaintext"

    def redact_image(self, content: bytes, fill_color: Tuple[int, int, int] = (0, 0, 0)) -> Optional[bytes]:
        """Redact PII from an image using Presidio Image Redactor.

        Args:
            content: Raw image bytes (JPEG, PNG, etc.)
            fill_color: RGB color to fill redacted regions (default: black)

        Returns:
            Redacted image as PNG bytes, or None if Presidio is not available.
        """
        redactor, _ = _get_presidio_image_engines()
        if redactor is None:
            return None

        try:
            from PIL import Image
            image = Image.open(io.BytesIO(content))
            redacted = redactor.redact(
                image,
                fill=fill_color,
                ocr_kwargs={"lang": "spa+eng"},
                language="es",
            )
            buf = io.BytesIO()
            redacted.save(buf, format="PNG")
            logger.info("image_redacted_successfully")
            return buf.getvalue()
        except Exception as e:
            logger.error("image_redaction_failed", error=str(e))
            return None

    def analyze_image(self, content: bytes) -> list:
        """Analyze an image for PII entities using Presidio Image Analyzer.

        Args:
            content: Raw image bytes.

        Returns:
            List of detected PII entities with bounding boxes,
            or empty list if Presidio is not available.
        """
        _, analyzer = _get_presidio_image_engines()
        if analyzer is None:
            return []

        try:
            from PIL import Image
            image = Image.open(io.BytesIO(content))
            results = analyzer.analyze(
                image,
                ocr_kwargs={"lang": "spa+eng"},
                language="es",
            )
            entities = []
            for r in results:
                entities.append({
                    "entity_type": r.entity_type,
                    "text": r.text if hasattr(r, "text") else "",
                    "score": r.score,
                    "left": r.left,
                    "top": r.top,
                    "width": r.width,
                    "height": r.height,
                })
            logger.info("image_analyzed", entities_found=len(entities))
            return entities
        except Exception as e:
            logger.error("image_analysis_failed", error=str(e))
            return []

    def _extract_image(self, content: bytes) -> str:
        """Extract text from image using LLM vision API."""
        try:
            from ..config import settings
            b64_image = base64.b64encode(content).decode("utf-8")

            # Detect MIME type
            mime = "image/png"
            if content[:3] == b'\xff\xd8\xff':
                mime = "image/jpeg"
            elif content[:4] == b'\x89PNG':
                mime = "image/png"
            elif content[:2] == b'BM':
                mime = "image/bmp"

            if settings.llm_provider == "openai":
                import httpx
                response = httpx.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                    json={
                        "model": settings.openai_model if "vision" in settings.openai_model or "4o" in settings.openai_model else "gpt-4o-mini",
                        "messages": [{"role": "user", "content": [
                            {"type": "text", "text": "Extrae todo el texto visible en esta imagen. Devuelve solo el texto extraido, sin comentarios ni explicaciones."},
                            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64_image}"}}
                        ]}],
                        "max_tokens": 4096,
                    },
                    timeout=60,
                )
                response.raise_for_status()
                text = response.json()["choices"][0]["message"]["content"]
                logger.info("image_text_extracted_via_llm", length=len(text))
                return text.strip()

            elif settings.llm_provider == "azure":
                import httpx
                response = httpx.post(
                    f"{settings.azure_openai_endpoint}/openai/deployments/{settings.azure_openai_deployment}/chat/completions?api-version={settings.azure_openai_api_version}",
                    headers={"api-key": settings.azure_openai_key},
                    json={
                        "messages": [{"role": "user", "content": [
                            {"type": "text", "text": "Extrae todo el texto visible en esta imagen. Devuelve solo el texto extraido, sin comentarios ni explicaciones."},
                            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64_image}"}}
                        ]}],
                        "max_tokens": 4096,
                    },
                    timeout=60,
                )
                response.raise_for_status()
                text = response.json()["choices"][0]["message"]["content"]
                logger.info("image_text_extracted_via_azure", length=len(text))
                return text.strip()

            else:
                return "[Extraccion de texto de imagenes requiere LLM_PROVIDER openai o azure con soporte vision]"

        except Exception as e:
            logger.error("llm_image_extraction_failed", error=str(e))
            return f"[Error extraccion imagen: {e}]"

    def _extract_pdf(self, content: bytes) -> str:
        try:
            import pdfplumber
        except ImportError:
            return "[Error: pdfplumber no instalado. Instalar con: pip install pdfplumber]"

        try:
            pages_text = []
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text and text.strip():
                        pages_text.append(text.strip())
                    else:
                        # LLM vision fallback for scanned pages
                        img = page.to_image(resolution=300)
                        buf = io.BytesIO()
                        img.original.save(buf, format="PNG")
                        ocr_text = self._extract_image(buf.getvalue())
                        if ocr_text and not ocr_text.startswith("[Error"):
                            pages_text.append(ocr_text)

            return "\n\n".join(pages_text) if pages_text else "[PDF sin texto extraíble]"
        except Exception as e:
            logger.error("pdf_extraction_failed", error=str(e))
            return f"[Error PDF: {e}]"

    def _extract_docx(self, content: bytes) -> str:
        try:
            from docx import Document
        except ImportError:
            return "[Error: python-docx no instalado. Instalar con: pip install python-docx]"

        try:
            doc = Document(io.BytesIO(content))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n".join(paragraphs) if paragraphs else "[DOCX sin texto]"
        except Exception as e:
            logger.error("docx_extraction_failed", error=str(e))
            return f"[Error DOCX: {e}]"

    def _extract_xlsx(self, content: bytes) -> str:
        try:
            from openpyxl import load_workbook
        except ImportError:
            return "[Error: openpyxl no instalado. Instalar con: pip install openpyxl]"

        try:
            wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            rows_text = []
            for sheet in wb.sheetnames:
                ws = wb[sheet]
                rows_text.append(f"--- Hoja: {sheet} ---")
                for row in ws.iter_rows(values_only=True):
                    cells = [str(c) if c is not None else "" for c in row]
                    if any(cells):
                        rows_text.append(" | ".join(cells))
            wb.close()
            return "\n".join(rows_text) if rows_text else "[XLSX sin datos]"
        except Exception as e:
            logger.error("xlsx_extraction_failed", error=str(e))
            return f"[Error XLSX: {e}]"

    def _extract_pptx(self, content: bytes) -> str:
        try:
            from pptx import Presentation
        except ImportError:
            return "[Error: python-pptx no instalado. Instalar con: pip install python-pptx]"

        try:
            prs = Presentation(io.BytesIO(content))
            slides_text = []
            for i, slide in enumerate(prs.slides, 1):
                texts = []
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        for para in shape.text_frame.paragraphs:
                            if para.text.strip():
                                texts.append(para.text.strip())
                if texts:
                    slides_text.append(f"--- Diapositiva {i} ---\n" + "\n".join(texts))
            return "\n\n".join(slides_text) if slides_text else "[PPTX sin texto]"
        except Exception as e:
            logger.error("pptx_extraction_failed", error=str(e))
            return f"[Error PPTX: {e}]"

    def _extract_plaintext(self, content: bytes) -> str:
        try:
            return content.decode("utf-8").strip()
        except UnicodeDecodeError:
            try:
                return content.decode("latin-1").strip()
            except Exception:
                return "[No se pudo decodificar el archivo como texto]"
