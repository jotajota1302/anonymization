# Diagrama de Proceso General — Plataforma de Anonimizacion de Ticketing

> **NTT DATA EMEAL** — Sistema de intermediacion GDPR-compliant para soporte offshore
> Version 1.6 — 15 de Marzo de 2026

---

## Flujo End-to-End

```mermaid
flowchart TB
    subgraph SOURCES["🔌 Fuentes de Tickets"]
        KOSIN_SRC["KOSIN / Jira\n(Proyecto PESESG)"]
        REMEDY["Remedy\n(mock)"]
        SERNOW["ServiceNow\n(mock)"]
    end

    subgraph FRONTEND["🖥️ Frontend (Next.js 14)"]
        BOARD["Board de Tickets\nPendientes"]
        CONFIRM["Panel de Confirmacion\n'Atender esta incidencia'"]
        CHAT["Chat con Agente\n(WebSocket streaming)"]
        CHIPS["Chips de Accion\nSugerida"]
        TICKET_VIEW["Vista del Ticket\n(solo datos anonimizados)"]
        SYNC_BTN["Sincronizar\ncon Origen"]
        CLOSE_BTN["Cerrar Ticket"]
    end

    subgraph BACKEND["⚙️ Backend (FastAPI)"]
        direction TB
        subgraph CONNECTORS["Conectores"]
            CONNECTOR_ROUTER["ConnectorRouter"]
            KOSIN_CONN["KosinConnector\n(httpx → Jira REST v2)"]
        end

        subgraph ANON_PIPELINE["Pipeline de Anonimizacion"]
            COMPOSITE["CompositeDetector\n(Presidio NLP + Regex)"]
            ANON["Anonymizer\n• Detectar PII\n• Generar tokens\n• Crear mapa sustitucion"]
            AES["Cifrado AES-256-GCM\n(mapa sustitucion)"]
            PRE_FILTER["Pre-filtro\n(input operador)"]
            POST_FILTER["Post-filtro\n(output LLM)\n+ PII desconocido"]
        end

        subgraph LLM_LAYER["Agente LangChain"]
            LLM_SELECT{{"Proveedor LLM\nOllama | OpenAI | Azure"}}
            AGENT["AnonymizationAgent\n• System prompt\n• Tools (allowlist)\n• Historial por ticket"]
            TOOLS["Tools:\n• read_ticket\n• update_kosin\n• create_kosin_ticket\n• execute_action"]
        end

        DB[("SQLite\n• ticket_mapping\n• substitution_map\n• chat_history\n• audit_log")]
        DEANON["De-anonimizar\n(mapa inverso)"]
        DESTROY["Destruir mapa\nsustitucion"]
    end

    subgraph KOSIN_DEST["📋 KOSIN Destino"]
        ANON_TICKET["Ticket VOLCADO\n[ANON] Sub-Requirement"]
    end

    %% === FLUJO 1: INGESTA ===
    KOSIN_SRC -->|"1. Polling\nboard tickets"| CONNECTOR_ROUTER
    REMEDY -.->|"futuro"| CONNECTOR_ROUTER
    SERNOW -.->|"futuro"| CONNECTOR_ROUTER
    CONNECTOR_ROUTER -->|"2. Lista\nmetadata"| BOARD
    BOARD -->|"3. Operador\nselecciona ticket"| CONFIRM
    CONFIRM -->|"4. POST /ingest-confirm\n{kosin_key}"| KOSIN_CONN
    KOSIN_CONN -->|"5. Lee ticket\ncompleto + PII"| COMPOSITE
    COMPOSITE --> ANON
    ANON -->|"6. Texto anonimizado\n+ mapa tokens"| AES
    AES -->|"7. Mapa cifrado"| DB
    ANON -->|"8. Crear [ANON]\nSub-Requirement"| ANON_TICKET
    ANON -->|"9. ticket_mapping"| DB
    DB -->|"10. Ticket\nen sidebar"| TICKET_VIEW

    %% === FLUJO 2: CHAT ===
    TICKET_VIEW -->|"11. Seleccionar\nticket"| CHAT
    CHAT -->|"12. Mensaje\noperador"| PRE_FILTER
    PRE_FILTER -->|"13. Input\nlimpio"| AGENT
    AGENT --> LLM_SELECT
    LLM_SELECT -->|"14. Invocar\nLLM"| TOOLS
    TOOLS -->|"15. Tool calls\n(datos reales)"| KOSIN_CONN
    AGENT -->|"16. Respuesta\nLLM"| POST_FILTER
    POST_FILTER -->|"17. Respuesta\nanonimizada"| CHAT
    CHAT --> CHIPS
    CHIPS -->|"18. Click\nen chip"| CHAT

    %% === FLUJO 3: CIERRE ===
    SYNC_BTN -->|"19. POST /sync-to-client\nDe-anonimizar comentario"| DEANON
    DEANON -->|"20. Comentario\ncon datos reales"| KOSIN_SRC
    CLOSE_BTN -->|"21. PUT /status → closed"| DESTROY
    DESTROY -->|"22. DELETE\nmapa sustitucion"| DB

    %% === ESTILOS ===
    classDef sourceStyle fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px,color:#1b5e20
    classDef frontStyle fill:#e3f2fd,stroke:#1565c0,stroke-width:2px,color:#0d47a1
    classDef backStyle fill:#fff3e0,stroke:#ef6c00,stroke-width:2px,color:#e65100
    classDef dbStyle fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px,color:#4a148c
    classDef anonStyle fill:#fce4ec,stroke:#c62828,stroke-width:2px,color:#b71c1c
    classDef destStyle fill:#e0f2f1,stroke:#00695c,stroke-width:2px,color:#004d40

    class KOSIN_SRC,REMEDY,SERNOW sourceStyle
    class BOARD,CONFIRM,CHAT,CHIPS,TICKET_VIEW,SYNC_BTN,CLOSE_BTN frontStyle
    class CONNECTOR_ROUTER,KOSIN_CONN,AGENT,LLM_SELECT,TOOLS backStyle
    class DB dbStyle
    class COMPOSITE,ANON,AES,PRE_FILTER,POST_FILTER,DEANON,DESTROY anonStyle
    class ANON_TICKET destStyle
```

