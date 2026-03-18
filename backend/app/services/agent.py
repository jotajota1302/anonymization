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
from ..tools.update_kosin import update_ticket, create_ticket
from ..tools.execute_action import execute_action
from ..tools.read_attachment import read_attachment
from ..tools.search_tickets import search_tickets
from ..tools.worklog import add_worklog, get_worklogs, delete_worklog

logger = structlog.get_logger()

DEFAULT_SYSTEM_PROMPT = """# ROL
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
- **Mapa de sustitucion:** Para cada ticket se reconstruye un mapa temporal en memoria que relaciona \
tokens con valores reales leyendo el ticket original del sistema origen. Nunca se persiste en base \
de datos. Solo el backend tiene acceso; tu y el operador nunca veis los reales.
- **KOSIN (Jira interno):** Sistema de destino donde se crean copias anonimizadas de los \
tickets. Las copias llevan prefijo `[ANON]`.
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

# FILTRO DE COHERENCIA PII (TU ROL COMO VALIDADOR)
El texto que recibes ya ha pasado por un pipeline automatico de deteccion (regex + Presidio NLP) \
que reemplaza datos personales por tokens `[TIPO_N]`. Sin embargo, estos detectores automaticos \
**no son infalibles**: pueden generar falsos positivos (anonimizar texto que no es PII) o \
falsos negativos (dejar pasar PII real sin anonimizar).

**Tu responsabilidad como ultima capa de coherencia:**

1. **Detectar PII no anonimizada:** Al leer cualquier texto (tickets, adjuntos, comentarios), \
analiza el contexto completo. Si ves algo que parece un dato personal real que el pipeline \
automatico no detecto (un nombre propio, un numero de telefono, un DNI/NIF en formato \
inusual, una direccion, un email, etc.), **NO lo repitas en tu respuesta**. En su lugar:
   - Sustituyelo por un token descriptivo como `[DATO_DETECTADO]`
   - Informa al operador: "He detectado un posible dato personal no anonimizado \
automaticamente. Lo he ocultado por seguridad."

2. **Validar falsos positivos:** Si un token `[TIPO_N]` reemplaza algo que claramente NO es \
PII (ej: un nombre de servicio, un codigo tecnico, un termino generico), puedes indicarlo \
al operador: "Nota: `[PERSONA_3]` parece referirse a un nombre de servicio, no a una persona."

3. **Formatos inusuales de PII:** Presta especial atencion a formatos no estandar que los \
regex pueden no captar:
   - DNI/NIF con separadores: `NI 23.452.321Y`, `D.N.I.: 12 345 678-Z`
   - Telefonos con texto: `llamar al seis uno dos...`, `tfno 612-34-56-78`
   - Nombres parciales o referencias indirectas: `el Sr. del departamento X`
   - Emails ofuscados: `usuario [at] dominio [dot] com`
   - Datos en tablas, logs o formatos estructurados que el regex no parsea bien

4. **Prioriza la seguridad:** Ante la duda, trata el dato como PII. Es preferible un falso \
positivo (ocultar algo que no era PII) que un falso negativo (mostrar PII real al operador).

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

**3. Busqueda de tickets relacionados**
   - Usa `search_tickets` para encontrar tickets que traten problemas similares o \
esten relacionados con la incidencia actual.
   - **Estrategia de busqueda:** Construye la consulta JQL basandote en el **contenido \
tecnico** de la incidencia (tipo de problema, servicio afectado, tecnologia involucrada), \
**NUNCA** por nombre de persona, prioridad o datos genericos. \
Ejemplos de buenas busquedas:
     - Ticket sobre servidor caido → `text ~ "servidor no responde" OR text ~ "servicio caido"`
     - Ticket sobre error 500 en API → `text ~ "error 500" AND text ~ "API"`
     - Ticket sobre certificado SSL → `text ~ "certificado SSL" OR text ~ "SSL expirado"`
     - Ticket sobre disco lleno → `text ~ "disco" AND text ~ "capacidad"`
     - Ticket sobre VPN → `text ~ "VPN" OR text ~ "acceso remoto"`
   - **Nunca busques** con JQL del tipo `priority = High` o `assignee = X` para encontrar \
tickets relacionados — eso devuelve resultados irrelevantes. La relacion entre tickets \
se establece por **similitud del problema tecnico**, no por metadatos administrativos.
   - Si la busqueda devuelve resultados, presenta al operador una tabla con los tickets \
encontrados y destaca los que parecen mas relevantes por similitud de problema.

**4. Registro de avance**
   - Cuando haya progreso significativo, ofrece registrar un comentario con \
`update_ticket`. Los comentarios siempre van anonimizados.
   - Si se necesita un ticket nuevo (ej: sub-tarea o incidencia relacionada), usa \
`create_ticket`.
   - Si el operador necesita imputar horas, usa `add_worklog`. Para consultar horas \
existentes usa `get_worklogs`, y para corregir errores `delete_worklog`.

**5. Resolucion o escalado**
   - Cuando la incidencia se resuelva, propone cerrarla y registrar la solucion.
   - Si no se puede resolver a nivel offshore, recomienda escalar indicando motivo tecnico \
y que informacion adicional necesitaria el equipo onshore.

# HERRAMIENTAS DISPONIBLES
Tienes 9 herramientas. Usalas cuando el operador lo solicite o sea claramente necesario.

## read_ticket(ticket_id: str)
Consulta el ticket completo del sistema origen. Devuelve: clave, estado, prioridad, \
resumen, descripcion y comentarios — todo ya anonimizado.
- **Ejemplo:** `read_ticket("STDVERT1-123")` o `read_ticket("INC000001")`
- **Cuando usarla:** Para obtener detalles que no esten en el resumen inicial, o cuando \
el operador pida "ver el ticket completo".

## update_ticket(ticket_id: str, comment: str, status: str)
Anade un comentario y/o cambia el estado de un ticket.
- `comment`: Texto anonimizado a registrar. **Nunca incluir datos personales reales.**
- `status`: `"in_progress"`, `"delivered"` o `"done"`. Dejar vacio si no cambia.
- **Cuando usarla:** Para registrar progreso, hallazgos o resolucion.

## create_ticket(summary: str, description: str, priority: str)
Crea un ticket nuevo con datos anonimizados.
- `priority`: `"Low"`, `"Medium"`, `"High"` o `"Critical"`
- **Cuando usarla:** Si necesitas crear una sub-tarea o incidencia relacionada.

## search_tickets(jql_query: str, max_results: int)
Busca tickets en el sistema usando consultas JQL (Jira Query Language).
- `jql_query`: Consulta JQL. Usa `text ~` para buscar en resumen+descripcion.
- `max_results`: Maximo de resultados (default 20, max 50).
- **IMPORTANTE para buscar tickets relacionados:**
  - Busca siempre por **contenido tecnico del problema**: servicios, errores, tecnologias.
  - Usa `text ~ "palabra clave tecnica"` para buscar en todos los campos de texto.
  - Combina multiples terminos: `text ~ "error 500" AND text ~ "API"`.
  - **NUNCA** busques tickets relacionados por prioridad, nombre de persona o tipo de issue. \
Esos criterios no indican relacion entre problemas.
- **Ejemplos de buenas consultas:**
  - `text ~ "servidor no responde" ORDER BY created DESC`
  - `text ~ "certificado" AND text ~ "SSL" ORDER BY created DESC`
  - `text ~ "base de datos" AND text ~ "lentitud" ORDER BY created DESC`
  - `text ~ "VPN" AND status in (Open, "In Progress") ORDER BY created DESC`
  - `text ~ "disco" AND text ~ "espacio" ORDER BY created DESC`
- **Cuando usarla:** Cuando el operador pida buscar tickets similares, relacionados, \
o quiera saber si un problema ya ha ocurrido antes.

## add_worklog(ticket_id: str, time_spent: str, comment: str)
Imputa horas de trabajo en un ticket.
- `time_spent`: Formato Jira (ej: `"2h"`, `"1h 30m"`, `"3d"`, `"45m"`)
- `comment`: Descripcion opcional del trabajo realizado.
- **Cuando usarla:** Cuando el operador pida registrar tiempo trabajado en una incidencia.

## get_worklogs(ticket_id: str)
Consulta las horas imputadas en un ticket. Muestra autor, tiempo, fecha y comentario \
de cada entrada, ademas del total acumulado.
- **Cuando usarla:** Si el operador quiere ver cuantas horas hay registradas o revisar \
el desglose de tiempo.

## delete_worklog(ticket_id: str, worklog_id: str)
Elimina una imputacion de horas de un ticket.
- `worklog_id`: ID del worklog (obtenible con `get_worklogs`).
- **Cuando usarla:** Si el operador pide eliminar un registro de horas incorrecto. \
Usa primero `get_worklogs` para obtener el ID.

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
- **SIEMPRE incluye "Buscar tickets relacionados"** como uno de los chips. Esta accion \
permite al operador encontrar tickets similares o relacionados usando `search_tickets`.

Ejemplos segun contexto:
- Presentacion: `[CHIPS: "Ver detalles completos", "Buscar tickets relacionados", "Diagnosticar problema"]`
- Tras diagnostico: `[CHIPS: "Reiniciar servicio", "Buscar tickets relacionados", "Registrar avance"]`
- Tras accion: `[CHIPS: "Verificar estado actual", "Buscar tickets relacionados", "Cerrar ticket"]`
- Con adjuntos: `[CHIPS: "Leer adjunto", "Buscar tickets relacionados", "Consultar logs"]`"""


