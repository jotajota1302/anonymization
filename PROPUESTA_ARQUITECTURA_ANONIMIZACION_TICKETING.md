# Propuesta de Arquitectura: Plataforma de Anonimizacion de Ticketing

**Version:** 1.2
**Fecha original:** 13 de Marzo de 2026
**Ultima actualizacion:** 14 de Marzo de 2026
**Equipo:** NTT DATA EMEAL
**Estado:** Piloto implementado con sync_to_client, adjuntos y tests — pendiente validacion (Fase 4)

---

## 1. Contexto y Problema

### 1.1 Situacion Actual

Los equipos offshore (trabajadores en otros paises) necesitan gestionar tickets de soporte de clientes, pero la normativa GDPR/RGPD impide que accedan a datos personales contenidos en dichos tickets (nombres, emails, telefonos, DNIs, direcciones, IPs, etc.).

### 1.2 Objetivo

Crear una plataforma que permita a los operadores offshore trabajar con tickets de clientes **sin acceder nunca a datos personales**, manteniendo la capacidad operativa completa para resolver incidencias.

### 1.3 Solucion Propuesta

Una **plataforma de intermediacion con anonimización controlada** en la que un agente de IA
asiste al operador offshore sin exponerle datos personales.

- El **backend y los conectores** son las unicas capas con acceso a los datos reales del ticket
- El operador trabaja **siempre sobre una vista anonimizada**
- El agente consulta informacion tecnica y propone o ejecuta acciones dentro de un catalogo controlado
- Todo el trabajo operativo se registra en un sistema interno (KOSIN) en version anonimizada

La barrera GDPR no depende solo del prompt del agente: depende de una combinacion de
anonimizacion previa, control de herramientas, filtro de salida, auditoria y escalado a onshore
cuando no se puede garantizar seguridad suficiente.

---

## 2. Arquitectura General

### 2.1 Vision de Alto Nivel

```
 KOSIN (Jira interno)              PLATAFORMA DE ANONIMIZACION                    OPERADOR
 Proyecto PESESG                                                                  OFFSHORE

                        ┌──────────────────────────────────────────────┐
 ┌─────────────┐        │                                              │   ┌──────────────┐
 │             │        │  1. CONECTORES         2. ANONYMIZER         │   │              │
 │  Ticket     │◄──────►│  ┌──────────────┐      ┌─────────────────┐   │   │  Interfaz    │
 │  con PII    │        │  │ KOSIN source │─────►│ RegexDetector   │   │   │  de Chat     │
 │  (PESESG-*) │        │  │ KOSIN dest.  │      │ Mapa sustitucion│   │   │  (Next.js)   │
 └─────────────┘        │  └──────────────┘      │ Filtro salida   │   │   │              │
                        │        ▲               └────────┬────────┘   │   │  Solo ve     │
                        │        │                        │            │   │  datos       │
                        │        │                        ▼            │   │  anonimizados│
                        │  3. AGENTE LANGCHAIN (Ollama / Azure OpenAI) │   │              │
                        │  ┌──────────────────────────────────────┐    │   └──────┬───────┘
                        │  │ System prompt anonimizador           │    │          │
                        │  │ Tools (allowlist):                   │◄───┼──────────┘
                        │  │   read_ticket · update_kosin         │    │   WebSocket
                        │  │   create_kosin_ticket · exec_action  │    │   (streaming)
                        │  │ Historial por ticket (SQLite)        │    │
                        │  └──────────────────┬───────────────────┘    │
                        │                     │                        │
                        │                     ▼                        │
                        │  ┌──────────────────────────────────────┐    │
                        │  │  KOSIN (Jira interno) — destino      │    │
                        │  │  Ticket VOLCADO [ANON] + audit log   │    │
                        │  └──────────────────────────────────────┘    │
                        │                                              │
                        │  4. ESCALADO ONSHORE (pendiente)             │
                        │  Si no se puede anonimizar con confianza     │
                        │  → bloqueo + derivacion a supervisor         │
                        └──────────────────────────────────────────────┘

 Flujo de datos PII:
 Ticket real → Conectores → Anonymizer (regex + tokens) → Agente (ve tokens) → Operador (ve tokens)
                                                           ▲
                                                           │ Las acciones tecnicas se ejecutan
                                                           │ via tools controladas (simuladas en piloto),
                                                           │ pero el resultado se anonimiza antes
                                                           │ de mostrarse al operador.
```

**Nota POC:** En el piloto, la misma instancia KOSIN (proyecto PESESG) actua como origen y destino.
Los tickets originales se leen del board KOSIN, y las copias anonimizadas se crean como
Sub-Requirements con prefijo `[ANON]` bajo un ticket padre configurado (`KOSIN_PARENT_KEY`).

### 2.2 Principio Fundamental

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│   El operador NUNCA accede a datos reales.                       │
│   El agente IA es la UNICA entidad que lee datos PII.            │
│   Toda comunicacion hacia el operador pasa por anonimizacion.    │
│   Toda accion tecnica la ejecuta el agente con datos reales.     │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**Aclaracion de arquitectura:** Aunque el diagrama simplifica el flujo hablando del agente,
en la implementacion real el acceso a PII en claro queda restringido a backend y conectores.
El LLM trabaja por defecto con contexto ya anonimizado y las acciones tecnicas se ejecutan
mediante herramientas controladas y auditadas.

### 2.3 Arquitectura de Componentes (Implementada)

