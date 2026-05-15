# AcentoPartners Email Classifier

AI-powered email classification system for AcentoPartners. Classifies incoming lender/bank emails by **Lender** and **Waiver Type** using a local LLM (Ollama) with a RAG-based knowledge base.

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
                        │   SQLite DB   │
                        │ classifications│
                        └──────────────┘
```

## Quick Start

### 1. Install Ollama & Pull Model

```bash
# Install Ollama (macOS)
brew install ollama

# Install Ollama (Linux)
curl -fsSL https://ollama.com/install.sh | sh

# Start Ollama server
ollama serve

# Pull the model (in another terminal)
ollama pull llama3.1:8b

# Alternative lighter model:
# ollama pull mistral:7b
```

### 2. Setup Project

```bash
# Clone/navigate to project
cd acento-classifier

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Copy environment config
cp .env.example .env
# Edit .env with your settings (Ollama URL, email paths, etc.)
```

### 3. Run the Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000/docs for the interactive API docs (Swagger UI).

## Usage

### Option A: Classify .eml Files from a Folder (Batch)

Place your `.eml` files in the `sample_emails/` folder, then:

```bash
curl -X POST http://localhost:8000/api/v1/classify/batch \
  -H "Content-Type: application/json" \
  -d '{"folder_path": "./sample_emails", "max_emails": 10}'
```

### Option B: Upload a Single .eml File

```bash
curl -X POST http://localhost:8000/api/v1/classify/upload \
  -F "file=@/path/to/email.eml"
```

### Option C: Classify from Outlook (Microsoft Graph API)

First configure Azure AD credentials in `.env`, then:

```bash
# Test connection
curl http://localhost:8000/api/v1/outlook/test

# Classify recent emails
curl -X POST http://localhost:8000/api/v1/classify/outlook \
  -H "Content-Type: application/json" \
  -d '{"num_emails": 5, "folder": "Inbox"}'
```

### View Results

```bash
# List all classifications
curl http://localhost:8000/api/v1/classifications

# Filter by lender
curl "http://localhost:8000/api/v1/classifications?lender=JLL"

# Get statistics
curl http://localhost:8000/api/v1/stats
```

## Outlook Integration Setup (Microsoft Graph API)

### Step 1: Register App in Azure Portal

1. Go to [Azure Portal](https://portal.azure.com) → **App registrations** → **New registration**
2. Name: `AcentoPartners Email Classifier`
3. Account type: **Single tenant**
4. Redirect URI: leave blank (we use client credentials flow)

### Step 2: Configure API Permissions

1. Go to **API permissions** → **Add a permission**
2. Select **Microsoft Graph** → **Application permissions**
3. Add: `Mail.Read`
4. Click **Grant admin consent** (requires admin)

### Step 3: Create Client Secret

1. Go to **Certificates & secrets** → **New client secret**
2. Description: `acento-classifier`
3. Copy the **Value** (not the Secret ID)

### Step 4: Update .env

```env
AZURE_TENANT_ID=your-directory-tenant-id
AZURE_CLIENT_ID=your-application-client-id
AZURE_CLIENT_SECRET=the-secret-value-you-copied
OUTLOOK_MAILBOX=waivers@acentopartners.com
```

## Project Structure

```
acento-classifier/
├── app/
│   ├── main.py                          # FastAPI application
│   ├── api/
│   │   └── routes.py                    # API endpoints
│   ├── core/
│   │   ├── config.py                    # Settings (Pydantic)
│   │   └── knowledge_base.py            # Lender/waiver matrix
│   ├── models/
│   │   ├── database.py                  # SQLAlchemy models
│   │   └── schemas.py                   # Pydantic schemas
│   └── services/
│       ├── orchestrator.py              # Classification pipeline
│       ├── email_parser/
│       │   └── parser.py                # .eml file parser
│       ├── classifier/
│       │   └── llm_classifier.py        # Ollama LLM classifier
│       └── outlook/
│           └── connector.py             # Microsoft Graph API
├── sample_emails/                       # Drop .eml files here
├── data/                                # SQLite DB (auto-created)
├── requirements.txt
├── .env.example
└── README.md
```

## Classification Matrix

The system classifies emails into these lender/waiver combinations:

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

## LLM Model Notes

- **Recommended**: `llama3.1:8b` — best balance of speed and accuracy
- **Alternative**: `mistral:7b` — slightly faster, good for testing
- **Best accuracy**: `llama3.1:70b` — requires 40GB+ VRAM
- Temperature is set to **0.1** for consistent, deterministic classifications
- JSON mode is enforced via Ollama's `format="json"` parameter
