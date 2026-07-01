# AcentoPartners Email Classifier

AI-powered email classification system for AcentoPartners. Classifies incoming lender/bank emails by **Lender** and **Waiver Type** using a local LLM (Ollama) with a RAG-based knowledge base.

## Architecture

```text
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Email Sources   │     │   FastAPI          │     │   Ollama LLM    │
│                  │────▶│   :8000            │────▶│  (llama3.1:8b)  │
│ • .eml folder    │     │                  │◀────│  JSON response  │
│ • Outlook/Graph  │     │ + Knowledge Base  │     │                 │
│ • Upload API     │     │   (RAG)           │     └─────────────────┘
└─────────────────┘     └────────┬─────────┘
                                  │ proxy /api
                         ┌────────▼─────────┐
                         │  React Frontend   │
                         │     :5173         │
                         └──────────────────┘
                                  │
                         ┌────────▼─────────┐
                         │   PostgreSQL DB   │
                         └──────────────────┘
```

---

## URLs de acceso

| Servicio | URL | Descripción |
| --- | --- | --- |
| **Frontend React** | `http://localhost:5173` | Interfaz principal (inicio aquí) |
| **Backend API** | `http://localhost:8000` | FastAPI server |
| **Swagger UI** | `http://localhost:8000/docs` | Documentación interactiva |
| **Emails UI** | `http://localhost:8000/api/v1/emails/form` | Vista HTML de emails |
| **Lenders UI** | `http://localhost:8000/api/v1/lenders/form` | Vista HTML de lenders |

> El frontend en `:5173` redirige automáticamente todas las llamadas `/api/...` al backend en `:8000`.

---

## Quick Start

### 1. Instalar Ollama y el modelo

```bash
# Windows: descargar desde https://ollama.com/download

# Iniciar servidor Ollama
ollama serve

# Descargar el modelo (en otra terminal)
ollama pull llama3.1:8b
```

### 2. Configurar el proyecto

```bash
# Crear entorno virtual
python -m venv venv

# Activar (Windows PowerShell)
venv\Scripts\Activate.ps1

# Instalar dependencias
pip install -r requirements.txt

# Copiar y editar variables de entorno
copy .env.example .env
# Editar .env con tus credenciales (DB, Azure, Ollama URL, etc.)
```

### 3. Iniciar el Backend (FastAPI)

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Disponible en `http://localhost:8000`

### 4. Iniciar el Frontend (React)

```bash
cd apps\waiver_lender_classifier

# Primera vez: instalar dependencias
npm install

# Iniciar servidor de desarrollo
npm run dev
```

Disponible en **`http://localhost:5173`** — este es el punto de entrada principal.

---

## Outlook Integration (Microsoft Graph API)

### Paso 1: Registrar la app en Azure Portal

1. Ir a [Azure Portal](https://portal.azure.com) → **App registrations** → **New registration**
2. Nombre: `AcentoPartners Email Classifier`
3. Account type: **Single tenant**
4. Redirect URI: dejar en blanco (usamos client credentials flow)

### Paso 2: Configurar permisos API

1. **API permissions** → **Add a permission**
2. Seleccionar **Microsoft Graph** → **Application permissions**
3. Agregar: `Mail.Read`
4. Hacer clic en **Grant admin consent**

### Paso 3: Crear Client Secret

1. **Certificates & secrets** → **New client secret**
2. Descripción: `acento-classifier`
3. Copiar el **Value** (no el Secret ID)

### Paso 4: Actualizar `.env`

```env
AZURE_TENANT_ID=your-directory-tenant-id
AZURE_CLIENT_ID=your-application-client-id
AZURE_CLIENT_SECRET=the-secret-value-you-copied
OUTLOOK_MAILBOX=waivers@acentopartners.com
```

---

## Estructura del proyecto

```text
acento-classifier_v2/
├── app/
│   ├── main.py                    # FastAPI application entry point
│   ├── api/
│   │   ├── routes.py              # Endpoints clasificación/outlook
│   │   ├── lenders.py             # CRUD lenders + form HTML
│   │   └── emails.py              # CRUD emails + form HTML
│   ├── core/
│   │   ├── config.py              # Settings (Pydantic)
│   │   └── knowledge_base.py      # Matriz lender/waiver (RAG)
│   ├── models/
│   │   ├── database.py            # SQLAlchemy models (PostgreSQL)
│   │   └── schemas.py             # Pydantic schemas
│   ├── services/
│   │   ├── orchestrator.py        # Pipeline de clasificación
│   │   ├── email_parser/
│   │   │   └── parser.py          # Parser de archivos .eml
│   │   ├── classifier/
│   │   │   └── llm_classifier.py  # Clasificador Ollama LLM
│   │   └── outlook/
│   │       └── connector.py       # Microsoft Graph API
│   └── templates/
│       ├── emails.html            # UI HTML emails
│       └── lenders.html           # UI HTML lenders
├── apps/
│   └── waiver_lender_classifier/  # Frontend React + Vite
│       ├── src/
│       ├── vite.config.js         # Puerto 5173, proxy → :8000
│       └── package.json
├── sample_emails/                 # Colocar archivos .eml aquí
├── ingest_today.py                # Script de ingesta manual
├── requirements.txt
├── .env.example
└── README.md
```

---

## Modelo LLM

| Modelo | RAM requerida | Recomendación |
| --- | --- | --- |
| `llama3.1:8b` | ~8 GB VRAM | Recomendado — balance velocidad/precisión |
| `mistral:7b` | ~6 GB VRAM | Alternativa más rápida |
| `llama3.1:70b` | ~40 GB VRAM | Mayor precisión |

- Temperatura: **0.1** para clasificaciones deterministas
- Formato JSON forzado via `format="json"` de Ollama