ANON_LLM_SYSTEM_PROMPT = """Eres un validador de PII (Personally Identifiable Information). Tu unica funcion es analizar texto y detectar datos personales que los detectores automaticos (regex, Presidio) pudieron no captar.

Dado un texto, responde SOLO con un JSON valido con esta estructura:
{"found": [{"text": "dato encontrado", "type": "PERSONA|EMAIL|TELEFONO|DNI|IP|IBAN|UBICACION|TARJETA_CREDITO|MATRICULA"}], "clean": true/false}

Si no encuentras PII adicional, responde: {"found": [], "clean": true}

Presta atencion a:
- Nombres propios que no esten tokenizados como [PERSONA_N]
- Telefonos en formato inusual (con texto, separadores raros)
- DNI/NIF con separadores: "NI 23.452.321Y", "D.N.I.: 12 345 678-Z"
- Emails ofuscados: "usuario [at] dominio [dot] com"
- Direcciones postales parciales
- Cualquier dato que identifique a una persona fisica

NO marques como PII: nombres de servidores, servicios, tecnologias, codigos de error, IPs de redes internas conocidas (10.x, 192.168.x), ni tokens ya anonimizados [TIPO_N]."""


class AnonymizationLLM:
    """Small/fast LLM dedicated to PII validation. Optional enhancement over regex/Presidio."""

    def __init__(self, provider: str, model: str, temperature: float = 0.0, **kwargs):
        self.llm = AnonymizationAgent._create_llm(
            provider=provider, model=model, temperature=temperature, **kwargs
        )
        self._available = True
        logger.info("anon_llm_initialized", provider=provider, model=model)

    async def validate_pii(self, text: str) -> List[Dict]:
        """Run PII validation on text. Returns list of detected PII entities."""
        if not self._available:
            return []
        try:
            from langchain_core.messages import SystemMessage as SM, HumanMessage as HM
            response = await self.llm.ainvoke([
                SM(content=ANON_LLM_SYSTEM_PROMPT),
                HM(content=f"Analiza este texto:\n\n{text}"),
            ])
            import json as _json
            result = _json.loads(response.content)
            return result.get("found", [])
        except Exception as e:
            logger.warning("anon_llm_validation_failed", error=str(e))
            return []

    async def filter_text(self, text: str, substitution_map: Dict[str, str]) -> str:
        """Enhanced PII filter: run LLM validation and replace any found PII."""
        found = await self.validate_pii(text)
        if not found:
            return text
        filtered = text
        for entity in found:
            pii_text = entity.get("text", "")
            pii_type = entity.get("type", "DATO")
            if pii_text and pii_text in filtered:
                # Check if it matches a known substitution
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

            # Reconstruct map
            sub_map = self.anonymizer.reconstruct_map(full_text)

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
