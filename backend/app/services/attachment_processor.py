"""Attachment text extraction service supporting PDF, images (OCR), and Office formats."""

import io
from typing import Tuple

import structlog

logger = structlog.get_logger()


class AttachmentProcessor:
    """Extracts text from attachment files by routing on file extension."""

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

    def _extract_image(self, content: bytes) -> str:
        try:
            from PIL import Image
            import pytesseract
        except ImportError:
            return "[Error: pytesseract o Pillow no instalados. Instalar con: pip install pytesseract Pillow]"

        try:
            image = Image.open(io.BytesIO(content))
            text = pytesseract.image_to_string(image, lang="spa+eng")
            return text.strip()
        except Exception as e:
            logger.error("ocr_extraction_failed", error=str(e))
            return f"[Error OCR: {e}]"

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
                        # OCR fallback for scanned pages
                        img = page.to_image(resolution=300)
                        ocr_text = self._extract_image(img.original.tobytes())
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