```
┌─────────────────────────────────────────────────────────────────┐
│                FRONTEND (Next.js 14 + TypeScript + Tailwind)     │
│                                                                  │
│  ┌────────────────────┐  ┌───────────────────────────────────┐   │
│  │  Panel de Tickets  │  │         Panel de Chat             │   │
│  │                    │  │                                   │   │
│  │  PENDIENTES:       │  │  Conversacion con el agente IA   │   │
│  │  Tickets del board │  │  sobre el ticket seleccionado.   │   │
│  │  KOSIN aun no      │  │  Toda informacion mostrada esta  │   │
│  │  ingestados.       │  │  anonimizada.                    │   │
│  │                    │  │                                   │   │
│  │  EN ATENCION:      │  │  El operador puede:              │   │
│  │  Tickets ya        │  │  - Preguntar sobre el ticket     │   │
│  │  anonimizados e    │  │  - Dar instrucciones al agente   │   │
│  │  ingestados.       │  │  - Usar chips de accion sugerida │   │
│  │                    │  │  - Finalizar ticket               │   │
│  │  Cada ticket:      │  │                                   │   │
│  │  - ID KOSIN        │  │  Chips de accion sugerida:       │   │
│  │  - Resumen anonim. │  │  Botones clickeables que el      │   │
│  │  - Estado          │  │  agente sugiere al final de cada │   │
│  │  - Prioridad       │  │  respuesta via [CHIPS: "..."]    │   │
│  └────────────────────┘  └───────────────────────────────────┘   │
│                                                                  │
│  Estado global: Zustand (appStore.ts)                            │
│  Comunicacion: fetch() + useWebSocket hook                       │
└──────────────────────────────────┬───────────────────────────────┘
                                   │ REST + WebSocket (streaming)
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                     BACKEND (Python + FastAPI)                   │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │          Routers (tickets.py + chat.py)                    │   │
│  │                                                           │   │
│  │  La logica de ingesta se implementa directamente en los   │   │
│  │  endpoints del router (no hay orchestrator separado):     │   │
│  │  1. Operador selecciona ticket del board KOSIN            │   │
│  │  2. Endpoint ingest-confirm lee ticket + comentarios      │   │
│  │  3. Anonymizer detecta PII y genera mapa de sustitucion   │   │
│  │  4. Se crea ticket VOLCADO [ANON] en KOSIN como sub-req   │   │
│  │  5. Se guarda mapping + mapa cifrado + descripcion anon.  │   │
│  │  6. Chat via WebSocket con streaming de tokens             │   │
│  └───────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌───────────────────────────────┐  ┌──────────────────────┐   │
│  │  Agente LangChain             │  │  Conectores          │   │
│  │  (Ollama local / Azure)       │  │                      │   │
│  │                               │  │  - KOSIN (origen     │   │
│  │  System prompt anonimizador   │  │    y destino en POC) │   │
│  │  + Tools:                     │  │  - Jira (mock o      │   │
│  │    - read_ticket              │  │    real via httpx)    │   │
│  │    - create_kosin_ticket      │  │                      │   │
│  │    - update_kosin             │  │  Interfaz abstracta  │   │
│  │    - execute_action           │  │  TicketConnector      │   │
│  │  + Historial manual desde DB  │  │  (plug & play)       │   │
│  │  + RegexDetector pre/post     │  │                      │   │
│  │  + Chips de accion sugerida   │  │                      │   │
│  └───────────────────────────────┘  └──────────────────────┘   │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │                  SQLite (Piloto)                           │   │
│  │                                                           │   │
│  │  - ticket_mapping (+ summary, description, priority)      │   │
│  │  - substitution_map (cifrado AES-256-GCM)                 │   │
│  │  - chat_history (mensajes anonimizados)                   │   │
│  │  - audit_log (acciones registradas)                       │   │
│  └───────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

**Diferencias respecto a la propuesta original:**

| Aspecto | Propuesta v1.0 | Implementacion real |
|---|---|---|
| Orquestador | `services/orchestrator.py` dedicado | Logica distribuida en `routers/tickets.py` |
| Ingesta | Automatica (webhook/polling) | Manual: operador confirma desde el board |
| Frontend | React + TypeScript | Next.js 14 App Router + TypeScript |
| LLM | Solo Azure OpenAI | Configurable: Ollama (dev) / Azure (prod) |
| Conector Jira | Libreria `jira` (Atlassian) | `httpx` directo contra Jira REST API v2 |
| Memory agente | `ConversationBufferMemory` (LangChain) | Historial manual cargado desde SQLite |
| Modelos datos | 3 archivos (`database.py`, `ticket.py`, `chat.py`) | 1 archivo `schemas.py` (Pydantic) |
| Crypto/PII filter | Archivos separados en `utils/` | Integrados en `anonymizer.py` |
| Tool `sync_to_client` | Planificada | ✅ **Implementada** (endpoint + de_anonymize + frontend) |
| Volcado inverso a cliente | Planificado (flujo 3.3) | ✅ **Implementado** via sync_to_client |
| Autenticacion JWT | Planificada (Fase 4) | **No implementada** |
| Docker Compose / Dockerfile | Planificados | **No creados** |
| Tests | Planificados | ✅ **35 tests pytest** (anonymizer, attachments, roundtrip) |
| Rate limiter | Planificado | ✅ **Registrado** en app (RateLimiterMiddleware) |
| DetectionService abstracta | Planificada (interfaz) | ✅ **Implementada** (ABC + RegexDetector + AttachmentDetector) |
| Adjuntos (PDF, OCR, Office) | Planificados para fase 2 | ✅ **Implementados** (AttachmentProcessor + tool read_attachment) |
| Chips de accion | No planificados | **Anadidos** — UX significativa |
| Board view (tickets pendientes) | No planificado | **Anadido** — flujo de ingesta manual |

---

## 3. Flujos Principales

### 3.1 Ingesta de Ticket (Implementado)

```
1. Board KOSIN muestra tickets abiertos del proyecto PESESG
   (polling cada 60 segundos desde frontend)
              │
              ▼
2. Operador selecciona un ticket pendiente del board
   Se muestra panel de confirmacion: "Atender esta incidencia"
              │
              ▼
3. Operador confirma → POST /api/tickets/ingest-confirm/{kosin_key}
   Backend lee ticket completo + comentarios via KosinConnector
              │
              ▼
4. Texto del ticket pasa por Anonymizer (RegexDetector)
   Piloto: emails, DNIs, telefonos, IPs (v4), IBANs, nombres
              │
              ▼
5. Se genera mapa de sustitucion:
   {"PERSONA_1": "Juan Garcia", "EMAIL_1": "juan@acme.com", ...}
   Se cifra con AES-256-GCM y se almacena en substitution_map
              │
              ▼
6. Se crea ticket VOLCADO en KOSIN como Sub-Requirement:
   - Prefijo "[ANON]" en el summary
   - Sub-tarea bajo el parent configurado (KOSIN_PARENT_KEY)
   - Descripcion anonimizada
              │
              ▼
7. Se guarda en ticket_mapping (source_key, kosin_key, summary, etc.)
   El ticket aparece en la seccion "En atencion" del panel
              │
              ▼
8. Se genera resumen inicial automatico via el agente
```

**Diferencia con propuesta v1.0:** La ingesta era automatica (webhook/polling desde backend).
En la implementacion el operador la inicia manualmente desde el board, lo cual da mas control
y evita anonimizar tickets que nadie va a atender.

### 3.2 Trabajo del Operador (Chat con Agente) — Implementado

```
OPERADOR selecciona ticket en "En atencion"
              │
              ▼
AGENTE genera resumen inicial anonimizado (generate_initial_summary):
  "Ticket PESESG-123: Se reporta un error de conectividad.
   [PERSONA_1] indica que el servicio no responde desde las 09:00.
   Prioridad: Alta."
  [CHIPS: "Ver logs del sistema", "Verificar estado", "Reiniciar servicio"]
              │
              ▼