---

## Leyenda de colores

| Color | Componente |
|-------|-----------|
| 🟢 Verde | Fuentes de tickets (KOSIN, Remedy, ServiceNow) |
| 🔵 Azul | Frontend (interfaz del operador) |
| 🟠 Naranja | Backend (conectores, agente, tools) |
| 🟣 Morado | Base de datos (SQLite) |
| 🔴 Rojo | Pipeline de anonimizacion (deteccion, cifrado, filtros) |
| 🟦 Teal | KOSIN destino (tickets volcados [ANON]) |

---

## Resumen de flujos

### Flujo 1 — Ingesta (pasos 1-10)
El operador ve tickets pendientes en el board, selecciona uno y confirma. El backend lee el ticket completo con PII desde KOSIN, lo pasa por el CompositeDetector (Presidio NLP + Regex), genera tokens anonimizados, cifra el mapa de sustitucion con AES-256-GCM, crea una copia [ANON] en KOSIN y guarda todo en SQLite.

### Flujo 2 — Chat con agente (pasos 11-18)
El operador interactua via chat WebSocket. Su input pasa por un pre-filtro PII. El agente LangChain (configurable: Ollama/OpenAI/Azure) razona con el contexto anonimizado y ejecuta tools controladas. La respuesta del LLM pasa por un post-filtro que detecta PII conocido (mapa) y desconocido (regex fresco). El agente sugiere acciones via chips clickeables.

### Flujo 3 — Cierre (pasos 19-22)
El operador puede sincronizar comentarios al ticket origen (de-anonimizando con el mapa inverso). Al cerrar el ticket, el mapa de sustitucion se destruye permanentemente, garantizando el derecho al olvido GDPR.
