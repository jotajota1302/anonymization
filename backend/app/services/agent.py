"""LangChain anonymization agent with multi-provider LLM support (Ollama, Azure OpenAI)."""

import json
from typing import Dict, List, Optional, AsyncGenerator

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.callbacks import AsyncCallbackHandler

import structlog

from ..config import settings
from ..services.anonymizer import Anonymizer
from ..services.database import DatabaseService
from ..websocket.manager import ConnectionManager
from ..tools.read_ticket import read_ticket
from ..tools.update_kosin import update_kosin, create_kosin_ticket
from ..tools.execute_action import execute_action
from ..tools.read_attachment import read_attachment

logger = structlog.get_logger()

SYSTEM_PROMPT = """# ROL
Eres el Agente de Anonimizacion, un asistente tecnico que actua como intermediario entre \
los datos reales de incidencias (que contienen informacion personal) y los operadores \
offshore que las resuelven. Tu funcion principal es ayudar al operador a entender, \
diagnosticar y resolver incidencias SIN que este vea jamas datos personales reales.

# CONTEXTO OPERATIVO
- Los tickets llegan de sistemas cliente con datos personales (nombres, emails, DNIs, etc.)
- Antes de que tu los veas, un motor de anonimizacion ha sustituido cada dato personal por \
un token como [PERSONA_1], [EMAIL_1], [DNI_1], [TELEFONO_1], [IP_1], [IBAN_1], etc.
- Tu trabajas SOLO con estos tokens. Nunca tienes acceso a los datos reales.
- El operador te habla por chat. Tu le ayudas a decidir que hacer con la incidencia.

# PROTOCOLO DE ANONIMIZACION (CRITICO - GDPR)
1. Usa EXCLUSIVAMENTE los tokens proporcionados ([PERSONA_1], [EMAIL_1], etc.) para \
referirte a cualquier dato personal. Nunca inventes datos personales, ni siquiera ficticios.
2. Puedes hablar libremente de aspectos tecnicos: codigos de error, logs, configuraciones, \
puertos, servicios, fechas de sistema, versiones de software.
3. Si en algun momento detectas que un dato personal se ha filtrado en la conversacion, \
senalalo inmediatamente y sustituyelo por el token correspondiente.
4. Si no puedes resolver algo sin acceder a datos personales que no tienes, indica que \
se requiere escalado a un operador onshore con acceso autorizado.

# FLUJO DE CONVERSACION
Cuando el operador selecciona una incidencia, sigue este flujo natural:

**1. Presentacion del ticket**
   - Resume la incidencia usando los datos anonimizados disponibles.
   - Indica: referencia del ticket, prioridad, estado actual y descripcion del problema.
   - Pregunta al operador como quiere proceder.

**2. Diagnostico interactivo**
   - Responde a las preguntas del operador sobre la incidencia.
   - Si necesitas mas contexto, usa `read_ticket` para consultar el ticket original.
   - Propone lineas de investigacion o acciones tecnicas cuando sea apropiado.
   - Si el operador te pide ejecutar algo tecnico (ver logs, comprobar un servicio, \
reiniciar), usa `execute_action`.

**3. Registro de avance**
   - Cuando haya progreso significativo, ofrece registrarlo en KOSIN con `update_kosin`.
   - Los comentarios y actualizaciones en KOSIN siempre van anonimizados.

**4. Resolucion o escalado**
   - Cuando la incidencia se resuelva, propone cerrarla y registrar la solucion.
   - Si no se puede resolver a este nivel, recomienda escalar indicando el motivo tecnico.

# USO DE HERRAMIENTAS
- `read_ticket(ticket_id)`: Consulta los detalles completos de un ticket del sistema origen. \
Usala cuando necesites mas informacion sobre la incidencia.
- `update_kosin(ticket_id, comment, status)`: Anade comentarios o cambia el estado de un \
ticket en KOSIN. Los comentarios deben estar anonimizados.
- `create_kosin_ticket(summary, description, priority)`: Crea un ticket nuevo en KOSIN. \
Solo datos anonimizados.
- `execute_action(action, service, interval)`: Ejecuta acciones tecnicas controladas. \
Acciones disponibles: get_logs, check_status, restart_service, check_connectivity.
- `read_attachment(ticket_id, attachment_index)`: Lee y anonimiza el contenido de un adjunto \
del ticket origen. Soporta PDF, imagenes (OCR), Word, Excel, PowerPoint y texto plano. \
Usa attachment_index para seleccionar cual adjunto leer (0 = primero).

No ejecutes herramientas salvo que el operador lo solicite o sea claramente necesario \
para responder su pregunta. Informa siempre de lo que vas a hacer antes de hacerlo.

# ESTILO DE COMUNICACION
- Responde en espanol.
- Se directo y profesional, sin relleno innecesario.
- Usa viñetas o listas cuando ayude a la claridad.
- Cuando ejecutes una accion, indica que la estas ejecutando y muestra el resultado.
- Adapta el nivel tecnico al operador: si hace preguntas simples, responde simple; \
si entra en detalle tecnico, acompanale.
- No repitas informacion que el operador ya ha visto salvo que la pida.

# ACCIONES SUGERIDAS
Al final de CADA respuesta, incluye una linea con 2-4 acciones sugeridas que el operador \
podria querer hacer a continuacion. Usa este formato exacto (es parseado por el frontend):

[CHIPS: "Accion sugerida 1", "Accion sugerida 2", "Accion sugerida 3"]

Ejemplos de chips segun el contexto:
- Al presentar un ticket: [CHIPS: "Ver detalles completos", "Consultar logs", "Diagnosticar problema"]
- Tras diagnosticar: [CHIPS: "Reiniciar servicio", "Escalar incidencia", "Registrar en KOSIN"]
- Tras ejecutar accion: [CHIPS: "Verificar estado", "Registrar avance", "Finalizar ticket"]
- Si necesitas mas info: [CHIPS: "Leer ticket original", "Ver comentarios", "Consultar historico"]

Los chips deben ser acciones concretas y relevantes al momento de la conversacion. \
Deben ser frases cortas (2-5 palabras) y accionables."""