OPERADOR hace click en chip "Ver logs del sistema"
   → Se envia como mensaje de chat al agente
   → Se registra como comentario en el ticket VOLCADO en KOSIN
              │
              ▼
AGENTE: (usa tool read_ticket para consultar datos)
        (ejecuta tool execute_action para get_logs)
        (responde anonimizado, post-filtrado por Anonymizer)
  "Los logs muestran errores de conexion a la BD desde las 08:47.
   Error: 'Connection refused on port 5432'."
  [CHIPS: "Reiniciar servicio BD", "Verificar conectividad", "Escalar"]
              │
              ▼
OPERADOR: "Reinicia el servicio de base de datos"
              │
              ▼
AGENTE: (execute_action: restart_service — simulado en piloto)
  "He ejecutado el reinicio del servicio de BD.
   Estado: servicio activo. Tiempo de reinicio: 45 segundos."
  [CHIPS: "Confirmar resolucion", "Verificar estado", "Ver logs"]
              │
              ▼
OPERADOR: Click en "Finalizar ticket"
              │
              ▼
AGENTE: Registra resolucion en KOSIN (anonimizado)
PUT /api/tickets/{id}/status → closed
Se destruye el mapa de sustitucion
```

### 3.3 Cierre y Volcado a Cliente — Implementado

```
1. Operador hace click en "Sincronizar con origen"
   → Toma ultimo mensaje del agente como comentario de resolucion
   → POST /api/tickets/{id}/sync-to-client
              │
              ▼
2. Backend carga y descifra el mapa de sustitucion
   → Anonymizer.de_anonymize(comment, sub_map) reemplaza tokens por datos reales
   → jira_connector.add_comment(source_ticket_id, real_comment)
   → Comentario de-anonimizado publicado en ticket origen
              │
              ▼
3. Operador marca ticket como "Finalizar ticket" → status = "resolved"
   (el mapa de sustitucion se MANTIENE para permitir mas sincronizaciones)
              │
              ▼
4. Operador hace click en "Cerrar ticket" (solo visible en status resolved)
   → Dialogo de confirmacion (accion irreversible)
   → PUT /api/tickets/{id}/status → "closed"
   → Se destruye el mapa de sustitucion (delete_substitution_map)
   → closed_at registrado

⚠️  PENDIENTE:
5. Confirmacion de supervisor onshore no implementada
```

---

## 4. Componentes en Detalle

### 4.1 Agente LangChain - Componente de Decision Asistida

El agente es el componente conversacional del sistema, pero **no es el control primario de
seguridad**. Se implementa como un **agente LangChain** con tools y un system prompt
anonimizador, dentro de una plataforma donde la seguridad depende sobre todo del backend,
de la anonimización previa, del filtro de salida y del control de acciones.

**Arquitectura del agente (implementada):**

```
┌─────────────────────────────────────────────────────────┐
│                 AGENTE LANGCHAIN                        │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │  SYSTEM PROMPT (anonimizador — extendido)         │  │
│  │                                                   │  │
│  │  Incluye:                                         │  │
│  │  - Reglas absolutas de anonimizacion              │  │
│  │  - Protocolo de trabajo por fases                 │  │
│  │  - Instrucciones de comunicacion en espanol       │  │
│  │  - Formato de chips sugeridos:                    │  │
│  │    [CHIPS: "Accion 1", "Accion 2", "Accion 3"]   │  │
│  │  - Referencias al ticket KOSIN origen             │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │  TOOLS (5 implementadas)                           │  │
│  │                                                   │  │
│  │  read_ticket(ticket_id)                           │  │
│  │    → Lee ticket + comentarios via conector         │  │
│  │    → Devuelve contenido formateado al agente      │  │
│  │                                                   │  │
│  │  create_kosin_ticket(summary, description, ...)   │  │
│  │    → Crea ticket anonimizado en KOSIN             │  │
│  │                                                   │  │
│  │  update_kosin(ticket_id, comment, status)         │  │
│  │    → Actualiza progreso en KOSIN (anonimizado)    │  │
│  │                                                   │  │
│  │  execute_action(action, service, interval)        │  │
│  │    → Acciones tecnicas (simuladas en piloto)      │  │
│  │    → Allowlist: get_logs, check_status,           │  │
│  │      restart_service, check_connectivity          │  │
│  │                                                   │  │
│  │  read_attachment(ticket_id, attachment_index)     │  │
│  │    → Descarga adjunto, extrae texto (PDF/OCR/     │  │
│  │      Office), anonimiza y devuelve al agente      │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │  HISTORIAL (manual, no ConversationBufferMemory)  │  │
│  │                                                   │  │
│  │  Se carga el historial desde chat_history (SQL)   │  │
│  │  y se convierte a HumanMessage/AIMessage antes    │  │
│  │  de cada invocacion. No se usa la abstraccion     │  │
│  │  Memory de LangChain.                             │  │
│  │  Solo almacena versiones anonimizadas.            │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │  PRE/POST PROCESAMIENTO (red de seguridad)        │  │
│  │                                                   │  │
│  │  PRE (antes de enviar al LLM):                    │  │
│  │    Anonymizer.filter_output() escanea el input    │  │
│  │    del operador buscando PII antes de enviarlo.   │  │
│  │                                                   │  │
│  │  POST (antes de enviar al operador):              │  │
│  │    1. Sustituye valores conocidos del mapa        │  │
│  │    2. Regex fresco detecta PII desconocido        │  │
│  │    3. PII nuevo se reemplaza por [TYPE_REDACTED]  │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │  CHIPS DE ACCION SUGERIDA (nuevo, no en v1.0)     │  │
│  │                                                   │  │
│  │  El system prompt instruye al agente a terminar   │  │
│  │  cada respuesta con:                              │  │
│  │    [CHIPS: "Accion 1", "Accion 2", "Accion 3"]   │  │
│  │                                                   │  │
│  │  Frontend: parsea, oculta del texto, renderiza    │  │
│  │  como botones clickeables. Al click:              │  │
│  │  - Se envia como mensaje de chat                  │  │
│  │  - Se registra como comentario en KOSIN VOLCADO   │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

**Pipeline de cada respuesta (implementado):**

```
Pregunta del operador (o click en chip)
       │
       ▼
PRE: Anonymizer.filter_output() escanea input
       │
       ▼
Cargar historial de chat_history → HumanMessage/AIMessage
       │
       ▼
Agente LangChain: llm.bind_tools(tools).ainvoke()
con StreamingCallback via WebSocket
       │
       ▼
Si hay tool_calls → ejecutar tools → re-invocar LLM con resultados
       │
       ▼
POST: Anonymizer.filter_output() escanea respuesta
  1. Sustitucion de valores conocidos del mapa
  2. Regex fresco para PII desconocido → [TYPE_REDACTED]
       │
       ▼
Guardar en chat_history + audit_log
       │
       ▼
Respuesta limpia + chips → operador (WS complete)
```

