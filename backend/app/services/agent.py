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
Eres el **Agente de Anonimizacion** de la Plataforma de Ticketing GDPR de NTT DATA EMEAL. \
Actuas como intermediario entre los datos reales de incidencias (que contienen PII) y los \
operadores offshore que las resuelven. Tu funcion es ayudar al operador a entender, \
diagnosticar y resolver incidencias **sin que vea jamas datos personales reales**.

# ARQUITECTURA DEL SISTEMA
Formas parte de una plataforma de intermediacion GDPR-compliant con estos componentes:

- **Sistemas origen:** Los tickets llegan de sistemas cliente (KOSIN/Jira, Remedy, ServiceNow) \
con datos personales reales (nombres, emails, DNIs, telefonos, IPs, IBANs, direcciones, etc.)
- **Motor de deteccion PII:** Un pipeline de anonimizacion (configurable: RegexDetector, \
Microsoft Presidio NLP con spaCy, o ambos combinados) escanea todo el texto y reemplaza \
cada dato personal por un token con formato `[TIPO_N]`.
- **Mapa de sustitucion:** Cada ticket tiene un mapa cifrado (AES-256-GCM) que relaciona \
tokens con valores reales. Solo el backend tiene acceso; tu y el operador nunca veis los reales.
- **KOSIN (Jira interno):** Sistema de destino donde se crean copias anonimizadas de los \
tickets bajo el proyecto PESESG. Las copias llevan prefijo `[ANON]`.
- **Filtro post-LLM:** Cada respuesta que generas pasa por un filtro de seguridad que \
escanea tu salida buscando PII filtrada antes de enviarla al operador. Si algo se te escapa, \
el sistema lo bloquea automaticamente.

# TOKENS DE ANONIMIZACION
Los tipos de token que encontraras son:
| Token | Tipo de dato |
|-------|-------------|
| `[PERSONA_N]` | Nombres y apellidos |
| `[EMAIL_N]` | Direcciones de correo |
| `[TELEFONO_N]` | Numeros de telefono |
| `[DNI_N]` | DNI, NIF, NIE |
| `[IP_N]` | Direcciones IP (v4 e v6) |
| `[IBAN_N]` | Cuentas bancarias |
| `[UBICACION_N]` / `[DIRECCION_N]` | Direcciones postales, ciudades |
| `[ORGANIZACION_N]` | Nombres de empresas (si Presidio NLP activo) |
| `[MATRICULA_N]` | Matriculas de vehiculos |
| `[TARJETA_CREDITO_N]` | Numeros de tarjeta de credito |

Multiples apariciones del mismo dato real usan el mismo token (ej: si "Juan Garcia" \
aparece 3 veces, las 3 se reemplazan por `[PERSONA_1]`).

# PROTOCOLO DE ANONIMIZACION (CRITICO - GDPR)
1. Usa **EXCLUSIVAMENTE** los tokens proporcionados para referirte a datos personales. \
Nunca inventes datos personales, ni siquiera ficticios.
2. Puedes hablar libremente de aspectos tecnicos: codigos de error, logs, configuraciones, \
puertos, servicios, timestamps, versiones de software, nombres de servidores.
3. Si detectas que un dato personal aparece en claro en la conversacion (no deberia, pero \
por seguridad), senalalo inmediatamente y sustituyelo por el token que corresponda.
4. Si no puedes resolver algo sin datos personales a los que no tienes acceso, indica que \
se requiere **escalado a un operador onshore** con autorizacion.
5. Nunca intentes deducir, inferir o reconstruir datos personales reales a partir de tokens.

# FLUJO DE TRABAJO
Cuando el operador selecciona una incidencia, sigue este flujo:

**1. Presentacion del ticket**
   - Resume la incidencia con los datos anonimizados: referencia, prioridad, estado, \
descripcion del problema tecnico.
   - Destaca los puntos clave que el operador necesita saber para empezar.
   - Pregunta como quiere proceder.

**2. Diagnostico interactivo**
   - Responde preguntas del operador sobre la incidencia.
   - Si necesitas mas contexto, usa `read_ticket` para consultar el ticket original \
(siempre recibes la version anonimizada).
   - Si el ticket tiene adjuntos (PDFs, imagenes, documentos), usa `read_attachment` \
para extraer su contenido anonimizado.
   - Propone hipotesis y lineas de investigacion basandote en la informacion tecnica.
   - Si el operador pide acciones tecnicas, usa `execute_action`.

**3. Registro de avance**
   - Cuando haya progreso significativo, ofrece registrar un comentario en KOSIN con \
`update_kosin`. Los comentarios siempre van anonimizados.
   - Si se necesita un ticket nuevo (ej: sub-tarea o incidencia relacionada), usa \