class StreamingCallback(AsyncCallbackHandler):
    """Callback handler that streams tokens via WebSocket."""

    def __init__(self, ws_manager: ConnectionManager, client_id: str, ticket_id: int = None):
        self.ws_manager = ws_manager
        self.client_id = client_id
        self.ticket_id = ticket_id
        self.tokens: List[str] = []

    async def on_llm_new_token(self, token: str, **kwargs):
        self.tokens.append(token)
        await self.ws_manager.send_token(self.client_id, token, self.ticket_id)

    def get_full_response(self) -> str:
        return "".join(self.tokens)


class AnonymizationAgent:
    """LangChain agent with anonymization pipeline."""

    def __init__(
        self,
        anonymizer: Anonymizer,
        db: DatabaseService,
        ws_manager: ConnectionManager,
        encryption_key: bytes,
    ):
        self.anonymizer = anonymizer
        self.db = db
        self.ws_manager = ws_manager
        self.encryption_key = encryption_key

        # Initialize LLM based on provider
        self.llm = self._create_llm()
        logger.info("llm_initialized", provider=settings.llm_provider)

        # Tools
        self.tools = [read_ticket, update_kosin, create_kosin_ticket, execute_action, read_attachment]

    @staticmethod
    def _create_llm():
        """Create LLM instance based on configured provider."""
        provider = settings.llm_provider.lower()

        if provider == "ollama":
            from langchain_ollama import ChatOllama
            return ChatOllama(
                base_url=settings.ollama_base_url,
                model=settings.ollama_model,
                temperature=0.3,
            )
        elif provider == "azure":
            from langchain_openai import AzureChatOpenAI
            return AzureChatOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                azure_deployment=settings.azure_openai_deployment,
                api_key=settings.azure_openai_key,
                api_version=settings.azure_openai_api_version,
                temperature=0.3,
                streaming=True,
            )
        else:
            raise ValueError(f"Unknown LLM provider: {provider}. Use 'ollama' or 'azure'")

    def _build_messages(
        self, chat_history: List[Dict], user_message: str
    ) -> List:
        """Build message list from chat history and new message."""
        messages = [SystemMessage(content=SYSTEM_PROMPT)]

        for msg in chat_history:
            if msg["role"] == "operator":
                messages.append(HumanMessage(content=msg["message"]))
            else:
                messages.append(AIMessage(content=msg["message"]))

        messages.append(HumanMessage(content=user_message))
        return messages

    async def _get_substitution_map(self, ticket_id: int) -> Dict[str, str]:
        """Load and decrypt substitution map for a ticket."""
        encrypted = await self.db.get_substitution_map(ticket_id)
        if encrypted:
            try:
                return Anonymizer.decrypt_map(encrypted, self.encryption_key)
            except Exception as e:
                logger.error("decrypt_map_failed", ticket_id=ticket_id, error=str(e))
        return {}

    async def chat(
        self,
        ticket_id: int,
        user_message: str,
        client_id: str,
    ) -> str:
        """Process a chat message with anonymization pipeline.

        1. Load substitution map
        2. PRE: Filter user message for any PII
        3. Invoke LLM agent with history + message
        4. POST: Filter response for PII leaks
        5. Save to chat history
        6. Send response via WebSocket
        """
        # 1. Load substitution map
        sub_map = await self._get_substitution_map(ticket_id)

        # 2. PRE-filter: anonymize user input
        filtered_message = self.anonymizer.filter_output(user_message, sub_map)

        # 3. Load chat history
        history = await self.db.get_chat_history(ticket_id)

        # Save operator message
        await self.db.add_chat_message(ticket_id, "operator", filtered_message)

        # 4. Build messages and invoke LLM
        messages = self._build_messages(history, filtered_message)

        streaming_cb = StreamingCallback(self.ws_manager, client_id, ticket_id)

        try:
            # Use LLM with tools via bind_tools
            llm_with_tools = self.llm.bind_tools(self.tools)

            response = await llm_with_tools.ainvoke(
                messages,
                config={"callbacks": [streaming_cb]},
            )

            # Check if tools need to be called
            if response.tool_calls:
                tool_results = []
                for tool_call in response.tool_calls:
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]

                    # Find and execute the tool
                    for t in self.tools:
                        if t.name == tool_name:
                            await self.ws_manager.send_info(
                                client_id,
                                f"Ejecutando: {tool_name}...",
                                ticket_id,
                            )
                            result = await t.ainvoke(tool_args)
                            tool_results.append(f"[{tool_name}]: {result}")
                            break

                # Re-invoke LLM with tool results
                messages.append(AIMessage(content=response.content or ""))
                for tr in tool_results:
                    messages.append(HumanMessage(content=f"Resultado de herramienta: {tr}"))

                streaming_cb2 = StreamingCallback(self.ws_manager, client_id, ticket_id)
                final_response = await self.llm.ainvoke(
                    messages,
                    config={"callbacks": [streaming_cb2]},
                )
                agent_text = final_response.content
            else:
                agent_text = response.content

        except Exception as e:
            logger.error("agent_error", error=str(e), ticket_id=ticket_id)
            agent_text = f"Error al procesar la solicitud. Por favor, intenta de nuevo."
            await self.ws_manager.send_error(client_id, agent_text, ticket_id)
            return agent_text

        # 5. POST-filter: scan response for PII leaks
        filtered_response = self.anonymizer.filter_output(agent_text, sub_map)

        # 6. Save agent response
        await self.db.add_chat_message(ticket_id, "agent", filtered_response)

        # 7. Send complete signal
        await self.ws_manager.send_complete(client_id, filtered_response, ticket_id)

        # 8. Audit log
        await self.db.add_audit_log(
            operator_id="operator",
            action="chat_message",
            ticket_mapping_id=ticket_id,
            details=f"message_length={len(filtered_message)}",
        )

        return filtered_response

    async def generate_initial_summary(
        self, ticket_id: int, client_id: str
    ) -> str:
        """Generate an anonymized initial summary when a ticket is selected."""
        sub_map = await self._get_substitution_map(ticket_id)
        ticket = await self.db.get_ticket(ticket_id)

        if not ticket:
            return "Ticket no encontrado."

        # Load existing chat history so the LLM has full context
        history = await self.db.get_chat_history(ticket_id)

        prompt = (
            f"El operador ha seleccionado la siguiente incidencia para revisarla. "
            f"Presentale un resumen claro y preguntale como quiere proceder.\n\n"
            f"Referencia: {ticket['kosin_ticket_id']}\n"
            f"Resumen: {ticket['summary']}\n"
            f"Descripcion anonimizada:\n{ticket['anonymized_description']}\n"
            f"Estado: {ticket['status']}\n"
            f"Prioridad: {ticket['priority']}\n\n"
            f"Recuerda: usa solo los tokens de anonimizacion, nunca inventes datos personales."
        )

        # Build messages with history context
        messages = [SystemMessage(content=SYSTEM_PROMPT)]
        for msg in history:
            if msg["role"] == "operator":
                messages.append(HumanMessage(content=msg["message"]))
            else:
                messages.append(AIMessage(content=msg["message"]))
        messages.append(HumanMessage(content=prompt))

        streaming_cb = StreamingCallback(self.ws_manager, client_id, ticket_id)

        try:
            response = await self.llm.ainvoke(
                messages,
                config={"callbacks": [streaming_cb]},
            )
            agent_text = response.content
        except Exception as e:
            logger.error("summary_error", error=str(e))
            agent_text = (
                f"Ticket {ticket['kosin_ticket_id']}: "
                f"{ticket['summary']}\n\n"
                f"Estado: {ticket['status']} | Prioridad: {ticket['priority']}\n\n"
                f"{ticket['anonymized_description']}"
            )

        filtered = self.anonymizer.filter_output(agent_text, sub_map)
        await self.db.add_chat_message(ticket_id, "agent", filtered)
        await self.ws_manager.send_complete(client_id, filtered, ticket_id)

        return filtered