**Triple barrera:** Anonymizer pre-LLM + system prompt anonimizador + filtro post-LLM.
La capa determinista reduce la exposicion al modelo; el prompt aporta capacidad conversacional;
el filtro final bloquea fugas residuales.

**Modelo LLM (implementado):** Configurable via `LLM_PROVIDER`:
- `ollama` (por defecto para desarrollo): Ollama local con modelo configurable (`OLLAMA_MODEL`)
- `azure` (para produccion): Azure OpenAI en instancia privada con compliance GDPR

**Framework:** LangChain con `ChatOllama` o `AzureChatOpenAI` segun configuracion.

### 4.2 Anonymizer (Simplificado para Piloto)

Se ha implementado la interfaz abstracta `DetectionService` (ABC) con implementaciones
intercambiables. `Anonymizer` acepta un detector inyectable (default: `RegexDetector`).

```
┌─────────────────────────────────────────────┐
│     DetectionService (ABC) — detection.py   │
│       detect(text) → List[PiiEntity]        │
├─────────────────────────────────────────────┤
│  ┌──────────────┐  ┌────────────────────┐   │
│  │ RegexDetector │  │ AttachmentDetector │   │
│  │ (default)     │  │ (delega a Regex)   │   │
│  └──────────────┘  └────────────────────┘   │
│                                             │
│  Futuro:                                    │
│  ┌──────────────┐  ┌────────────────────┐   │
│  │ AXETDetector │  │ PresidioDetector   │   │
│  └──────────────┘  └────────────────────┘   │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│   Anonymizer (anonymizer.py)                │
│                                             │
│  __init__(detector=RegexDetector())         │
│  detect_pii(text) → delega a detector       │
│  anonymize(text) → (anon_text, map)         │
│  filter_output(text, sub_map) → clean_text  │
│  de_anonymize(text, sub_map) → real_text    │
│                                             │
│  Metodos estaticos de cifrado:              │
│  generate_key() / encrypt_map / decrypt_map │
└─────────────────────────────────────────────┘
```

**Piloto - RegexDetector (implementado):**
- Emails
- Telefonos (+34, moviles, fijos)
- DNI/NIE/NIF espanoles
- IPs (solo v4)
- IBANs
- Nombres propios (diccionario de ~60 nombres y apellidos espanoles)

**No implementado en piloto (previsto en propuesta v1.0):**
- IPv6
- Direcciones y codigos postales (`UBICACION`)
- Deteccion de sistemas/servidores (`SISTEMA`)
- NER/ML avanzado para nombres

**Mejora no prevista:** El filtro post-LLM detecta PII nuevo (no presente en el mapa original)
y lo reemplaza con `[TYPE_REDACTED]`, proporcionando una capa adicional de seguridad.

### 4.3 Mapa de Sustitucion

Estructura que vincula tokens anonimos con valores reales:

```
Ticket PESESG-123:
  PERSONA_1  → "Juan Garcia"
  PERSONA_2  → "Maria Lopez"
  EMAIL_1    → "juan.garcia@acme.com"
  TELEFONO_1 → "+34 612 345 678"
  IP_1       → "192.168.1.50"
  DNI_1      → "12345678A"
  IBAN_1     → "ES91 2100 0418 4502 0005 1332"
```

**Nota:** Los tipos `SISTEMA` y `UBICACION` mostrados en la propuesta v1.0 no se detectan
automaticamente. No existe regex para direcciones ni para nombres de servidores.

**Reglas de seguridad (implementadas):**
- Almacenado cifrado con AES-256-GCM en SQLite (nonce 12 bytes + ciphertext)
- Solo accesible por el servicio backend, nunca expuesto al frontend
- Los tokens son unicos POR TICKET (no reutilizados entre tickets)
- Se destruye cuando el ticket se cierra (`delete_substitution_map`)
- La clave de cifrado se configura en `.env` (`ENCRYPTION_KEY`, base64 de 32 bytes)

**Diferencia con propuesta v1.0:** El cifrado esta integrado directamente en `Anonymizer`
(metodos estaticos), no en un `utils/crypto.py` separado.

### 4.4 Conectores

**Interfaz comun (implementada):**

```python
class TicketConnector(ABC):
    async def get_ticket(self, ticket_id: str) -> Optional[Dict]
    async def get_comments(self, ticket_id: str) -> List[Dict]
    async def update_status(self, ticket_id: str, status: str) -> bool
    async def add_comment(self, ticket_id: str, comment: str) -> bool
    async def create_ticket(self, summary: str, description: str,
                            priority: str, ...) -> Optional[str]
```

**Diferencias con propuesta v1.0:**
- `execute_action()` **removida de la interfaz** del conector; las acciones tecnicas se manejan
  exclusivamente en la tool `execute_action` del agente (simuladas en piloto)
- `create_ticket()` **anadida** a la interfaz (no estaba en la propuesta)
- Retorna `Dict` en lugar de `StandardTicket` (no se implemento el modelo comun)
- Se usa `httpx` para llamadas HTTP, no la libreria `jira` de Atlassian

**Conectores implementados:**
- `KosinConnector`: Conector real contra Jira REST API v2 (KOSIN). Incluye `get_board_issues()`
  para consultar el board via JQL. Bearer token auth.
- `MockKosinConnector`: Mock en memoria para desarrollo sin acceso a KOSIN real.
- `JiraConnector`: Conector real para Jira externo via httpx (Basic Auth email+token).
  `update_status` y `create_ticket` no implementados (solo lectura).
- `MockJiraConnector`: 5 tickets hardcodeados con PII de seguros (contexto espanol).

**Modo POC:** En el piloto, `jira_connector = kosin_connector` — la misma instancia KOSIN
sirve como origen y destino. Los tickets se distinguen por el prefijo `[ANON]` y el tipo
de issue (Sub-Requirement vs otros tipos).

### 4.5 Control de Acciones Tecnicas

Las acciones tecnicas se implementan via la tool `execute_action` del agente con un
**catalogo cerrado de acciones** (allowlist).

**Acciones permitidas (implementadas, todas simuladas en piloto):**
- `get_logs(service, interval)` — devuelve logs ficticios
- `check_status(service)` — devuelve estado ficticio
- `restart_service(service)` — simula reinicio
- `check_connectivity(service)` — simula comprobacion de red

Cada ejecucion se registra en `audit_log` con operador, ticket, hora y resultado.

**Nota:** `add_internal_comment` (propuesta v1.0) se implemento como endpoint REST
`POST /api/tickets/{id}/kosin-comment` en lugar de como accion en la allowlist.

### 4.6 Base de Datos (SQLite - Piloto)

