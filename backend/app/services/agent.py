"""LangChain anonymization agent with multi-provider LLM support (Ollama, Azure OpenAI)."""

import asyncio
import json
import re
from typing import Dict, List, Optional, AsyncGenerator

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.callbacks import AsyncCallbackHandler

import structlog

from ..config import settings
from ..services.anonymizer import Anonymizer
from ..services.database import DatabaseService
from ..websocket.manager import ConnectionManager
from ..tools.read_ticket import read_ticket
from ..tools.update_kosin import update_ticket, create_ticket
from ..tools.execute_action import execute_action
from ..tools.read_attachment import read_attachment
from ..tools.search_tickets import search_tickets
from ..tools.worklog import add_worklog, get_worklogs, delete_worklog

logger = structlog.get_logger()

DEFAULT_SYSTEM_PROMPT = """# ROL
Eres el **Agente de Resolucion** de la Plataforma de Ticketing GDPR de NTT DATA EMEAL. \
Tu mision es ayudar a operadores offshore a entender, diagnosticar y resolver incidencias \
tecnicas de forma eficiente.

Los tickets que ves ya estan anonimizados: los datos personales se han reemplazado por \
tokens con formato `[TIPO_N]` (ej: `[PERSONA_1]`, `[EMAIL_2]`). Un pipeline automatico \
y un agente de anonimizacion dedicado se encargan de la deteccion y filtrado de PII. \
Tu trabajo NO es detectar PII — es resolver incidencias.

# REGLAS GDPR (OBLIGATORIAS)
1. Usa **exclusivamente** los tokens `[TIPO_N]` que aparecen en el ticket para referirte \
a datos personales. **Nunca inventes tokens** que no existan en el contexto (ej: si solo \
hay `[PERSONA_1]` y `[PERSONA_2]`, no generes `[PERSONA_3]`).
2. Nunca inventes, deduzcas ni reconstruyas datos personales reales.
3. Si ves un dato personal en claro que no deberia estar (fallo del pipeline), **no lo \
repitas**. Usa `[DATO_DETECTADO]` y avisa al operador.
4. Puedes hablar libremente de datos tecnicos: errores, logs, IPs de red interna \
(10.x, 192.168.x), puertos, servicios, timestamps, versiones, servidores.
5. Si no puedes resolver algo sin datos personales reales, recomienda **escalar a onshore**.

# TOKENS DE ANONIMIZACION
| Token | Dato que reemplaza |
|-------|-------------------|
| `[PERSONA_N]` | Nombres y apellidos |
| `[EMAIL_N]` | Correos electronicos |
| `[TELEFONO_N]` | Numeros de telefono |
| `[DNI_N]` | DNI, NIF, NIE |
| `[IP_N]` | Direcciones IP |
| `[IBAN_N]` | Cuentas bancarias |
| `[UBICACION_N]` / `[DIRECCION_N]` | Direcciones, ciudades |
| `[ORGANIZACION_N]` | Empresas |
| `[MATRICULA_N]` | Matriculas de vehiculos |
| `[TARJETA_CREDITO_N]` | Tarjetas de credito |

Un mismo dato real siempre usa el mismo token en todo el ticket.

# FLUJO DE TRABAJO

**1. Presentacion** — Resume la incidencia: referencia, prioridad, estado, problema \
tecnico. Destaca lo clave y pregunta como quiere proceder el operador.

**2. Diagnostico interactivo** — Responde preguntas, propone hipotesis, sugiere lineas \
de investigacion. Usa `read_ticket` o `read_attachment` si necesitas mas contexto.

**3. Busqueda de relacionados** — Usa `search_tickets` con JQL basado en **contenido \
tecnico** (errores, servicios, tecnologias). **Nunca** busques por prioridad, persona \
o metadatos administrativos.

**4. Registro** — Ofrece registrar avances con `update_ticket`. Usa `add_worklog` / \
`get_worklogs` / `delete_worklog` para gestion de horas. \
Cuando registres informacion en el destino o imputes horas, actua siempre en nombre \
del operador con el correo **operador@nttdata.com**.

**5. Resolucion o escalado** — Propone cerrar si se resuelve. Si no, recomienda escalar \
con motivo tecnico y que informacion necesita el equipo onshore.

# HERRAMIENTAS
Tienes 9 herramientas. Usalas cuando el operador lo pida o sea claramente necesario. \
Informa al operador antes de ejecutar cualquier herramienta.

| Herramienta | Uso |
|-------------|-----|
| `read_ticket(ticket_id)` | Leer ticket completo anonimizado del sistema origen |
| `read_attachment(ticket_id, attachment_index)` | Extraer texto anonimizado de adjuntos (PDF, Word, Excel, imagenes) |
| `update_ticket(ticket_id, comment, status)` | Anadir comentario y/o cambiar estado (`in_progress`, `delivered`, `done`) |
| `create_ticket(summary, description, priority)` | Crear ticket nuevo anonimizado |
| `search_tickets(jql_query, max_results)` | Buscar tickets con JQL. Usa `text ~ "termino tecnico"` |
| `execute_action(action, service, interval)` | Acciones tecnicas: `get_logs`, `check_status`, `restart_service`, `check_connectivity` |
| `add_worklog(ticket_id, time_spent, comment)` | Imputar horas (formato Jira: `"2h"`, `"1h 30m"`) |
| `get_worklogs(ticket_id)` | Consultar horas registradas |
| `delete_worklog(ticket_id, worklog_id)` | Eliminar worklog incorrecto |

**Busqueda de tickets relacionados — ejemplos JQL:**
- `text ~ "servidor no responde" ORDER BY created DESC`
- `text ~ "error 500" AND text ~ "API" ORDER BY created DESC`
- `text ~ "certificado" AND text ~ "SSL" ORDER BY created DESC`
- `text ~ "VPN" AND status in (Open, "In Progress") ORDER BY created DESC`

# FORMATO DE RESPUESTA
- **Siempre en espanol.** Directo y profesional.
- Usa Markdown: `##`/`###`, **negritas**, listas, bloques de codigo para logs.
- Tablas para datos comparables. Adapta el nivel tecnico al operador.
- No repitas informacion ya vista salvo que se pida.

# ACCIONES SUGERIDAS
Al final de **CADA** respuesta, incluye exactamente una linea con 2-4 acciones:

[CHIPS: "Accion 1", "Accion 2", "Accion 3"]

Reglas:
- Concretas y relevantes al momento de la conversacion
- Frases cortas (2-5 palabras)
- Sin tokens PII dentro de los chips
- **Incluye siempre "Buscar tickets relacionados"**

Ejemplos:
- Presentacion: `[CHIPS: "Ver detalles completos", "Buscar tickets relacionados", "Diagnosticar problema"]`
- Tras diagnostico: `[CHIPS: "Reiniciar servicio", "Buscar tickets relacionados", "Registrar avance"]`
- Tras accion: `[CHIPS: "Verificar estado actual", "Buscar tickets relacionados", "Cerrar ticket"]`"""


