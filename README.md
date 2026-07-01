# AcentoPartners Email Classifier (OGM_Lenders)

[![CI](https://github.com/CarlosMartinez2018/OGM_Lenders/actions/workflows/ci.yml/badge.svg)](https://github.com/CarlosMartinez2018/OGM_Lenders/actions/workflows/ci.yml)

AI-powered email classification system for AcentoPartners. Classifies incoming
lender/bank insurance-compliance emails by **Lender** and **Waiver Type** using a
local LLM (**Ollama**, `llama3.1:8b`) with a knowledge base stored in **PostgreSQL**.

This is **Phase 1** (Ingest + Classify) of a larger end-to-end waiver-management
pipeline (Ingest → Classify → Retrieve → Assemble → Respond). See `CONTEXTO.md`
for the full business context and roadmap.

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Email Sources   │     │   FastAPI     │     │   Ollama LLM    │
│                  │────▶│   Server      │────▶│  (llama3.1:8b)  │
│ • .eml folder    │     │              │     │                 │
│ • Outlook/Graph  │     │ + Knowledge  │◀────│  JSON response  │
│ • Upload API     │     │   Base (RAG) │     │                 │
└─────────────────┘     └──────┬───────┘     └─────────────────┘
                               │
                        ┌──────▼───────┐
                        │  PostgreSQL   │
                        │ lenders /     │
                        │ waivers /     │
                        │ classifications│
                        └──────────────┘
```

The **knowledge base lives in PostgreSQL** (`lenders`, `lender_aliases`,
`lender_domains`, `waivers`). If the DB has no active lenders, the classifier
falls back to the static matrix in `app/core/knowledge_base.py`.

## Quick Start

### 1. Start infrastructure (PostgreSQL + Ollama) with Docker

```bash
# Brings up postgres, ollama, pulls llama3.1:8b, and the FastAPI app
docker-compose up -d

# ...or just the infra, if you want to run the app locally:
docker-compose up -d postgres ollama ollama-pull
```

PostgreSQL is exposed on host port **5433** (mapped to 5432 inside the container).
Ollama listens on **11434**.

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env: DATABASE_URL, OLLAMA_MODEL, and (optional) Azure/Outlook credentials.
# Never commit .env — it is gitignored.
```

Set `USE_MOCK_LLM=true` to run the keyword-based mock classifier without Ollama
(useful for local development and tests).

### 3. Install dependencies & run the server (local)

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000/docs for the interactive Swagger UI.

## Usage

### Ingest emails into PostgreSQL (Stage 1)

```bash
# Local .eml files (all dates)
python ingest_today.py --source file --all-dates

# Outlook, specific month (requires Azure credentials configured)
python ingest_today.py --source outlook --month 3 --year 2026
```

### Classify (Stage 2)

```bash
# Batch a folder of .eml files
curl -X POST http://localhost:8000/api/v1/classify/batch \
  -H "Content-Type: application/json" \
  -d '{"folder_path": "./sample_emails", "max_emails": 10}'

# Upload a single .eml
curl -X POST http://localhost:8000/api/v1/classify/upload \
  -F "file=@/path/to/email.eml"

# From Outlook
curl -X POST http://localhost:8000/api/v1/classify/outlook \
  -H "Content-Type: application/json" \
  -d '{"num_emails": 5, "folder": "Inbox"}'
```

### Review results

```bash
curl http://localhost:8000/api/v1/classifications
curl "http://localhost:8000/api/v1/classifications?lender=JLL"
curl http://localhost:8000/api/v1/stats
curl http://localhost:8000/api/v1/review-queue   # human-in-the-loop queue

# WaiverPack readiness for a classification (Stage 4: Assemble) —
# reconciles KB-required documents against the ones retrieved for the email.
curl http://localhost:8000/api/v1/classifications/<id>/waiver-pack
```

## Outlook Integration (Microsoft Graph API)

1. Register an app in the [Azure Portal](https://portal.azure.com) →
   **App registrations** (single tenant, no redirect URI — client-credentials flow).
2. **API permissions** → Microsoft Graph → Application permissions → `Mail.Read`
   → **Grant admin consent**.
3. **Certificates & secrets** → new client secret; copy the **Value**.
4. Fill `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`,
   `OUTLOOK_MAILBOX` in `.env`.

> Security: `.env` is gitignored. Never commit real secrets. If a secret is ever
> committed, rotate it immediately in the Azure Portal.

## Project Structure

```
OGM_Lenders/
├── app/
│   ├── main.py                       # FastAPI application
│   ├── api/
│   │   ├── routes.py                 # Classification / review endpoints
│   │   ├── lenders.py                # Lender KB CRUD
│   │   └── emails.py                 # Parsed-email endpoints
│   ├── core/
│   │   ├── config.py                 # Settings (Pydantic)
│   │   ├── knowledge_base.py         # Static fallback lender/waiver matrix
│   │   └── business_context.json     # Company context + prompt guardrails
│   ├── models/
│   │   ├── database.py               # SQLAlchemy models (PostgreSQL)
│   │   └── schemas.py                # Pydantic schemas
│   └── services/
│       ├── orchestrator.py           # Classification pipeline
│       ├── email_parser/parser.py    # .eml parser
│       ├── classifier/llm_classifier.py  # Ollama LLM classifier
│       └── outlook/connector.py      # Microsoft Graph API
├── apps/waiver_lender_classifier/    # React + Vite dashboard (source)
├── sample_emails/                    # Example .eml files
├── ingest_today.py                   # Ingestion CLI (file / outlook)
├── docker-compose.yml                # postgres + ollama + app
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```

## Classification Matrix

| Lender | Waiver Type |
|--------|-------------|
| JLL (Insurance Servicing) | Assault & Battery (A&B) sublimit |
| JLL (Insurance Servicing) | Sexual Abuse & Molestation (SAM) |
| JLL (Insurance Servicing) | Equipment Breakdown (EB) limit |
| Capital One (Servicing) | Full Policy Package timing |
| Freddie Mac (via JLL Real Estate Capital) | Additional Insured/Mortgagee wording |
| Grandbridge / KeyBank / Wells Fargo | OL / BI / EPI specifics |
| Berkadia | Invoice components (Excess/Terrorism) & Address |
| NEWMARK (MCM Servicing) | Address / Excess lines |
| Greystone | ACORD-gate for payment & Umbrella clarity |
| CBRE | General compliance |
| M&T Bank | Multi-issue compliance |

## LLM Model Notes

- **Recommended**: `llama3.1:8b` — best balance of speed and accuracy
- **Alternative**: `mistral:7b` — slightly faster, good for testing
- **Best accuracy**: `llama3.1:70b` — requires 40GB+ VRAM
- Temperature is set to **0.1** for consistent, deterministic classifications
- JSON mode is enforced via Ollama's `format="json"` parameter
- The prompt includes anti-prompt-injection fencing and keyword-based escalation
  (see `app/core/business_context.json`)

## Testing

```bash
# Tests run against the mock classifier (no Ollama required)
USE_MOCK_LLM=true pytest
```