```sql
-- Mapping entre tickets origen y KOSIN (+ campos denormalizados)
CREATE TABLE ticket_mapping (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_system TEXT NOT NULL,           -- "kosin-pesesg", "jira-seguros"
    source_ticket_id TEXT NOT NULL,        -- "PESESG-123"
    kosin_ticket_id TEXT NOT NULL,         -- "PESESG-456" (ticket VOLCADO [ANON])
    summary TEXT NOT NULL DEFAULT '',      -- ⬅ NUEVO: summary anonimizado (cache local)
    anonymized_description TEXT NOT NULL DEFAULT '',  -- ⬅ NUEVO: descripcion completa anonimizada
    priority TEXT NOT NULL DEFAULT 'medium',          -- ⬅ NUEVO: prioridad denormalizada
    status TEXT DEFAULT 'open',            -- open, in_progress, resolved, closed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP,
    UNIQUE(source_system, source_ticket_id)
);

-- Mapa de sustitucion (cifrado AES-256-GCM)
CREATE TABLE substitution_map (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_mapping_id INTEGER NOT NULL REFERENCES ticket_mapping(id),
    encrypted_map BLOB NOT NULL,           -- nonce(12 bytes) + ciphertext AES-256-GCM
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

-- Historial de chat por ticket
CREATE TABLE chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_mapping_id INTEGER NOT NULL REFERENCES ticket_mapping(id),
    role TEXT NOT NULL,                     -- "operator", "agent"
    message TEXT NOT NULL,                 -- siempre anonimizado
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Audit log
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operator_id TEXT NOT NULL,             -- ⚠️ hardcoded "operator" (sin auth)
    action TEXT NOT NULL,                  -- "view_ticket", "chat_message", "ingest_confirmed",
                                           --  "action_executed", etc.
    ticket_mapping_id INTEGER REFERENCES ticket_mapping(id),
    details TEXT,                           -- descripcion de la accion (anonimizada)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Diferencias con propuesta v1.0:**
- `ticket_mapping` tiene 3 columnas adicionales: `summary`, `anonymized_description`, `priority`
  (denormalizacion para evitar consultar KOSIN en cada lectura)
- `AUTOINCREMENT` explicito en primary keys
- `operator_id` siempre vale `"operator"` (sin autenticacion real)

---

## 5. Stack Tecnologico

### 5.1 Piloto (Implementado)

| Capa | Tecnologia | Justificacion |
|---|---|---|
| Frontend | **Next.js 14** (App Router) + TypeScript + Tailwind CSS + Zustand | SPA con streaming WebSocket. Cambio vs propuesta: Next.js en lugar de React puro |
| Backend | Python 3.11+ / FastAPI | Async nativo, ideal para streaming LLM, tipado |
| Base de datos | SQLite (aiosqlite) | Sin infraestructura adicional, suficiente para piloto |
| Agente IA | LangChain + **Ollama (dev) / AzureChatOpenAI (prod)** | Cambio vs propuesta: soporte dual para desarrollo local sin Azure |
| Deteccion PII | DetectionService ABC + RegexDetector | Red de seguridad determinista. Interfaz abstracta con inyeccion |
| Conectores | **httpx** (REST directo) | Cambio vs propuesta: no se usa libreria `jira` de Atlassian |
| Comunicacion | REST (fetch) + WebSocket (nativo) | WebSocket para streaming de tokens del agente |
| Logging | structlog | Logging estructurado (no previsto en propuesta) |
| Despliegue | **Manual** (uvicorn + npm run dev) | ⚠️ Docker Compose planificado pero no creado |

### 5.2 Evolucion a Produccion (Futuro)

| Componente | Piloto (actual) | Produccion |
|---|---|---|
| Base de datos | SQLite | PostgreSQL |
| Autenticacion | Sin auth (operator_id hardcoded) | SSO/OAuth2 corporativo |
| Adjuntos | ✅ OCR + PDF + Office (AttachmentProcessor) | Tesseract en servidor, validacion formatos |
| Conectores | 1 KOSIN (source+dest) | Multi-sistema (Jira externo, Remedy, ServiceNow) |
| Despliegue | Manual (uvicorn + npm) | Docker Compose → Kubernetes / Azure Container Apps |
| Escalado | Monolito | Microservicios si volumen lo requiere |
| Cache | Ninguna | Redis para sesiones y cache LLM |
| Deteccion PII | ✅ DetectionService ABC + RegexDetector | + AXET/Presidio como implementaciones |
| Volcado inverso | ✅ sync_to_client (de_anonymize + endpoint) | Confirmacion supervisor onshore |

---

## 6. Seguridad y Compliance GDPR

### 6.1 Garantias de Anonimizacion (Implementadas)

| Punto de control | Mecanismo | Estado |
|---|---|---|
| Antes del LLM | Anonymizer.filter_output() escanea input del operador | ✅ Implementado |
| Durante el LLM | System prompt con reglas estrictas de anonimizacion | ✅ Implementado |
| Despues del LLM | Filtro escanea respuesta: mapa conocido + regex fresco | ✅ Implementado |
| En KOSIN | Ticket VOLCADO [ANON] solo contiene version anonimizada | ✅ Implementado |
| En el chat | Historial guardado solo contiene mensajes anonimizados | ✅ Implementado |
| PII desconocido | PII nuevo en respuesta LLM → `[TYPE_REDACTED]` | ✅ Implementado (mejora) |

### 6.2 Residencia de Datos

- **LLM (dev):** Ollama local — datos no salen de la maquina del desarrollador.
- **LLM (prod):** Azure OpenAI en instancia privada con compliance GDPR.
- **Plataforma:** Desplegable en la misma region que los datos de cliente.
- **Logs y trazas:** structlog para logging estructurado. No se almacenan payloads con PII en claro.
- **Credenciales:** Gestionadas via `.env` (archivo no commiteado). La clave de cifrado se configura
  en `ENCRYPTION_KEY` y no se almacena en SQLite.

### 6.3 Principio de Minimo Privilegio

- El **operador offshore** nunca tiene credenciales de los sistemas cliente
- El **agente IA** accede via service accounts controlados (tokens en `.env`)
- El **mapa de sustitucion** esta cifrado (AES-256-GCM) y solo el backend lo descifra
- Los **logs de auditoria** registran acciones sin incluir PII
- ⚠️ **Pendiente:** autenticacion de operadores (actualmente `operator_id` = `"operator"`)

### 6.4 Riesgos y Mitigaciones

| Riesgo | Probabilidad | Mitigacion | Estado |
|---|---|---|---|
| LLM filtra PII en respuesta | Baja | Triple barrera: pre-LLM + prompt + post-LLM | ✅ |
| Operador deduce datos por contexto | Baja | Tokens consistentes por ticket | ✅ |
| Mapa de sustitucion comprometido | Muy baja | Cifrado AES-256-GCM en reposo | ✅ |
| Adjuntos con PII visible | Media | AttachmentProcessor + read_attachment tool (OCR, PDF, Office) | ✅ |
| Accion tecnica no segura | Media | Allowlist + auditoria. Acciones simuladas en piloto | ✅ (simulado) |
| Caso ambiguo no anonimizable | Media | Escalado a onshore | ⚠️ No implementado |
| read_ticket devuelve PII al LLM | Baja | System prompt + post-filter. Pre-filter no aplicado en este path | ⚠️ Riesgo aceptado |

**Nota sobre `read_ticket`:** La tool `read_ticket` devuelve el contenido completo del ticket
(con PII) directamente al LLM para que pueda razonar sobre el contexto. El system prompt
le indica que nunca repita PII, y el filtro post-LLM captura fugas. Sin embargo, el PII si
llega al LLM en este flujo (necesario para que el agente pueda operar con datos reales y
ejecutar acciones tecnicas). En produccion con Azure privado esto es aceptable por compliance.

### 6.5 Politica de Escalado Seguro

El sistema no debe responder ni ejecutar automaticamente cuando no pueda garantizar un nivel
suficiente de seguridad o trazabilidad.

**Se escala a onshore cuando:**
- El detector no puede anonimizar con confianza suficiente
- El operador solicita informacion con riesgo de reidentificacion
- La accion requerida no pertenece a la allowlist
- La accion tiene impacto alto o es potencialmente destructiva
- Existe inconsistencia entre ticket origen, mapa de sustitucion y estado en KOSIN

⚠️ **Estado:** El escalado a onshore esta definido como politica pero **no implementado**
como funcionalidad del sistema. No hay mecanismo automatico de bloqueo ni derivacion.

---

## 7. Interfaz de Usuario (Implementada)

### 7.1 Layout Principal

```
┌──────────────────────────────────────────────────────────────┐
│  🔒 Plataforma Anonimizacion Ticketing       [● Conectado]   │
├──────────────────┬───────────────────────────────────────────┤
│                  │                                           │
│  PENDIENTES (3)  │  (Ningún ticket seleccionado)             │
│  ┌────────────┐  │                                           │
│  │ PESESG-101 │  │  Selecciona un ticket del panel           │
│  │ Alta       │  │  izquierdo para comenzar                  │
│  └────────────┘  │                                           │
│  ┌────────────┐  │─────── AL SELECCIONAR PENDIENTE ─────────│
│  │ PESESG-102 │  │                                           │
│  │ Media      │  │  🔒 Ticket PESESG-101                     │
│  └────────────┘  │  Resumen del ticket...                    │
│  ┌────────────┐  │                                           │
│  │ PESESG-103 │  │  ┌──────────────────────────────────────┐│
│  │ Baja       │  │  │  ⚠️ Al atender, se creara una copia  ││
│  └────────────┘  │  │  anonimizada para trabajo seguro.    ││
│                  │  │                                      ││
│  ─────────────── │  │  [🔒 Atender esta incidencia]        ││
│  EN ATENCION (2) │  └──────────────────────────────────────┘│
│  ┌────────────┐  │                                           │
│  │▶ PESESG-456│  │─────── DESPUES DE INGESTAR ──────────────│
│  │  [ANON]    │  │                                           │
│  │  En progr. │  │  AGENTE: Ticket PESESG-456 - Se reporta  │
│  └────────────┘  │  un error de conectividad. [PERSONA_1]   │
│  ┌────────────┐  │  indica que no responde desde las 09:00. │
│  │  PESESG-789│  │                                           │
│  │  [ANON]    │  │  TU: Que logs hay disponibles?            │
│  │  Abierto   │  │                                           │
│  └────────────┘  │  AGENTE: Los logs muestran errores de    │
│                  │  conexion a la BD desde las 08:47.        │
│                  │                                           │
│                  │  ┌─────────┐ ┌──────────┐ ┌───────────┐  │
│                  │  │Ver logs │ │Reiniciar │ │Escalar    │  │
│                  │  └─────────┘ └──────────┘ └───────────┘  │
│                  │                                           │
│                  │  [Escribe tu mensaje...        ] [Enviar] │
│                  │                                           │
│                  │  [Finalizar ticket]                       │
└──────────────────┴───────────────────────────────────────────┘
```

**Diferencias con propuesta v1.0:**
- **Dos secciones de tickets:** "Pendientes" (board KOSIN) y "En atencion" (ingestados) en lugar
  de una sola lista plana
- **Flujo de confirmacion:** Panel intermedio "Atender esta incidencia" antes de anonimizar
- **Chips de accion:** Botones sugeridos por el agente (reemplaza "Registrar en KOSIN")
- **Links KOSIN en chat:** Referencias a tickets PESESG-XXX se renderizan como enlaces clickeables
- **Sin barra de estado** con "Tickets activos" y "Resueltos hoy" (no implementada)
- **Tema visual:** Estilo Jira con header azul (#0052CC)

---

## 8. Plan de Implementacion del Piloto

### 8.1 Alcance del Piloto

- **1 sistema:** KOSIN (Jira interno) como origen y destino simultaneo (POC)
- **1 proyecto:** PESESG en KOSIN
- **Solo texto** (adjuntos/imagenes en fase 2)
- **SQLite** como base de datos
- **Ollama** como LLM para desarrollo, **Azure OpenAI** para produccion

**Fuera de alcance del piloto:**
- Ejecucion real de acciones tecnicas (simuladas)
- Autenticacion de operadores (JWT/SSO)
- Deteccion exhaustiva de PII implicito complejo
- Multi-idioma avanzado
- Integracion simultanea con multiples clientes
- Escalado automatico a onshore
- Docker Compose / Dockerfiles

### 8.2 Fases de Desarrollo

**Fase 1 - Esqueleto (Semana 1)** ✅ Completada
- Estructura del proyecto (FastAPI + Next.js)
- SQLite schema y modelos de datos (con columnas adicionales)
- Conector KOSIN basico (lectura y creacion de tickets)
- MockJiraConnector y MockKosinConnector para desarrollo
- Layout frontend: split panel con Tailwind + tema Jira

**Fase 2 - Core de Anonimizacion (Semana 2)** ✅ Completada
- RegexDetector (emails, DNIs, telefonos, IPs v4, IBANs, nombres)
- Generacion y cifrado de mapa de sustitucion (AES-256-GCM)
- Pipeline de anonimizacion completo (pre y post filtro)
- Chat basico con agente (Ollama + system prompt extendido)
- Flujo de ingesta con confirmacion del operador

**Fase 3 - Flujo Completo (Semana 3)** ✅ Parcialmente completada
- ✅ Chat con streaming (WebSocket + token streaming)
- ✅ Agente con tools: read_ticket, update_kosin, create_kosin_ticket, execute_action, read_attachment
- ✅ Registro de acciones en KOSIN (comments via endpoint REST + chips)
- ✅ Filtro de salida post-LLM con deteccion de PII desconocido
- ✅ Board view con polling cada 60s
- ✅ Chips de accion sugerida (mejora UX no prevista)
- ✅ Volcado inverso al sistema cliente (sync_to_client + de_anonymize)
- ✅ Tool read_attachment (PDF, OCR, Office) con AttachmentProcessor
- ✅ DetectionService ABC con RegexDetector + AttachmentDetector
- ✅ Rate limiter registrado en app
- ✅ Tests pytest (35 tests: anonymizer, attachments, roundtrip)

**Fase 4 - Validacion (Semana 4)** ⏳ Pendiente
- Testing con tickets representativos
- Ajuste de prompts y reglas de deteccion
- Autenticacion basica (JWT) — **no iniciada**
- Correccion de fugas de PII detectadas en pruebas
- Demo con stakeholders
- Docker Compose y Dockerfiles

### 8.3 Criterios de Exito del Piloto

| Criterio | Metrica | Estado |
|---|---|---|
| Anonimizacion efectiva | 0 fugas de PII en respuestas al operador | ⏳ Pendiente validacion |
| Operatividad | Operador puede resolver tickets sin ver datos reales | ✅ Flujo funcional |
| Flujo completo | Ticket entra → se trabaja anonimizado → sync_to_client → cierre | ✅ Completo |
| Usabilidad | Operadores validan que el flujo es practico | ⏳ Pendiente |
| Rendimiento | Respuesta del agente en < 10 segundos | ⏳ Depende del LLM |
| Control operativo | 100% de acciones ejecutadas dentro de allowlist y auditadas | ✅ (simulado) |
| Calidad de deteccion | Medicion de falsos positivos/negativos | ⏳ Pendiente |

---

## 9. Estructura del Proyecto (Implementada)

```
ticketing-anonymization/
├── .gitignore
├── PROPUESTA_ARQUITECTURA_ANONIMIZACION_TICKETING.md
├── backend/
│   ├── .env                             # Variables de entorno (no commiteado)
│   ├── .env.example                     # Template con todas las variables
│   ├── requirements.txt                 # Dependencias Python (+ attachment + pytest)
│   ├── seed.py                          # Poblar DB con tickets mock de seguros
│   ├── create_source_tickets.py         # Crear ticket padre VOLCADO + tickets POC en KOSIN
│   ├── cleanup_tickets.py              # Limpiar tickets POC + padre + DB + .env
│   ├── data/
│   │   └── ticketing.db                 # SQLite database
│   ├── tests/                           # Tests pytest (35 tests)
│   │   ├── __init__.py
│   │   ├── test_anonymizer.py           # 17 tests: detect_pii, anonymize, de_anonymize, crypto
│   │   ├── test_attachment_processor.py # 11 tests: routing, plaintext, mocks OCR/PDF/DOCX
│   │   └── test_de_anonymize_roundtrip.py # 4 tests: anonymize→encrypt→decrypt→de_anonymize
│   └── app/
│       ├── __init__.py
│       ├── main.py                      # FastAPI app, lifespan, CORS, RateLimiter, routers
│       ├── config.py                    # Pydantic Settings desde .env
│       │
│       ├── routers/                     # (propuesta: api/)
│       │   ├── tickets.py               # REST: CRUD + ingest + board + sync-to-client + kosin-comment
│       │   └── chat.py                  # WebSocket: streaming chat con agente
│       │
│       ├── services/
│       │   ├── anonymizer.py            # Anonymizer: mapa sustitucion + AES-256-GCM + filtro + de_anonymize
│       │   ├── detection.py             # DetectionService ABC + RegexDetector + AttachmentDetector
│       │   ├── attachment_processor.py  # Extraccion texto: PDF, OCR, DOCX, XLSX, PPTX, plaintext
│       │   ├── agent.py                 # AnonymizationAgent (LangChain, 5 tools, streaming, chips)
│       │   └── database.py              # DatabaseService async (aiosqlite, schema, CRUD)
│       │
│       ├── connectors/
│       │   ├── base.py                  # Interfaz abstracta TicketConnector + download_attachment
│       │   ├── jira.py                  # MockJiraConnector + JiraConnector (httpx)
│       │   └── kosin.py                 # KosinConnector + MockKosinConnector (httpx)
│       │
│       ├── tools/                       # LangChain tools (5 implementadas)
│       │   ├── read_ticket.py           # Tool: leer ticket origen completo
│       │   ├── update_kosin.py          # Tool: comentar/actualizar KOSIN
│       │   ├── execute_action.py        # Tool: acciones tecnicas (simuladas)
│       │   └── read_attachment.py       # Tool: descargar, extraer texto y anonimizar adjuntos
│       │
│       ├── models/
│       │   └── schemas.py               # Pydantic schemas (+ SyncToClientRequest)
│       │
│       ├── middleware/
│       │   └── rate_limiter.py          # Rate limiter (registrado en app)
│       │
│       └── websocket/
│           └── manager.py               # ConnectionManager (token/complete/error/info)
│
└── frontend/
    ├── package.json                     # Next.js 14 + React 18 + Zustand
    ├── next.config.js                   # Config vacia
    ├── tailwind.config.js
    ├── tsconfig.json
    ├── .env.local                       # NEXT_PUBLIC_API_URL, NEXT_PUBLIC_WS_URL
    └── src/
        ├── app/
        │   ├── layout.tsx               # Root layout (lang="es")
        │   ├── page.tsx                 # SPA: orquestacion + sync-to-client + close ticket
        │   └── globals.css
        ├── components/
        │   ├── ChatPanel.tsx            # Chat + chips + botones Sincronizar/Cerrar
        │   ├── ChatMessage.tsx          # Burbuja de mensaje + links KOSIN
        │   ├── TicketList.tsx           # Panel izquierdo: pendientes + en atencion
        │   └── TicketCard.tsx           # Tarjeta de ticket ingestado
        ├── hooks/
        │   └── useWebSocket.ts          # WS: conexion, reconnect, streaming, chips
        ├── stores/
        │   └── appStore.ts              # Zustand: estado global (tickets, chat, streaming)
        ├── lib/
        │   └── config.ts                # API_URL, WS_URL desde env
        └── types/
            └── index.ts                 # Interfaces TypeScript