ANON_LLM_SYSTEM_PROMPT = """# ROL
Eres el **Agente de Anonimizacion** de una plataforma GDPR. Tu unica funcion es detectar \
datos personales (PII) que los detectores automaticos (regex + Presidio NLP) no captaron.

# ENTRADA
Recibes texto que ya ha pasado por un pipeline automatico de deteccion. Los datos personales \
detectados se han reemplazado por tokens `[TIPO_N]` (ej: `[PERSONA_1]`, `[EMAIL_2]`). \
Tu trabajo es encontrar PII **residual** que el pipeline no detecto.

NOTA: Es posible que los detectores regex y/o Presidio esten desactivados. En ese caso, \
el texto puede contener PII en claro que normalmente ya estaria tokenizada. \
Si ves datos personales reales sin tokenizar, DEBES marcarlos.

# RESPUESTA
Responde SOLO con JSON valido. Sin texto adicional, sin explicaciones, sin markdown.

Si encuentras PII no anonimizada:
{"found": [{"text": "dato encontrado", "type": "TIPO"}], "clean": false}

Si el texto esta limpio:
{"found": [], "clean": true}

Tipos validos para "type": PERSONA, EMAIL, TELEFONO, DNI, IP, IBAN, UBICACION, \
DIRECCION, TARJETA_CREDITO, MATRICULA, ORGANIZACION, DATO

# QUE BUSCAR (PII que el regex/Presidio suele fallar)

**Nombres propios** no tokenizados:
- Nombres completos en texto narrativo: "segun indica Martinez Garcia..."
- Nombres parciales con contexto: "el Sr. Perez", "Dna. Ana", "contactar con Luis"
- Nombres en firmas de email o comentarios

**Documentos de identidad** en formatos inusuales:
- `NI 23.452.321Y`, `D.N.I.: 12 345 678-Z`, `NIE: X-1234567-W`
- CIF/NIF con separadores: `B-12.345.678`

**Telefonos** no estandar:
- Con texto: "llamar al seis uno dos tres cuatro"
- Separados: `612-34-56-78`, `+34 (612) 345 678`
- Extensiones: "ext. 4521 preguntar por recepcion"

**Emails** ofuscados:
- `usuario [at] dominio [dot] com`, `usuario(arroba)empresa.es`

**Direcciones postales** parciales:
- "Calle Mayor 15, 3o B", "Avda. de la Constitucion s/n"
- Codigos postales sueltos junto a poblacion: "28001 Madrid"

**Datos en estructuras** (tablas, logs, CSV):
- PII dentro de campos tabulados que el regex no parsea bien
- Nombres o emails en lineas de log: `user=jgarcia@empresa.com action=login`

# QUE NO ES PII (CRITICO — no marcar como encontrado)
- **Tokens ya anonimizados** en CUALQUIER formato: `[PERSONA_1]`, `[EMAIL_3]`, `[ES_NIF_8]`, \
`[UBICACION_REDACTED]`, `[DNI_2]`, `[TELEFONO_1]`, etc. Todo texto entre corchetes con \
formato `[TIPO_N]` o `[TIPO_REDACTED]` es un token de anonimizacion, NO PII.
- Nombres de servidores, servicios o aplicaciones: `auth-server-01`, `PostgreSQL`
- IPs de redes internas: `10.x.x.x`, `192.168.x.x`, `172.16-31.x.x`
- Codigos tecnicos: `ERR_CONNECTION_REFUSED`, `HTTP 500`, `ORA-12541`
- Nombres de productos, frameworks o tecnologias: `SAP`, `SharePoint`, `Solution Manager`
- Codigos de transaccion SAP: `SE38`, `SE80`, `SM37`, etc.
- Fechas y timestamps
- Nombres de campos o etiquetas: "Nombre:", "Email:", "Telefono:"
- **Frases genericas de procedimiento**: "lineas de actuacion", "plan de accion", \
"verificar estado", "comprobar disponibilidad", "validar configuracion"
- **Verbos y sustantivos comunes**: "actuacion", "gestion", "configuracion", "validacion", etc.
- **Terminos de negocio/ITSM**: "incidencia", "requerimiento", "entregable", \
"documentacion tecnica", "repositorio documental"

# PRINCIPIO
Marca como PII solo datos que identifiquen o puedan identificar a una persona fisica. \
No marques terminologia tecnica, de negocio o frases genericas como PII."""