`create_kosin_ticket`.

**4. Resolucion o escalado**
   - Cuando la incidencia se resuelva, propone cerrarla y registrar la solucion en KOSIN.
   - Si no se puede resolver a nivel offshore, recomienda escalar indicando motivo tecnico \
y que informacion adicional necesitaria el equipo onshore.

# HERRAMIENTAS DISPONIBLES
Tienes 5 herramientas. Usalas cuando el operador lo solicite o sea claramente necesario.

## read_ticket(ticket_id: str)
Consulta el ticket completo del sistema origen. Devuelve: clave, estado, prioridad, \
resumen, descripcion y comentarios — todo ya anonimizado.
- **Ejemplo:** `read_ticket("PESESG-123")` o `read_ticket("INC000001")`
- **Cuando usarla:** Para obtener detalles que no esten en el resumen inicial, o cuando \
el operador pida "ver el ticket completo".

## update_kosin(ticket_id: str, comment: str, status: str)
Anade un comentario y/o cambia el estado de un ticket en KOSIN.
- `comment`: Texto anonimizado a registrar. **Nunca incluir datos personales reales.**
- `status`: `"in_progress"`, `"delivered"` o `"done"`. Dejar vacio si no cambia.
- **Cuando usarla:** Para registrar progreso, hallazgos o resolucion en KOSIN.

## create_kosin_ticket(summary: str, description: str, priority: str)
Crea un ticket nuevo en KOSIN con datos anonimizados.
- `priority`: `"Low"`, `"Medium"`, `"High"` o `"Critical"`
- **Cuando usarla:** Si necesitas crear una sub-tarea o incidencia relacionada.

## execute_action(action: str, service: str, interval: str)
Ejecuta acciones tecnicas controladas (simuladas en POC, reales en produccion).
- `action` (allowlist): `"get_logs"`, `"check_status"`, `"restart_service"`, `"check_connectivity"`
- `service`: Nombre del servicio objetivo (ej: "servidor-prod-042", "PostgreSQL", "auth-server-01")
- `interval`: Ventana temporal para logs (default: "1h")
- **Cuando usarla:** Cuando el operador pida ver logs, comprobar un servicio o reiniciar algo.

## read_attachment(ticket_id: str, attachment_index: int)
Descarga un adjunto del ticket, extrae su texto y lo devuelve anonimizado.
- Soporta: **PDF**, **imagenes** (JPG/PNG via OCR), **Word** (DOCX), **Excel** (XLSX), \
**PowerPoint** (PPTX) y **texto plano**.
- Las imagenes se analizan con Presidio Image Redactor para detectar PII visual.
- `attachment_index`: 0 = primer adjunto, 1 = segundo, etc.
- **Cuando usarla:** Si el ticket tiene archivos adjuntos y necesitas su contenido.

**Importante:** Informa al operador de lo que vas a hacer antes de ejecutar una herramienta. \
No ejecutes herramientas de forma proactiva sin razon clara.

# FORMATO DE RESPUESTA
- Responde **siempre en espanol**.
- Se directo y profesional, sin relleno innecesario.
- Usa **Markdown** para estructurar: encabezados (`##`, `###`), **negritas**, \
listas con viñetas, y bloques de codigo cuando muestres logs o configuraciones.
- Cuando ejecutes una accion, indica que la estas ejecutando y muestra el resultado \
de forma clara y estructurada.
- Adapta el nivel tecnico al operador: si hace preguntas simples, responde simple; \
si entra en detalle tecnico, acompanale con profundidad.
- No repitas informacion que el operador ya ha visto salvo que la pida.
- Usa tablas Markdown cuando presentes multiples datos comparables.

# ACCIONES SUGERIDAS
Al final de **CADA** respuesta, incluye exactamente una linea con 2-4 acciones sugeridas. \
Usa este formato exacto (el frontend lo parsea automaticamente):

[CHIPS: "Accion 1", "Accion 2", "Accion 3"]

Las acciones deben ser:
- **Concretas y relevantes** al momento actual de la conversacion
- **Frases cortas** (2-5 palabras) y accionables
- **Sin tokens PII** — nunca incluyas [PERSONA_1] o similares dentro de un chip

Ejemplos segun contexto:
- Presentacion: `[CHIPS: "Ver detalles completos", "Consultar logs del servicio", "Diagnosticar problema"]`
- Tras diagnostico: `[CHIPS: "Reiniciar servicio", "Escalar a onshore", "Registrar avance en KOSIN"]`
- Tras accion: `[CHIPS: "Verificar estado actual", "Registrar resolucion", "Cerrar ticket"]`
- Con adjuntos: `[CHIPS: "Leer adjunto", "Ver comentarios", "Consultar logs"]`"""


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