```

**Archivos no creados (previstos en propuesta v1.0):**
- `api/auth.py` — autenticacion JWT
- `services/orchestrator.py` — orquestador centralizado (logica en routers/tickets.py)
- `config/clients/piloto.yaml` — configuracion por cliente
- `frontend/src/hooks/useTickets.ts` — hook de tickets (logica en page.tsx)
- `frontend/src/services/api.ts` — cliente REST (se usa fetch directo)
- `Dockerfile` (backend y frontend)
- `docker-compose.yml`

**Archivos nuevos (no previstos en propuesta v1.0):**
- `services/detection.py` — DetectionService ABC con RegexDetector y AttachmentDetector
- `services/attachment_processor.py` — Extraccion de texto de adjuntos (PDF, OCR, Office)
- `tools/read_attachment.py` — Tool LangChain para leer y anonimizar adjuntos
- `tests/` — 35 tests pytest (anonymizer, attachments, roundtrip de-anonymize)

---

## 10. Base de Codigo Existente

El piloto no partio de cero. Se reutilizaron componentes de dos proyectos internos ya
desarrollados por el equipo:

### 10.1 Agents Lab (`multiagents`) — Base principal

Plataforma multi-agente con FastAPI + LangChain + Next.js. Se reutilizo la arquitectura
general y patrones, adaptandolos al caso de uso de anonimizacion:

| Componente | Ruta origen | Uso en el piloto | Estado |
|---|---|---|---|
| FastAPI + WebSocket streaming | `backend/app/main.py`, `websocket/manager.py` | Backend base con streaming de tokens | ✅ Adaptado |
| Agente LangChain con tools | `agents/configurable_agent.py` | Adaptado a agente anonimizador | ✅ Adaptado |
| Sistema de tools con registro | `TOOLS/` | Patron para read_ticket, update_kosin, execute_action | ✅ Adaptado |
| Abstraccion BD SQLite | `services/database.py` | Adaptado con aiosqlite | ✅ Adaptado |
| Hook useWebSocket | `frontend/hooks/useWebSocket.ts` | Conexion real-time con streaming | ✅ Adaptado |
| Middleware (rate limiter) | `middleware/` | Implementado y registrado en app | ✅ Adaptado |

**No reutilizado** (decision consciente):
- Provider factory multi-LLM → reemplazado por config simple `LLM_PROVIDER`
- Servicio de APIs externas → reemplazado por httpx directo
- Cliente MCP → no se uso MCP, se conecta via REST API directo
- StreamingOutputPanel → UI completamente nueva

### 10.2 AI Content Platform (`ai-content-platform`) — Componentes puntuales

| Componente | Ruta origen | Uso en el piloto | Estado |
|---|---|---|---|
| Cifrado AES-256-GCM | `lib/crypto-secrets.ts` | Patron portado a Python (cryptography lib) | ✅ Adaptado |
| Chat store (Zustand) | `stores/chat-store.ts` | Patron de estado para appStore.ts | ✅ Adaptado |
| Componentes de chat UI | `components/` | Inspiracion para ChatPanel/ChatMessage | ✅ Referencia |

### 10.3 Estrategia de Reutilizacion (Ejecutada)

Se creo un proyecto nuevo (`ticketing-anonymization/`) copiando y adaptando modulos
seleccionados. Esto mantuvo el proyecto limpio y enfocado al caso de uso, sin arrastrar
funcionalidad innecesaria de los proyectos origen.

---

## 11. Consideraciones Adicionales

### 11.1 MCP (Model Context Protocol)

Se evaluo el uso de MCP pero **no se implemento**. Los conectores se comunican directamente
con las APIs REST de Jira/KOSIN via httpx. MCP puede reconsiderarse si se necesitan mas
integraciones o si el ecosistema de herramientas crece significativamente.

### 11.2 Evolucion Post-Piloto

Prioridades inmediatas (deuda tecnica del piloto):
- **Autenticacion:** JWT basico o SSO para identificar operadores reales
- **Docker:** Crear Dockerfile + docker-compose.yml para despliegue reproducible
- **IPv6 y ubicaciones:** Ampliar regex del RegexDetector

Mejoras funcionales:
- **Multi-cliente:** Conectores para Jira externo real, Remedy, ServiceNow
- **Escalado:** Migracion a PostgreSQL, Redis, y despliegue en Kubernetes
- **Analytics:** Dashboard de metricas (tickets procesados, tiempo resolucion, etc.)
- **Multi-idioma:** Soporte para deteccion de PII en multiples idiomas europeos
- **Deteccion avanzada:** Nuevas implementaciones DetectionService (AXET/Presidio)
- **Escalado onshore:** Mecanismo automatico de bloqueo y derivacion

### 11.3 Dependencias Externas

| Dependencia | Estado | Responsable |
|---|---|---|
| Endpoint AXET (futuro, opcional) | No requerido para piloto | Equipo plataforma |
| Instancia Azure OpenAI privada | Existente (no usada aun en piloto) | Equipo infra/cloud |
| KOSIN (Jira interno) | ✅ En uso (source + dest en POC) | Equipo operaciones |
| Ollama (LLM local) | ✅ En uso para desarrollo | Desarrollador local |
| Acceso API al Jira cliente piloto | Por gestionar (para salir de modo POC) | Equipo proyecto piloto |
| Credenciales service account | Parcial (tokens KOSIN configurados) | Equipo infra/cloud |
| Catalogo de acciones permitidas | Parcial (4 acciones simuladas) | Squad IA + equipo funcional |

---

## 12. Resumen Ejecutivo

Se ha construido un **piloto funcional** de la plataforma de anonimizacion de ticketing.
El operador puede visualizar tickets del board KOSIN, ingestarlos manualmente con confirmacion,
trabajar con el agente IA via chat con streaming, y ejecutar acciones tecnicas simuladas —
todo sin ver datos personales en ningun momento.

La implementacion se apoya en **LangChain + Ollama** (desarrollo) / **Azure OpenAI** (produccion),
junto con un **Anonymizer** con regex pre-LLM, un filtro post-LLM con deteccion de PII desconocido,
KOSIN como repositorio interno anonimizado, y un catalogo cerrado de acciones tecnicas.

**Principales mejoras respecto a la propuesta original:**
- Ingesta manual con confirmacion del operador (mas control que la ingesta automatica)
- Chips de accion sugerida (UX significativamente mejorada)
- Soporte dual LLM (Ollama + Azure) para desarrollo agil
- Filtro post-LLM mejorado con deteccion de PII desconocido (`[TYPE_REDACTED]`)

**Principales elementos pendientes:**
- Autenticacion de operadores (JWT/SSO)
- Docker Compose y Dockerfiles
- Escalado automatico a onshore
- Deteccion de IPv6, direcciones y ubicaciones

El principio fundamental se mantiene: **el operador nunca ve datos reales; la plataforma,
no solo el agente, actua como barrera de acceso a PII**.