class AnonymizationLLM:
    """Small/fast LLM dedicated to PII validation. Optional enhancement over regex/Presidio."""

    def __init__(self, provider: str, model: str, temperature: float = 0.0, system_prompt: str = "", **kwargs):
        self.llm = AnonymizationAgent._create_llm(
            provider=provider, model=model, temperature=temperature, **kwargs
        )
        self._available = True
        self.system_prompt = system_prompt or ANON_LLM_SYSTEM_PROMPT
        logger.info("anon_llm_initialized", provider=provider, model=model)

    async def validate_pii(self, text: str) -> List[Dict]:
        """Run PII validation on text. Returns list of detected PII entities."""
        if not self._available:
            return []
        try:
            from langchain_core.messages import SystemMessage as SM, HumanMessage as HM
            response = await self.llm.ainvoke([
                SM(content=self.system_prompt),
                HM(content=f"Analiza este texto:\n\n{text}"),
            ])
            import json as _json
            result = _json.loads(response.content)
            return result.get("found", [])
        except Exception as e:
            logger.warning("anon_llm_validation_failed", error=str(e))
            return []

    # Regex to detect existing anonymization tokens — must NOT be treated as PII
    _TOKEN_PATTERN = re.compile(r'^\[[A-Z_]+_(?:\d+|REDACTED)\]$')

    async def filter_text(self, text: str, substitution_map: Dict[str, str]) -> str:
        """Enhanced PII filter: run LLM validation and replace any found PII."""
        found = await self.validate_pii(text)
        if not found:
            return text
        filtered = text
        for entity in found:
            pii_text = entity.get("text", "")
            pii_type = entity.get("type", "DATO")
            if not pii_text or pii_text not in filtered:
                continue

            # Skip if the LLM mistakenly flagged an existing anonymization token
            if self._TOKEN_PATTERN.match(pii_text):
                logger.debug("anon_llm_skipped_token", text=pii_text)
                continue

            # Check if it matches a known substitution value
            known_token = None
            for token, val in substitution_map.items():
                if val == pii_text:
                    known_token = token
                    break
            replacement = known_token or f"[{pii_type}_REDACTED]"
            filtered = filtered.replace(pii_text, replacement)
            logger.warning("anon_llm_pii_caught", type=pii_type, replacement=replacement)
        return filtered

    def update_llm(self, provider: str, model: str, temperature: float = 0.0, **kwargs):
        """Hot-reload the anonymization LLM."""
        self.llm = AnonymizationAgent._create_llm(
            provider=provider, model=model, temperature=temperature, **kwargs
        )
        logger.info("anon_llm_hot_reloaded", provider=provider, model=model)


