"""Tool: Read and anonymize an attachment from the source ticket."""

from langchain_core.tools import tool


@tool
async def read_attachment(ticket_id: str, attachment_index: int = 0) -> str:
    """Lee y anonimiza el contenido de un adjunto del ticket origen.

    Descarga el archivo adjunto, extrae su texto (soporta PDF, imagenes,
    Word, Excel, PowerPoint y texto plano) y lo devuelve anonimizado.

    Args:
        ticket_id: ID del ticket en el sistema origen (ej: PROJ-101)
        attachment_index: Indice del adjunto a leer (0 = primero). Por defecto 0.
    """
    from ..main import app_state
    from ..services.attachment_processor import AttachmentProcessor

    # Use router to resolve connector by ticket prefix, fallback to jira_connector
    router = app_state.get("connector_router")
    if router:
        try:
            _, connector = router.get_connector(ticket_id)
        except ValueError:
            connector = app_state["jira_connector"]
    else:
        connector = app_state["jira_connector"]
    anonymizer = app_state["anonymizer"]

    try:
        ticket = await connector.get_ticket(ticket_id)
        attachments = ticket.get("attachments", [])

        if not attachments:
            return f"El ticket {ticket_id} no tiene adjuntos."

        if attachment_index < 0 or attachment_index >= len(attachments):
            return (
                f"Indice {attachment_index} fuera de rango. "
                f"El ticket tiene {len(attachments)} adjunto(s) (indices 0-{len(attachments) - 1})."
            )

        attachment = attachments[attachment_index]
        filename = attachment.get("filename", "unknown")
        content_url = attachment.get("content", "")

        if not content_url:
            return f"El adjunto '{filename}' no tiene URL de contenido."

        # Download attachment
        content_bytes = await connector.download_attachment(content_url)
        if not content_bytes:
            return f"No se pudo descargar el adjunto '{filename}'."

        # Extract text
        processor = AttachmentProcessor()
        text, format_used = processor.extract_text(content_bytes, filename)

        if not text or text.startswith("[Error"):
            return f"Adjunto '{filename}' ({format_used}): {text}"

        # Anonymize the extracted text
        anonymized_text, _ = anonymizer.anonymize(text)

        # For images, also try Presidio image analysis for extra PII context
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        image_pii_note = ""
        if ext in ("jpg", "jpeg", "png", "bmp", "tiff", "tif"):
            image_entities = processor.analyze_image(content_bytes)
            if image_entities:
                unique_types = {e["entity_type"] for e in image_entities}
                image_pii_note = (
                    f"\n\n[Presidio Image: {len(image_entities)} entidades PII detectadas "
                    f"en la imagen — tipos: {', '.join(sorted(unique_types))}. "
                    f"Imagen redactada disponible via API.]"
                )

        return (
            f"Contenido del adjunto '{filename}' ({format_used}):\n\n"
            f"{anonymized_text}{image_pii_note}"
        )

    except Exception as e:
        return f"Error al leer adjunto del ticket {ticket_id}: {str(e)}"
