# Guia de Despliegue en Azure — Plataforma de Anonimizacion Ticketing

> **NTT DATA EMEAL** — Sistema de intermediacion GDPR-compliant para soporte offshore
> Ultima actualizacion: 2026-03-15

---

## Indice

1. [Arquitectura de Despliegue](#1-arquitectura-de-despliegue)
2. [Prerequisitos](#2-prerequisitos)
3. [Servicios Azure Necesarios](#3-servicios-azure-necesarios)
4. [Preparacion de Imagenes Docker](#4-preparacion-de-imagenes-docker)
5. [Base de Datos — Migracion de SQLite a MySQL o PostgreSQL](#5-base-de-datos--migracion-de-sqlite-a-mysql-o-postgresql)
6. [Azure Key Vault — Gestion de Secretos](#6-azure-key-vault--gestion-de-secretos)
7. [Azure OpenAI Service — Configuracion LLM](#7-azure-openai-service--configuracion-llm)
8. [Despliegue del Backend (Azure Container Apps)](#8-despliegue-del-backend-azure-container-apps)
9. [Despliegue del Frontend (Azure Static Web Apps)](#9-despliegue-del-frontend-azure-static-web-apps)
10. [Networking y Seguridad](#10-networking-y-seguridad)
11. [CI/CD con Azure DevOps / GitHub Actions](#11-cicd-con-azure-devops--github-actions)
12. [Monitorizacion y Logging](#12-monitorizacion-y-logging)
13. [Estimacion de Costes](#13-estimacion-de-costes)
14. [Checklist de Despliegue](#14-checklist-de-despliegue)

---

## 1. Arquitectura de Despliegue

```
                         Azure Region: West Europe
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   ┌─────────────────┐         ┌──────────────────────────┐      │
│   │  Static Web Apps │────────▶│  Container Apps (Backend) │      │
│   │   (Next.js SSR)  │   API   │  FastAPI + Uvicorn        │      │
│   │   Port 3000      │◀────────│  Port 8000                │      │
│   └─────────────────┘   WS    └──────────┬───────────────┘      │
│                                          │                      │
│                           ┌──────────────┼──────────────┐       │
│                           │              │              │       │
│                           ▼              ▼              ▼       │
│                    ┌────────────┐  ┌───────────┐  ┌──────────┐  │
│                    │ Azure      │  │ Azure     │  │ Azure    │  │
│                    │ OpenAI     │  │ Database  │  │ Key      │  │
│                    │ (GPT-4)    │  │ MySQL/PgSQL│  │ Vault    │  │
│                    └────────────┘  └───────────┘  └──────────┘  │
│                                                                 │
│                    ┌────────────────────────────┐               │
│                    │  VNET + Private Endpoints   │               │
│                    └────────────────────────────┘               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTPS (via VNET peering o public)
                              ▼
                   ┌─────────────────────┐
                   │  KOSIN / Jira       │
                   │  umane.emeal.       │
                   │  nttdata.com/jiraito │
                   └─────────────────────┘
```

**Flujo de datos:**
1. Operador accede al frontend via HTTPS (dominio custom o `*.azurestaticapps.net`)
2. Frontend llama a la API REST y conecta por WebSocket al backend
3. Backend consulta KOSIN via HTTPS, anonimiza con pipeline PII, invoca Azure OpenAI
4. Datos sensibles nunca salen del pipeline: pre-filtro → LLM → post-filtro
5. Mapa de sustitucion cifrado con AES-256-GCM, clave en Key Vault

---

## 2. Prerequisitos

### Herramientas locales
```bash
# Azure CLI
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
az login

# Docker
docker --version  # >= 20.x

# Node.js (para build del frontend)
node --version    # >= 18.x
```

### Accesos requeridos
- Suscripcion Azure con permisos de Contributor
- Acceso a Azure OpenAI Service (requiere solicitud previa en https://aka.ms/oai/access)
- Credenciales KOSIN (bearer token) para el entorno de produccion
- Repositorio Git con el codigo fuente

### Variables de entorno de referencia
```bash
# Configurar para los scripts de despliegue
export RESOURCE_GROUP="rg-ticketing-anonymization"
export LOCATION="westeurope"
export ACR_NAME="acrticketing"
export APP_NAME="ticketing-backend"
export FRONTEND_NAME="ticketing-frontend"
```

---

## 3. Servicios Azure Necesarios

| Servicio | SKU Recomendado | Uso | Coste aprox/mes |
|----------|----------------|-----|-----------------|
| **Azure Container Apps** | Consumption | Backend FastAPI + WebSocket | ~15-40 EUR |
| **Azure Static Web Apps** | Standard | Frontend Next.js | ~8 EUR |
| **Azure Database for MySQL o PostgreSQL** | Flexible Server, Burstable B1ms | Base de datos | ~13 EUR |
| **Azure OpenAI Service** | S0 (pay-per-token) | LLM GPT-4 | Variable (~50-200 EUR) |
| **Azure Key Vault** | Standard | Secretos y claves | ~0.03 EUR |
| **Azure Container Registry** | Basic | Imagenes Docker | ~5 EUR |
| **Azure Monitor + Log Analytics** | Pay-as-you-go | Logs y metricas | ~5-15 EUR |
| **VNET** | — | Red privada | Gratis |

**Total estimado: ~100-300 EUR/mes** (segun uso del LLM)

---

## 4. Preparacion de Imagenes Docker

### 4.1 Dockerfile — Backend

Crear `ticketing-anonymization/backend/Dockerfile`:

```dockerfile
FROM python:3.11-slim

# Dependencias del sistema para Tesseract OCR y procesamiento de documentos
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-spa \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Descargar modelo spaCy para PII detection
RUN python -m spacy download es_core_news_sm || true
RUN python -m spacy download en_core_web_sm || true

# Copiar codigo fuente
COPY . .

# Crear directorio para datos (si se usa SQLite en desarrollo)
RUN mkdir -p data

# Puerto del servidor
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health')" || exit 1

# Arrancar con uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

> **Nota:** Se usa `--workers 1` porque el backend mantiene estado en memoria (WebSocket connections, agent instance). Para escalar horizontalmente, se requeriria Redis para estado compartido.

### 4.2 Dockerfile — Frontend

Crear `ticketing-anonymization/frontend/Dockerfile`:

```dockerfile
FROM node:18-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Variables de entorno en build time
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_WS_URL

ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_WS_URL=$NEXT_PUBLIC_WS_URL

RUN npm run build

# --- Produccion ---
FROM node:18-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000

CMD ["node", "server.js"]
```

> Requiere `output: "standalone"` en `next.config.js`.

### 4.3 Configuracion Next.js para standalone

Verificar/actualizar `frontend/next.config.js`:

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  // ... resto de configuracion existente
};

module.exports = nextConfig;
```

### 4.4 Build y Push al Azure Container Registry

```bash
# 1. Crear Resource Group
az group create --name $RESOURCE_GROUP --location $LOCATION

# 2. Crear Azure Container Registry
az acr create --resource-group $RESOURCE_GROUP \
    --name $ACR_NAME --sku Basic --admin-enabled true

# 3. Login en ACR
az acr login --name $ACR_NAME

# 4. Build y push del backend
cd ticketing-anonymization/backend
docker build -t $ACR_NAME.azurecr.io/ticketing-backend:latest .
docker push $ACR_NAME.azurecr.io/ticketing-backend:latest

# 5. Build y push del frontend
cd ../frontend
docker build \
    --build-arg NEXT_PUBLIC_API_URL=https://ticketing-backend.<region>.azurecontainerapps.io \
    --build-arg NEXT_PUBLIC_WS_URL=wss://ticketing-backend.<region>.azurecontainerapps.io \
    -t $ACR_NAME.azurecr.io/ticketing-frontend:latest .
docker push $ACR_NAME.azurecr.io/ticketing-frontend:latest
```

---

## 5. Base de Datos — Migracion de SQLite a MySQL o PostgreSQL

> **Elegir uno:** La plataforma soporta ambos motores. Seleccionar segun la infraestructura disponible en el entorno del cliente.

| Criterio | MySQL | PostgreSQL |
|----------|-------|------------|
| Familiaridad equipo NTT | Comun en proyectos enterprise | Comun en proyectos cloud-native |
| JSON nativo | `JSON` con `JSON_EXTRACT()` | `JSONB` con operadores `->`, `->>` |
| Coste Azure (B1ms) | ~13 EUR/mes | ~13 EUR/mes |
| Driver async Python | `aiomysql` | `asyncpg` |
| Cifrado en reposo | AES-256 (Azure por defecto) | AES-256 (Azure por defecto) |
| Azure Flexible Server | Si | Si |

---

### 5.A — Opcion MySQL

#### 5.A.1 Crear Azure Database for MySQL

```bash
az mysql flexible-server create \
    --resource-group $RESOURCE_GROUP \
    --name ticketing-db \
    --location $LOCATION \
    --sku-name Standard_B1ms \
    --tier Burstable \
    --storage-size 32 \
    --version 8.0.21 \
    --admin-user ticketingadmin \
    --admin-password "<PASSWORD_SEGURO>" \
    --yes

# Crear la base de datos
az mysql flexible-server db create \
    --resource-group $RESOURCE_GROUP \
    --server-name ticketing-db \
    --database-name ticketing_anonymization

# Configurar SSL obligatorio
az mysql flexible-server parameter set \
    --resource-group $RESOURCE_GROUP \
    --server-name ticketing-db \
    --name require_secure_transport \
    --value ON

# Configurar charset UTF-8
az mysql flexible-server parameter set \
    --resource-group $RESOURCE_GROUP \
    --server-name ticketing-db \
    --name character_set_server \
    --value utf8mb4
```

#### 5.A.2 Dependencia Python (MySQL)

Actualizar `requirements.txt`:
```
aiomysql>=0.2.0
# Reemplazar: aiosqlite>=0.19.0
```

Connection string para `.env` / Key Vault:
```
DATABASE_URL=mysql+aiomysql://ticketingadmin:<PASSWORD>@ticketing-db.mysql.database.azure.com:3306/ticketing_anonymization?ssl=true
```

#### 5.A.3 DatabaseService adaptado (MySQL)

```python
import aiomysql

class DatabaseService:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool = None

    async def initialize(self):
        self.pool = await aiomysql.create_pool(
            host="ticketing-db.mysql.database.azure.com",
            port=3306,
            user="ticketingadmin",
            password="<PASSWORD>",
            db="ticketing_anonymization",
            charset="utf8mb4",
            autocommit=True,
            ssl={"ssl": True},
            minsize=2,
            maxsize=10,
        )
        await self._create_tables()

    async def _execute(self, query: str, params=None):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query, params)
                return await cur.fetchall()

    async def _execute_insert(self, query: str, params=None):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                return cur.lastrowid
```

#### 5.A.4 Esquema MySQL

```sql
CREATE TABLE ticket_mapping (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_system VARCHAR(50) NOT NULL,
    source_id VARCHAR(100) NOT NULL,
    kosin_id VARCHAR(100),
    summary TEXT,
    anonymized_description TEXT,
    priority VARCHAR(20) DEFAULT 'Medium',
    status VARCHAR(20) DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_source (source_system, source_id),
    INDEX idx_kosin (kosin_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE substitution_map (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ticket_id INT NOT NULL,
    nonce VARBINARY(16) NOT NULL,
    ciphertext MEDIUMBLOB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ticket_id) REFERENCES ticket_mapping(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE chat_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ticket_id INT NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ticket_id) REFERENCES ticket_mapping(id) ON DELETE CASCADE,
    INDEX idx_ticket (ticket_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE audit_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    action VARCHAR(50) NOT NULL,
    ticket_id INT,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_action (action),
    INDEX idx_ticket (ticket_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE system_config (
    `key` VARCHAR(100) PRIMARY KEY,
    value TEXT,
    extra_config JSON,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

---

### 5.B — Opcion PostgreSQL

#### 5.B.1 Crear Azure Database for PostgreSQL

```bash
az postgres flexible-server create \
    --resource-group $RESOURCE_GROUP \
    --name ticketing-db \
    --location $LOCATION \
    --sku-name Standard_B1ms \
    --tier Burstable \
    --storage-size 32 \
    --version 16 \
    --admin-user ticketingadmin \
    --admin-password "<PASSWORD_SEGURO>" \
    --yes

# Crear la base de datos
az postgres flexible-server db create \
    --resource-group $RESOURCE_GROUP \
    --server-name ticketing-db \
    --database-name ticketing_anonymization

# SSL esta habilitado por defecto en Azure PostgreSQL Flexible Server
```

#### 5.B.2 Dependencia Python (PostgreSQL)

Actualizar `requirements.txt`:
```
asyncpg>=0.29.0
# Reemplazar: aiosqlite>=0.19.0
```

Connection string para `.env` / Key Vault:
```
DATABASE_URL=postgresql+asyncpg://ticketingadmin:<PASSWORD>@ticketing-db.postgres.database.azure.com:5432/ticketing_anonymization?ssl=require
```

#### 5.B.3 DatabaseService adaptado (PostgreSQL)

```python
import asyncpg

class DatabaseService:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool = None

    async def initialize(self):
        self.pool = await asyncpg.create_pool(
            host="ticketing-db.postgres.database.azure.com",
            port=5432,
            user="ticketingadmin",
            password="<PASSWORD>",
            database="ticketing_anonymization",
            ssl="require",
            min_size=2,
            max_size=10,
        )
        await self._create_tables()

    async def _execute(self, query: str, *params):
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *params)

    async def _execute_insert(self, query: str, *params):
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *params)
```

#### 5.B.4 Esquema PostgreSQL

```sql
CREATE TABLE ticket_mapping (
    id SERIAL PRIMARY KEY,
    source_system VARCHAR(50) NOT NULL,
    source_id VARCHAR(100) NOT NULL,
    kosin_id VARCHAR(100),
    summary TEXT,
    anonymized_description TEXT,
    priority VARCHAR(20) DEFAULT 'Medium',
    status VARCHAR(20) DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_tm_source ON ticket_mapping(source_system, source_id);
CREATE INDEX idx_tm_kosin ON ticket_mapping(kosin_id);
CREATE INDEX idx_tm_status ON ticket_mapping(status);

CREATE TABLE substitution_map (
    id SERIAL PRIMARY KEY,
    ticket_id INTEGER NOT NULL REFERENCES ticket_mapping(id) ON DELETE CASCADE,
    nonce BYTEA NOT NULL,
    ciphertext BYTEA NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE chat_history (
    id SERIAL PRIMARY KEY,
    ticket_id INTEGER NOT NULL REFERENCES ticket_mapping(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_ch_ticket ON chat_history(ticket_id);

CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,
    action VARCHAR(50) NOT NULL,
    ticket_id INTEGER,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_al_action ON audit_log(action);
CREATE INDEX idx_al_ticket ON audit_log(ticket_id);

CREATE TABLE system_config (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT,
    extra_config JSONB,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

### 5.C — Opcion desarrollo (SQLite)

Mantener SQLite con volumen persistente en Container Apps. Valido para MVP o si hay una sola instancia del backend. No requiere cambios en el codigo.

---

### 5.D — Tabla comparativa de diferencias SQLite → MySQL vs PostgreSQL

| Concepto | SQLite | MySQL | PostgreSQL |
|----------|--------|-------|------------|
| Placeholder | `?` | `%s` | `$1, $2, ...` |
| Autoincrement | `INTEGER PRIMARY KEY` | `INT AUTO_INCREMENT PRIMARY KEY` | `SERIAL PRIMARY KEY` |
| Binarios | `BLOB` | `VARBINARY(n)` / `MEDIUMBLOB` | `BYTEA` |
| Boolean | `INTEGER (0/1)` | `TINYINT(1)` | `BOOLEAN` |
| JSON nativo | No (TEXT) | `JSON` + `JSON_EXTRACT()` | `JSONB` + `->`, `->>` |
| Update timestamp | Manual | `ON UPDATE CURRENT_TIMESTAMP` | Trigger o manual |
| Palabra reservada `key` | Sin escapar | `` `key` `` (backticks) | `"key"` (comillas dobles) |
| Driver async Python | `aiosqlite` | `aiomysql` | `asyncpg` |
| SSL en Azure | N/A | `ssl=true` en connection string | `ssl=require` en connection string |
| Pool de conexiones | No necesario | `aiomysql.create_pool()` | `asyncpg.create_pool()` |
| Tipo JSON recomendado | `TEXT` | `JSON` | `JSONB` (indexable) |

---

## 6. Azure Key Vault — Gestion de Secretos

### 6.1 Crear Key Vault

```bash
az keyvault create \
    --resource-group $RESOURCE_GROUP \
    --name kv-ticketing \
    --location $LOCATION \
    --enable-rbac-authorization true
```

### 6.2 Almacenar secretos

```bash
# Clave de cifrado AES-256-GCM (generar una nueva para produccion)
python -c "import base64, os; print(base64.b64encode(os.urandom(32)).decode())"
# Copiar el output y guardarlo:

az keyvault secret set --vault-name kv-ticketing \
    --name "ENCRYPTION-KEY" --value "<base64-key-generada>"

az keyvault secret set --vault-name kv-ticketing \
    --name "KOSIN-TOKEN" --value "<bearer-token-produccion>"

az keyvault secret set --vault-name kv-ticketing \
    --name "AZURE-OPENAI-KEY" --value "<api-key>"

# Si se usa MySQL:
az keyvault secret set --vault-name kv-ticketing \
    --name "DATABASE-URL" --value "mysql+aiomysql://ticketingadmin:<PASSWORD>@ticketing-db.mysql.database.azure.com:3306/ticketing_anonymization?ssl=true"

# Si se usa PostgreSQL:
# az keyvault secret set --vault-name kv-ticketing \
#     --name "DATABASE-URL" --value "postgresql+asyncpg://ticketingadmin:<PASSWORD>@ticketing-db.postgres.database.azure.com:5432/ticketing_anonymization?ssl=require"
```

### 6.3 Identidad Managed del Backend

```bash
# El Container App usara Managed Identity para acceder a Key Vault
# Se configura al crear el Container App (seccion 8)
```

---

## 7. Azure OpenAI Service — Configuracion LLM

### 7.1 Crear recurso Azure OpenAI

```bash
az cognitiveservices account create \
    --resource-group $RESOURCE_GROUP \
    --name openai-ticketing \
    --kind OpenAI \
    --sku S0 \
    --location $LOCATION \
    --custom-domain openai-ticketing
```

### 7.2 Desplegar modelo

```bash
# Desplegar GPT-4 (o GPT-4o para mejor coste/rendimiento)
az cognitiveservices account deployment create \
    --resource-group $RESOURCE_GROUP \
    --name openai-ticketing \
    --deployment-name gpt-4o \
    --model-name gpt-4o \
    --model-version "2024-08-06" \
    --model-format OpenAI \
    --sku-capacity 10 \
    --sku-name Standard
```

### 7.3 Variables resultantes

```bash
# Obtener endpoint
az cognitiveservices account show \
    --resource-group $RESOURCE_GROUP \
    --name openai-ticketing \
    --query properties.endpoint -o tsv

# Obtener clave
az cognitiveservices account keys list \
    --resource-group $RESOURCE_GROUP \
    --name openai-ticketing \
    --query key1 -o tsv
```

Configuracion resultante para el backend:
```
LLM_PROVIDER=azure
AZURE_OPENAI_ENDPOINT=https://openai-ticketing.openai.azure.com/
AZURE_OPENAI_KEY=<key-desde-keyvault>
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_VERSION=2024-08-06
```

---

## 8. Despliegue del Backend (Azure Container Apps)

### 8.1 Crear entorno Container Apps

```bash
# Crear Log Analytics workspace
az monitor log-analytics workspace create \
    --resource-group $RESOURCE_GROUP \
    --workspace-name logs-ticketing \
    --location $LOCATION

LOG_ANALYTICS_ID=$(az monitor log-analytics workspace show \
    --resource-group $RESOURCE_GROUP \
    --workspace-name logs-ticketing \
    --query customerId -o tsv)

LOG_ANALYTICS_KEY=$(az monitor log-analytics workspace get-shared-keys \
    --resource-group $RESOURCE_GROUP \
    --workspace-name logs-ticketing \
    --query primarySharedKey -o tsv)

# Crear Container Apps Environment
az containerapp env create \
    --resource-group $RESOURCE_GROUP \
    --name env-ticketing \
    --location $LOCATION \
    --logs-workspace-id $LOG_ANALYTICS_ID \
    --logs-workspace-key $LOG_ANALYTICS_KEY
```

### 8.2 Desplegar Container App del Backend

```bash
# Obtener credenciales ACR
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query passwords[0].value -o tsv)

az containerapp create \
    --resource-group $RESOURCE_GROUP \
    --name $APP_NAME \
    --environment env-ticketing \
    --image $ACR_NAME.azurecr.io/ticketing-backend:latest \
    --registry-server $ACR_NAME.azurecr.io \
    --registry-username $ACR_NAME \
    --registry-password $ACR_PASSWORD \
    --target-port 8000 \
    --ingress external \
    --transport http \
    --min-replicas 1 \
    --max-replicas 3 \
    --cpu 1.0 \
    --memory 2.0Gi \
    --env-vars \
        "DEBUG=false" \
        "LLM_PROVIDER=azure" \
        "AZURE_OPENAI_ENDPOINT=https://openai-ticketing.openai.azure.com/" \
        "AZURE_OPENAI_DEPLOYMENT=gpt-4o" \
        "AZURE_OPENAI_API_VERSION=2024-08-06" \
        "KOSIN_URL=https://umane.emeal.nttdata.com/jiraito" \
        "KOSIN_PROJECT=PESESG" \
        "KOSIN_ISSUE_TYPE_ID=15408" \
        "KOSIN_BOARD_ID=18418" \
        "PII_DETECTOR=composite" \
        "USE_MOCK_JIRA=false" \
        "ACTIVE_SOURCES=kosin" \
    --secrets \
        "encryption-key=<valor>" \
        "kosin-token=<valor>" \
        "azure-openai-key=<valor>" \
        "database-url=<valor>" \
    --secret-env-vars \
        "ENCRYPTION_KEY=encryption-key" \
        "KOSIN_TOKEN=kosin-token" \
        "AZURE_OPENAI_KEY=azure-openai-key" \
        "DATABASE_URL=database-url"
```

> **WebSocket:** Azure Container Apps soporta WebSocket de forma nativa con `--transport http`. No requiere configuracion adicional.

### 8.3 Verificar despliegue

```bash
# Obtener URL del backend
BACKEND_URL=$(az containerapp show \
    --resource-group $RESOURCE_GROUP \
    --name $APP_NAME \
    --query properties.configuration.ingress.fqdn -o tsv)

echo "Backend URL: https://$BACKEND_URL"

# Test health check
curl https://$BACKEND_URL/health
```

---

## 9. Despliegue del Frontend (Azure Static Web Apps)

### Opcion A — Static Web Apps (recomendada)

```bash
# Crear Static Web App
az staticwebapp create \
    --resource-group $RESOURCE_GROUP \
    --name $FRONTEND_NAME \
    --location $LOCATION \
    --sku Standard
```

Crear `frontend/staticwebapp.config.json`:
```json
{
  "navigationFallback": {
    "rewrite": "/index.html"
  },
  "routes": [
    {
      "route": "/api/*",
      "allowedRoles": ["authenticated"]
    }
  ],
  "globalHeaders": {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "default-src 'self'; connect-src 'self' https://ticketing-backend.*.azurecontainerapps.io wss://ticketing-backend.*.azurecontainerapps.io; img-src 'self' data:; style-src 'self' 'unsafe-inline'"
  }
}
```

### Opcion B — Container App (si se necesita SSR)

```bash
az containerapp create \
    --resource-group $RESOURCE_GROUP \
    --name $FRONTEND_NAME \
    --environment env-ticketing \
    --image $ACR_NAME.azurecr.io/ticketing-frontend:latest \
    --registry-server $ACR_NAME.azurecr.io \
    --registry-username $ACR_NAME \
    --registry-password $ACR_PASSWORD \
    --target-port 3000 \
    --ingress external \
    --min-replicas 1 \
    --max-replicas 2 \
    --cpu 0.5 \
    --memory 1.0Gi
```

---

## 10. Networking y Seguridad

### 10.1 VNET y Private Endpoints

```bash
# Crear VNET
az network vnet create \
    --resource-group $RESOURCE_GROUP \
    --name vnet-ticketing \
    --location $LOCATION \
    --address-prefix 10.0.0.0/16

# Subnet para Container Apps
az network vnet subnet create \
    --resource-group $RESOURCE_GROUP \
    --vnet-name vnet-ticketing \
    --name snet-containers \
    --address-prefix 10.0.1.0/24 \
    --delegations Microsoft.App/environments

# Subnet para base de datos
# Usar la delegacion correspondiente segun el motor elegido:
#   MySQL:      Microsoft.DBforMySQL/flexibleServers
#   PostgreSQL: Microsoft.DBforPostgreSQL/flexibleServers
az network vnet subnet create \
    --resource-group $RESOURCE_GROUP \
    --vnet-name vnet-ticketing \
    --name snet-database \
    --address-prefix 10.0.2.0/24 \
    --delegations Microsoft.DBforMySQL/flexibleServers

# Subnet para Private Endpoints (Key Vault, OpenAI)
az network vnet subnet create \
    --resource-group $RESOURCE_GROUP \
    --vnet-name vnet-ticketing \
    --name snet-endpoints \
    --address-prefix 10.0.3.0/24
```

### 10.2 CORS en Produccion

Actualizar la variable `CORS_ORIGINS` en el backend:
```
CORS_ORIGINS=["https://ticketing-frontend.azurestaticapps.net","https://tu-dominio-custom.nttdata.com"]
```

### 10.3 HTTPS y Dominio Custom

```bash
# Anadir dominio custom al frontend
az staticwebapp hostname set \
    --resource-group $RESOURCE_GROUP \
    --name $FRONTEND_NAME \
    --hostname ticketing.nttdata.com

# Azure Container Apps proporciona HTTPS automatico
# Para dominio custom en el backend:
az containerapp hostname add \
    --resource-group $RESOURCE_GROUP \
    --name $APP_NAME \
    --hostname api-ticketing.nttdata.com

az containerapp ssl upload \
    --resource-group $RESOURCE_GROUP \
    --name $APP_NAME \
    --hostname api-ticketing.nttdata.com \
    --certificate-file cert.pfx \
    --certificate-password "<password>"
```

### 10.4 Cabeceras de Seguridad

El frontend ya incluye CSP en `staticwebapp.config.json`. Para el backend, anadir middleware en `main.py`:

```python
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
```

---

## 11. CI/CD con Azure DevOps / GitHub Actions

### GitHub Actions — Backend

Crear `.github/workflows/deploy-backend.yml`:

```yaml
name: Deploy Backend

on:
  push:
    branches: [main]
    paths: ["ticketing-anonymization/backend/**"]

env:
  ACR_NAME: acrticketing
  RESOURCE_GROUP: rg-ticketing-anonymization
  APP_NAME: ticketing-backend

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Login to Azure
        uses: azure/login@v2
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}

      - name: Login to ACR
        run: az acr login --name $ACR_NAME

      - name: Build and push image
        working-directory: ticketing-anonymization/backend
        run: |
          docker build -t $ACR_NAME.azurecr.io/ticketing-backend:${{ github.sha }} .
          docker build -t $ACR_NAME.azurecr.io/ticketing-backend:latest .
          docker push $ACR_NAME.azurecr.io/ticketing-backend:${{ github.sha }}
          docker push $ACR_NAME.azurecr.io/ticketing-backend:latest

      - name: Deploy to Container Apps
        run: |
          az containerapp update \
            --resource-group $RESOURCE_GROUP \
            --name $APP_NAME \
            --image $ACR_NAME.azurecr.io/ticketing-backend:${{ github.sha }}
```

### GitHub Actions — Frontend

Crear `.github/workflows/deploy-frontend.yml`:

```yaml
name: Deploy Frontend

on:
  push:
    branches: [main]
    paths: ["ticketing-anonymization/frontend/**"]

env:
  RESOURCE_GROUP: rg-ticketing-anonymization

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: 18
          cache: npm
          cache-dependency-path: ticketing-anonymization/frontend/package-lock.json

      - name: Install and build
        working-directory: ticketing-anonymization/frontend
        env:
          NEXT_PUBLIC_API_URL: ${{ vars.BACKEND_URL }}
          NEXT_PUBLIC_WS_URL: ${{ vars.BACKEND_WS_URL }}
        run: |
          npm ci
          npm run build

      - name: Deploy to Static Web Apps
        uses: Azure/static-web-apps-deploy@v1
        with:
          azure_static_web_apps_api_token: ${{ secrets.SWA_TOKEN }}
          repo_token: ${{ secrets.GITHUB_TOKEN }}
          action: upload
          app_location: ticketing-anonymization/frontend
          output_location: out
```

---

## 12. Monitorizacion y Logging

### 12.1 Application Insights

```bash
# Crear Application Insights
az monitor app-insights component create \
    --resource-group $RESOURCE_GROUP \
    --app insights-ticketing \
    --location $LOCATION \
    --kind web

# Obtener instrumentation key
az monitor app-insights component show \
    --resource-group $RESOURCE_GROUP \
    --app insights-ticketing \
    --query instrumentationKey -o tsv
```

### 12.2 Alertas recomendadas

| Alerta | Condicion | Severidad |
|--------|-----------|-----------|
| Backend caido | Health check falla > 3 veces consecutivas | Critical |
| Latencia alta | P95 response time > 5s | Warning |
| Errores PII leak | Log contiene "PII_LEAK_DETECTED" | Critical |
| CPU alta | CPU > 80% durante 5 min | Warning |
| LLM errors | Azure OpenAI 429/500 errors | Warning |

```bash
# Ejemplo: alerta por health check
az monitor metrics alert create \
    --resource-group $RESOURCE_GROUP \
    --name "backend-health-alert" \
    --scopes "/subscriptions/<sub-id>/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.App/containerApps/$APP_NAME" \
    --condition "avg Requests < 1" \
    --window-size 5m \
    --evaluation-frequency 1m \
    --severity 1
```

### 12.3 Logs del audit_log

El `audit_log` de la aplicacion registra todas las acciones sensibles. En produccion, configurar export a Log Analytics:

```python
# En main.py, anadir logger que envia a Azure Monitor
import logging
from opencensus.ext.azure.log_exporter import AzureLogHandler

logger = logging.getLogger(__name__)
logger.addHandler(AzureLogHandler(
    connection_string="InstrumentationKey=<key>"
))
```

---

## 13. Estimacion de Costes

### Escenario: 5 operadores, ~100 tickets/dia

| Servicio | Detalle | Coste/mes EUR |
|----------|---------|---------------|
| Container Apps (backend) | 1 vCPU, 2GB RAM, ~720h | ~35 |
| Static Web Apps | Standard tier | ~8 |
| MySQL o PostgreSQL Flexible | B1ms (1 vCore, 2GB) | ~13 |
| Azure OpenAI (GPT-4o) | ~500K tokens/dia input, ~200K output | ~80-150 |
| Key Vault | ~1000 operaciones/dia | ~0.05 |
| Container Registry | Basic, ~2 imagenes | ~5 |
| Log Analytics | ~5 GB/mes | ~12 |
| **TOTAL** | | **~155-225** |

### Optimizaciones de coste
- Usar **GPT-4o mini** en vez de GPT-4o reduce el coste LLM un ~80%
- **Reserved instances** para MySQL/PostgreSQL (-30%)
- **Scale to zero** en Container Apps si no hay uso nocturno

---

## 14. Checklist de Despliegue

### Pre-despliegue
- [ ] Suscripcion Azure activa con cuota suficiente
- [ ] Acceso a Azure OpenAI aprobado
- [ ] Dominio DNS configurado (si aplica)
- [ ] Credenciales KOSIN de produccion obtenidas
- [ ] Clave AES-256-GCM generada para produccion
- [ ] `next.config.js` con `output: "standalone"`

### Infraestructura
- [ ] Resource Group creado
- [ ] VNET y subnets configuradas
- [ ] Azure Container Registry creado
- [ ] Azure Database for MySQL o PostgreSQL desplegado (ver seccion 5)
- [ ] Azure Key Vault con secretos cargados
- [ ] Azure OpenAI con modelo desplegado
- [ ] Log Analytics workspace creado

### Aplicacion
- [ ] Dockerfile backend construido y testeado localmente
- [ ] Dockerfile frontend construido y testeado localmente
- [ ] Imagenes subidas a ACR
- [ ] Container App del backend desplegado
- [ ] Frontend desplegado (Static Web Apps o Container App)
- [ ] Variables de entorno configuradas
- [ ] CORS configurado con dominios de produccion

### Verificacion
- [ ] `GET /health` responde 200
- [ ] Frontend carga sin errores
- [ ] WebSocket conecta correctamente
- [ ] Login y listado de tickets del board funciona
- [ ] Ingesta de ticket completa (anonimizacion + creacion KOSIN)
- [ ] Chat con agente funciona (streaming)
- [ ] Pipeline PII: verificar que no se filtran datos reales
- [ ] Dark mode funciona
- [ ] Configuracion del agente (pestana Agente) funciona

### Seguridad
- [ ] HTTPS activo en todos los endpoints
- [ ] Key Vault accesible solo via Managed Identity
- [ ] Base de datos (MySQL/PostgreSQL) accesible solo desde VNET
- [ ] CORS restringido a dominios conocidos
- [ ] Cabeceras de seguridad activas (CSP, HSTS, X-Frame-Options)
- [ ] `USE_MOCK_JIRA=false` en produccion
- [ ] `DEBUG=false` en produccion
- [ ] Audit log activo y exportado a Log Analytics

### Post-despliegue
- [ ] Alertas configuradas (health, latencia, errores)
- [ ] CI/CD pipeline funcionando
- [ ] Runbook documentado para incidencias
- [ ] Backup de base de datos configurado (automatico en Azure, retencion 7 dias por defecto)
- [ ] Plan de rotacion de claves (ENCRYPTION_KEY, KOSIN_TOKEN)

---

## Notas GDPR

1. **Region Azure:** West Europe (Paises Bajos) o North Europe (Irlanda) para cumplir residencia de datos EU
2. **Azure OpenAI:** Los datos NO se usan para entrenar modelos de OpenAI cuando se usa via Azure
3. **Cifrado en reposo:** Azure MySQL/PostgreSQL y Key Vault cifran datos en reposo por defecto (AES-256)
4. **Cifrado en transito:** Todo el trafico es HTTPS/TLS 1.2+
5. **Mapa de sustitucion:** Se destruye al cerrar el ticket, garantizando el derecho al olvido
6. **Logs:** El audit_log registra accesos pero nunca almacena PII
7. **Acceso:** Managed Identity elimina la necesidad de credenciales hardcodeadas