class StreamingCallback(AsyncCallbackHandler):
    """Callback handler that collects tokens without streaming to client.

    Tokens are NOT sent to the frontend during generation to prevent
    showing unanonymized content. The complete, filtered response is
    sent only after post-LLM PII filtering via send_complete().
    """

    def __init__(self, ws_manager: ConnectionManager, client_id: str, ticket_id: int = None):
        self.ws_manager = ws_manager
        self.client_id = client_id
        self.ticket_id = ticket_id
        self.tokens: List[str] = []

    async def on_llm_new_token(self, token: str, **kwargs):
        self.tokens.append(token)

    def get_full_response(self) -> str:
        return "".join(self.tokens)


async def _invoke_with_heartbeat(
    llm, messages: list, config: dict,
    ws_manager, client_id: str, ticket_id: int,
    interval: int = 10,
):
    """Invoke LLM while sending periodic WS heartbeats to survive proxy timeouts."""

    async def _heartbeat():
        while True:
            await asyncio.sleep(interval)
            try:
                await ws_manager.send_heartbeat(client_id, ticket_id)
            except Exception:
                break

    task = asyncio.create_task(_heartbeat())
    try:
        return await llm.ainvoke(messages, config=config)
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


class AnonymizationAgent:
    """LangChain agent with anonymization pipeline (Resolution Agent)."""

    def __init__(
        self,
        anonymizer: Anonymizer,
        db: DatabaseService,
        ws_manager: ConnectionManager,
        anon_llm: Optional["AnonymizationLLM"] = None,
    ):
        self.anonymizer = anonymizer
        self.db = db
        self.ws_manager = ws_manager
        self.anon_llm = anon_llm
        self._map_cache: Dict[int, Dict[str, str]] = {}
        self._map_cache_max = 50

        # Initialize LLM based on provider
        self.llm = self._create_llm()
        logger.info("resolution_llm_initialized", provider=settings.llm_provider)
        if anon_llm:
            logger.info("anon_llm_attached")

        # Tools — keep all_tools for toggling, tools for active set
        self.all_tools = [
            read_ticket, read_attachment, update_ticket, create_ticket,
            search_tickets, add_worklog, get_worklogs, delete_worklog,
            execute_action,
        ]
        self.tools = list(self.all_tools)

    @staticmethod
    def _create_llm(provider: str = None, model: str = None, temperature: float = None, **kwargs):
        """Create LLM instance based on configured provider."""
        provider = (provider or settings.llm_provider).lower()
        temperature = temperature if temperature is not None else 0.3

        if provider == "ollama":
            from langchain_ollama import ChatOllama
            return ChatOllama(
                base_url=kwargs.get("ollama_base_url", settings.ollama_base_url),
                model=model or settings.ollama_model,
                temperature=temperature,
            )
        elif provider == "openai":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                api_key=kwargs.get("openai_api_key", settings.openai_api_key),
                model=model or settings.openai_model,
                temperature=temperature,
                streaming=True,
            )
        elif provider == "axet":
            import httpx
            from langchain_openai import ChatOpenAI
            from ..routers.axet_auth import get_token_or_setting, _token_store
            project_id = kwargs.get("axet_project_id", settings.axet_project_id)
            if not project_id:
                raise ValueError("Axet project_id no configurado. Selecciona un proyecto en la configuracion.")
            bearer_token = kwargs.get("axet_bearer_token") or get_token_or_setting()
            if not bearer_token:
                raise ValueError("Axet bearer token no disponible. Inicia sesion con OKTA.")
            asset_id = kwargs.get("axet_asset_id", settings.axet_asset_id)
            base_url = f"https://axet.nttdata.com/api/llm-enabler/v2/openai/ntt/{project_id}/v1"
            default_headers = {
                "Authorization": f"Bearer {bearer_token}",
                "axet-asset-id": asset_id,
            }
            # Add user ID if available from OAuth
            user_info = _token_store.get("user_info")
            if user_info and user_info.get("id"):
                default_headers["axet-user-id"] = user_info["id"]
            http_client = httpx.Client(verify=False)
            async_http_client = httpx.AsyncClient(verify=False)
            return ChatOpenAI(
                api_key="dummy-key",
                base_url=base_url,
                default_headers=default_headers,
                http_client=http_client,
                http_async_client=async_http_client,
                model=model or settings.axet_model,
                temperature=temperature,
                streaming=True,
            )
        else:
            raise ValueError(f"Unknown LLM provider: {provider}. Use 'ollama', 'azure', 'openai', or 'axet'")

    def update_llm(self, provider: str, model: str, temperature: float = 0.3, **kwargs):
        """Hot-reload: recreate the LLM instance with new config."""
        self.llm = self._create_llm(provider=provider, model=model, temperature=temperature, **kwargs)
        logger.info("llm_hot_reloaded", provider=provider, model=model, temperature=temperature)

    def set_active_tools(self, tool_states: Dict[str, bool]):
        """Hot-reload: filter active tools based on name→enabled mapping."""
        self.tools = [t for t in self.all_tools if tool_states.get(t.name, True)]
        logger.info("tools_hot_reloaded", active=[t.name for t in self.tools])

    def _get_system_prompt(self) -> str:
        """Get current system prompt from app_state or fallback to default."""
        from ..main import app_state
        return app_state.get("system_prompt", DEFAULT_SYSTEM_PROMPT)

    def _build_messages(
        self, chat_history: List[Dict], user_message: str,
        ticket_context: Optional[Dict] = None,
    ) -> List:
        """Build message list from chat history and new message."""
        messages = [SystemMessage(content=self._get_system_prompt())]

        if ticket_context:
            context_msg = (
                "Contexto del ticket activo:\n"
                f"- Ticket origen (sistema fuente): {ticket_context.get('source_ticket_id', 'N/A')}\n"
                f"- Ticket anonimizado (KOSIN destino): {ticket_context.get('kosin_ticket_id', 'N/A')}\n"
                f"- Sistema fuente: {ticket_context.get('source_system', 'N/A')}\n"
                f"- Estado: {ticket_context.get('status', 'N/A')}\n"
                f"- Prioridad: {ticket_context.get('priority', 'N/A')}\n"
                "Usa estos IDs cuando necesites leer, actualizar o comentar en los tickets. "
                "No necesites pedir estos datos al operador."
            )
            messages.append(SystemMessage(content=context_msg))

        for msg in chat_history:
            if msg["role"] == "operator":
                messages.append(HumanMessage(content=msg["message"]))
            else:
                messages.append(AIMessage(content=msg["message"]))

        messages.append(HumanMessage(content=user_message))
        return messages

    async def _get_substitution_map(self, ticket_id: int) -> Dict[str, str]:
        """Reconstruct substitution map on-the-fly from the source ticket.

        No data is persisted in DB. The map is cached in memory per session.

        IMPORTANT: Always uses a full CompositeDetector for reconstruction,
        regardless of the currently active detector. This ensures the map
        matches what was generated during ingest even if the user later
        disables regex or Presidio.
        """
        # Check in-memory cache first
        if ticket_id in self._map_cache:
            return self._map_cache[ticket_id]

        ticket = await self.db.get_ticket(ticket_id)
        if not ticket:
            return {}

        source_ticket_id = ticket["source_ticket_id"]

        # Resolve source connector
        from ..main import app_state
        connector_router = app_state.get("connector_router")
        if connector_router:
            try:
                _, source_connector = connector_router.get_connector(source_ticket_id)
            except ValueError:
                source_connector = app_state.get("jira_connector")
        else:
            source_connector = app_state.get("jira_connector")

        if not source_connector:
            logger.error("no_source_connector", ticket_id=ticket_id)
            return {}

        try:
            # Re-read original ticket from source
            source_ticket = await source_connector.get_ticket(source_ticket_id)
            comments = await source_connector.get_comments(source_ticket_id)

            # Assemble text EXACTLY as done during ingest
            full_text = Anonymizer.assemble_ingest_text(
                source_ticket.get("summary", ""),
                source_ticket.get("description", "") or "",
                comments,
            )

            # Check for source changes via hash
            stored_hash = ticket.get("source_text_hash", "")
            current_hash = Anonymizer.compute_text_hash(full_text)
            if stored_hash and stored_hash != current_hash:
                logger.warning(
                    "source_text_changed",
                    ticket_id=ticket_id,
                    source_key=source_ticket_id,
                    hint="Source ticket modified since ingest, tokens may differ",
                )

            # Reconstruct map using the SAME detector type that was active during ingest.
            # If we reconstruct with a different detector we get different tokens → mismatch.
            from .detection import CompositeDetector, NullDetector
            try:
                # Load anonymization config from DB
                anon_config = None
                try:
                    row = await self.db.get_system_config("anonymization")
                    if row and row.get("extra_config"):
                        import json
                        raw = row["extra_config"]
                        anon_config = json.loads(raw) if isinstance(raw, str) else raw
                except Exception:
                    pass

                detector_type = (anon_config or {}).get("detector_type", "composite").lower()
                presidio_cfg = {}
                if anon_config:
                    presidio_cfg = {
                        "score_threshold": anon_config.get("presidio_sensitivity", 65),
                        "enabled_entities": anon_config.get("presidio_entities"),
                        "excluded_words": anon_config.get("presidio_excluded_words"),
                        "min_lengths": anon_config.get("presidio_min_lengths"),
                        "model_name": anon_config.get("presidio_model", "es_core_news_lg"),
                    }

                from ..routers.config import _create_detector
                reconstruction_detector = _create_detector(detector_type, presidio_config=presidio_cfg)
            except Exception as e:
                logger.warning("reconstruction_detector_failed", error=str(e),
                               fallback="current_detector")
                reconstruction_detector = self.anonymizer._detector

            reconstruction_anonymizer = Anonymizer(detector=reconstruction_detector)
            sub_map = reconstruction_anonymizer.reconstruct_map(full_text)

            # Cache (evict oldest if full)
            if len(self._map_cache) >= self._map_cache_max:
                oldest_key = next(iter(self._map_cache))
                del self._map_cache[oldest_key]
            self._map_cache[ticket_id] = sub_map

            return sub_map

        except Exception as e:
            logger.error("reconstruct_map_failed", ticket_id=ticket_id, error=str(e))
            return {}

    def invalidate_map_cache(self, ticket_id: int = None):
        """Invalidate cached substitution map(s)."""
        if ticket_id:
            self._map_cache.pop(ticket_id, None)
        else:
            self._map_cache.clear()

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
        # 1. Load substitution map and ticket context
        sub_map = await self._get_substitution_map(ticket_id)
        ticket = await self.db.get_ticket(ticket_id)

        # Expose sub_map in app_state so tools (read_ticket, etc.) can apply it
        from ..main import app_state
        app_state["active_sub_map"] = sub_map

        # 2. PRE-filter: anonymize user input (regex + optional LLM)
        filtered_message = self.anonymizer.filter_output(user_message, sub_map)
        if self.anon_llm:
            filtered_message = await self.anon_llm.filter_text(filtered_message, sub_map)

        # 3. Load chat history
        history = await self.db.get_chat_history(ticket_id)

        # Save operator message
        await self.db.add_chat_message(ticket_id, "operator", filtered_message)

        # 4. Build messages and invoke LLM
        messages = self._build_messages(history, filtered_message, ticket_context=ticket)

        streaming_cb = StreamingCallback(self.ws_manager, client_id, ticket_id)

        try:
            # Use LLM with tools via bind_tools
            llm_with_tools = self.llm.bind_tools(self.tools)

            response = await _invoke_with_heartbeat(
                llm_with_tools, messages,
                {"callbacks": [streaming_cb]},
                self.ws_manager, client_id, ticket_id,
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
                final_response = await _invoke_with_heartbeat(
                    self.llm, messages,
                    {"callbacks": [streaming_cb2]},
                    self.ws_manager, client_id, ticket_id,
                )
                agent_text = final_response.content
            else:
                agent_text = response.content

        except Exception as e:
            logger.error("agent_error", error=str(e), ticket_id=ticket_id)
            agent_text = f"Error al procesar la solicitud. Por favor, intenta de nuevo."
            await self.ws_manager.send_error(client_id, agent_text, ticket_id)
            return agent_text

        # 5. POST-filter: scan response for PII leaks (regex + optional LLM)
        filtered_response = self.anonymizer.filter_output(agent_text, sub_map)
        if self.anon_llm:
            filtered_response = await self.anon_llm.filter_text(filtered_response, sub_map)

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
            f"Ticket origen: {ticket['source_ticket_id']}\n"
            f"Referencia KOSIN: {ticket['kosin_ticket_id']}\n"
            f"Resumen: {ticket['summary']}\n"
            f"Descripcion anonimizada:\n{ticket['anonymized_description']}\n"
            f"Estado: {ticket['status']}\n"
            f"Prioridad: {ticket['priority']}\n\n"
            f"Recuerda: usa solo los tokens de anonimizacion, nunca inventes datos personales."
        )

        # Build messages with history context
        messages = [SystemMessage(content=self._get_system_prompt())]
        for msg in history:
            if msg["role"] == "operator":
                messages.append(HumanMessage(content=msg["message"]))
            else:
                messages.append(AIMessage(content=msg["message"]))
        messages.append(HumanMessage(content=prompt))

        streaming_cb = StreamingCallback(self.ws_manager, client_id, ticket_id)

        try:
            response = await _invoke_with_heartbeat(
                self.llm, messages,
                {"callbacks": [streaming_cb]},
                self.ws_manager, client_id, ticket_id,
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
