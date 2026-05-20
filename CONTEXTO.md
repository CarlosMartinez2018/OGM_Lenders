# CONTEXTO — AcentoPartners AI-Powered Waiver Management Platform

> **Fuente**: Video "REVISIÓN HIST. USUARIO AXA" — Reunión del 16 de marzo de 2026  
> **Presentación**: `AcentoPartners_Presentation_v2.pptx` (10 slides)  
> **Preparado por**: OGM para AcentoPartners  
> **Clasificación**: CONFIDENCIAL  
> **Participantes**: Manuel Cruz (presentador), Carlos Alberto Martínez, Diana Carolina Páez Rincón  

---

## 1. Contexto del Negocio

### ¿Qué es AcentoPartners?
AcentoPartners (junto con Captive Advisory Partners) es una firma que gestiona **pólizas de seguro e insurance compliance** para propiedades inmobiliarias (multifamily housing). Los operadores manejan comunicaciones con **lenders (prestamistas)** que exigen cumplimiento de requisitos de seguros como condición de los préstamos hipotecarios.

### El Problema ("The Challenge")
Los operadores enfrentan 4 puntos de dolor principales:

1. **Manual Email Triage**: Los operadores leen y clasifican manualmente emails de 10+ lenders con diferentes tipos de waiver, triggers y requisitos documentales.
2. **Scattered Documents**: Los documentos requeridos (ACORD forms, SOVs, policies, loss runs) están dispersos en SharePoint, OneDrive, bases de datos y drives locales.
3. **Complex Assembly Rules**: Cada combinación lender/waiver requiere un WaiverPack específico con evidencia única, endorsements y formatos de respuesta.
4. **Compliance Risk**: Deadlines incumplidos o documentación incorrecta genera flags de non-compliance de Capital One, JLL, Freddie Mac, CBRE, M&T Bank, y otros.

---

## 2. La Solución — AI Pipeline End-to-End

**Visión**: Pipeline de IA de extremo a extremo: de email a respuesta en **minutos, no horas**.

### Pipeline de 5 Etapas:

| Etapa | Nombre | Descripción |
|-------|--------|-------------|
| 1 | **Ingest** | Email + OCR |
| 2 | **Classify** | LLM + Knowledge Base |
| 3 | **Retrieve** | Multi-source document retrieval |
| 4 | **Assemble** | WaiverPack assembly |
| 5 | **Respond** | Draft + Send |

### Capacidades de Phase 1 (COMPLETE):

- ✅ **LLM Classification**: AI clasifica emails por lender + waiver type usando LLM local (Ollama) con contexto de knowledge base y domain detection
- ✅ **Human-in-the-Loop**: Review queue para confianza media/baja. Operadores aprueban o corrigen. Correcciones enriquecen automáticamente desde knowledge base
- ✅ **Multi-Label Detection**: Identifica issues primarios + secundarios por email. Domain-aware hints (TO > CC > FROM) para identificación de lender

---

## 3. Phase 1 Delivered (Estado actual del código)

### Backend — FastAPI + Ollama
- ✅ FastAPI async server con SQLAlchemy + SQLite
- ✅ Ollama LLM integration (llama3.1:8b local)
- ✅ .eml parser: FROM, TO, CC, body, attachments
- ✅ Knowledge Base: 9 lenders, 11 waiver entries
- ✅ Domain-aware lender detection (TO > CC > FROM)
- ✅ Multi-label classification (primary + secondary)
- ✅ Confidence scoring: high / medium / low routing
- ✅ Review queue + approve/correct API endpoints
- ✅ KB re-enrichment on corrections

### Dashboard — React (NO incluido en el código actual)
- ✅ Stats overview: total, avg confidence, auto-rate
- ✅ Charts: by lender (color-coded) + by waiver type
- ✅ Classify tab: upload .eml or batch folder
- ✅ History tab: all classifications with status badges
- ✅ Review Queue with pending count badge
- ✅ Correction modal: approve or correct with dropdowns
- ✅ Dynamic waiver filtering by lender (valid combos)
- ✅ Detail modal: full KB-enriched classification view
- ✅ Correction rate tracking in stats dashboard

---

## 4. Classification Engine — Detalle Técnico

### Classification Flow:
1. Email arrives → .eml parsed (TO, CC, FROM, body)
2. Domain detection identifies lender (TO > CC > FROM)
3. LLM receives email + KB context + domain hint
4. Returns: lender, primary waiver, secondary issues
5. Confidence score determines routing:
   - **>85%**: Auto-process (no human needed)
   - **60-85%**: Human review queue
   - **<60%**: Manual classification
6. Corrections re-enrich KB fields automatically

### Knowledge Base (9 Lenders):

| Lender | Waiver Types |
|--------|-------------|
| **JLL** | A&B, SAM, EB Limit |
| **Capital One** | Full Policy Package |
| **Freddie Mac** | AI/Mortgagee Wording |
| **Grandbridge/KeyBank** | OL/BI/EPI Specifics |
| **Berkadia** | Invoice & Address |
| **NEWMARK** | Address / Excess Lines |
| **Greystone** | ACORD-gate & Umbrella |
| **CBRE** ★ | General Compliance ★ |
| **M&T Bank** ★ | Multi-issue Compliance ★ |

> ★ CBRE y M&T Bank fueron **agregados desde análisis de emails reales de producción**

### Dominios internos de la empresa:
- `acentopartners.com`
- `captiveadvisorypartners.com`

### Personas clave mencionadas en emails de producción:
- **Terri Schell** — Agente de seguros en Captive Advisory Partners
- **Deb Tivnan** — Captive Advisory Partners
- **Marc Ross** — AcentoPartners

---

## 5. LLM Prompt Engineering (del código original completo)

El prompt del clasificador incluye:
- **CRITICAL CONTEXT**: Los emails son típicamente RESPUESTAS del agente de seguros (Terri Schell) TO al lender. El campo TO identifica al LENDER (no FROM).
- **DOMAIN HINT**: Pre-identificación del lender por dominio de email
- **KNOWLEDGE BASE**: Matriz completa lender/waiver como contexto
- **CLASSIFICATION INSTRUCTIONS**: 
  1. LENDER
  2. PRIMARY WAIVER TYPE
  3. SECONDARY ISSUES
  4. TRIGGER description
  5. CONFIDENCE score (0.0-1.0)
- **Output format**: JSON estricto

---

## 6. Emails de Producción (sample_emails)

El proyecto original contiene una carpeta `sample_emails/real/` con **10+ emails reales** de producción:

1. `01_Waiver_Request_AB_Sublimit_Defici...` — A&B waiver request
2. `02_RE_Sexual_Abuse_Molestation_Cov...` — SAM coverage
3. `03_Equipment_Breakdown_Limit_Deficie...` — EB limit deficiency
4. `04_NON-COMPLIANCE_NOTICE_-_Full_...` — Non-compliance notice
5. `05_Freddie_Mac_Wording_Deficiency_...` — Freddie Mac wording
6. `06_OL_BI_Structure_Review_-_Gateway_...` — OL/BI structure review
7. `07_Invoice_Clarification_Needed_-_Terro...` — Invoice clarification
8. `08_Address_Correction_Excess_Line_Re...` — Address correction
9. `09_ACORD_25-28_Required_Before_Pay...` — ACORD requirement
10. `10_Security_Assessment_Request_-_AB_...` — Security assessment

Además hay emails adicionales de producción visible en el explorer:
- `RE_Property Review Questions` (emails sobre Property Certificates con preguntas de lenders sobre SOV, blanket limits, deductibles, BI/OL, Equipment Breakdown, terrorism, mortgagee wording)
- FW/RE threads de Non-Compliance Agent notices
- Insurance Renewal Notices
- Incident reports (falls, sidewalk concerns, etc.)
- EXTERNAL emails de lenders

---

## 7. Estructura del Proyecto Original (completa, del video)

```
ACENTO-CLASSIFIER/
├── app/
│   ├── {api, core, services, models, templates}
│   ├── api/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   └── knowledge_base.py
│   ├── models/
│   ├── services/
│   │   ├── {email_parser, classifier, outlook}
│   │   ├── classifier/
│   │   │   ├── __init__.py
│   │   │   └── llm_classifier.py
│   │   ├── email_parser/
│   │   ├── outlook/
│   │   ├── __init__.py
│   │   └── orchestrator.py
│   ├── __init__.py
│   └── main.py
├── config/
├── data/
├── frontend/              ← React Dashboard (NO incluido en temp_acento)
├── sample_emails/
│   └── real/              ← 10+ emails .eml de producción
├── tests/
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── generate_sample_emails.py
├── README.md
└── requirements.txt
```

> **NOTA**: El código en `temp_acento` es una **versión reducida** del proyecto original. Faltan: `frontend/`, `config/`, `tests/`, `sample_emails/`, `Dockerfile`, `docker-compose.yml`, `.env.example`, `generate_sample_emails.py`, y los `__init__.py`.

---

## 8. Microsoft Graph API — Outlook Integration (Phase 2)

Se mostró un documento: **"AcentoPartners Microsoft Graph API Integration & Configuration Guide"**
- **Versión**: 2.0 — Phase 2: Outlook Integration
- **Fecha**: Febrero 2026
- **Contenido** (13 páginas):
  1. Overview & Architecture — Architecture Overview
  2. Prerequisites
  3. Azure AD App Registration
  4. API Permissions Configuration
  5. Client Secret Generation
  6. Application Configuration (.env)
  7. Security Best Practices — Restricting Mailbox Access (Recommended)
  8. Troubleshooting
  9. Appendix: API Permissions Reference — Useful Links

**Propósito**: Integrar la lectura directa del buzón de Outlook de AcentoPartners vía Microsoft Graph API para clasificación en vivo de emails de waiver.

---

## 9. Project Timeline

**Duración total**: 20 semanas (10 sprints) — Phase 1 complete, Phase 2 ready to start

| Fase | Semanas | Sprints | Descripción | Estado |
|------|---------|---------|-------------|--------|
| **Foundation** | W1-4 | S1-S2 | FastAPI, Ollama, .eml parser, SQLite, CI/CD | ✅ DONE |
| **Classification** | W5-8 | S3-S4 | LLM Engine, Knowledge Base, Confidence, Review UI, Corrections | 🟡 IN PROGRESS |
| **Retrieval** | W7-10 | S4-S5 | SharePoint, OneDrive, DB Connectors, Unified API | Pendiente |
| **Assembly** | W9-14 | S5-S7 | WaiverPack Builder, ACORD Auto-fill, Response Drafting | Pendiente |
| **Orchestration** | W13-18 | S7-S9 | Workflow Engine, Templates, SLA Monitoring, Dashboard | Pendiente |
| **Go-Live** | W19-20 | S10 | UAT, Training, Bug Fixes, Production Deployment | Pendiente |

**Hitos**:
- W4: Classification demo ✓
- W10: End-to-end prototype
- W16: Full integration
- W20: Go-live

---

## 10. Expected Outcomes (KPIs)

| Métrica | Objetivo |
|---------|----------|
| **Lender Detection** (domain-based) | 100% |
| **Auto-Process Rate** (high confidence) | 70%+ |
| **Email to Response** (from hours) | <5 min |
| **Audit Trail Coverage** | 100% |

### Key Benefits:
- ✅ Eliminar triage manual de email — operadores se enfocan en excepciones, no en clasificación rutinaria
- ✅ Reducir tiempo de respuesta de horas a minutos con ensamblaje automático de documentos
- ✅ Cero deadlines incumplidos con monitoreo de SLA y alertas proactivas por lender
- ✅ Mejora continua — correcciones retroalimentan para mejorar precisión con el tiempo
- ✅ Audit trail completo de compliance para cada waiver request procesada

---

## 11. Estado del Código en `temp_acento` (actualizado 2026-04-21)

> ✅ **Proyecto sincronizado desde GitHub** (`CarlosMartinez2018/OGM_Lenders/acento-classifier_v2`)

| Componente | Estado | Notas |
|-----------|--------|-------|
| Backend API (FastAPI) | ✅ Completo | 362 líneas, 13 endpoints |
| Knowledge Base | ✅ Completo | 11 entries, 9 lenders |
| Email Parser (.eml) | ✅ Completo | parse_eml_file + parse_eml_bytes |
| LLM Classifier (Ollama) | ✅ **REAL** | AsyncClient, llama3.1:8b, domain-aware |
| Outlook Connector | ✅ Completo | Microsoft Graph API via MSAL + httpx |
| Orchestrator | ✅ Completo | Single + batch + Outlook classification |
| `__init__.py` files | ✅ Restaurados | Todos los packages tienen __init__.py |
| Sample Emails (10) | ✅ Restaurados | 10 .eml de prueba en sample_emails/ |
| Docker/CI/CD | ✅ Restaurado | Dockerfile + docker-compose.yml |
| Backlog (Jira) | ✅ Nuevo | backlog/acento_backlog_jira.csv |
| Frontend (React) | ❌ Pendiente | No incluido en el repo |
| Tests | ❌ Pendiente | pytest configurado pero sin tests |
| .env.example | ❌ Pendiente | No incluido en el repo |

---

## 12. Próximos Pasos

1. **Crear `.env`** con configuración local (Ollama URL, modelo, paths)
2. **Instalar dependencias** (`pip install -r requirements.txt`)
3. **Instalar y configurar Ollama** con modelo `llama3.1:8b`
4. **Ejecutar el servidor** (`uvicorn app.main:app --reload`)
5. **Probar con sample_emails** (batch classification)
6. **Construir frontend React** dashboard
7. **Implementar Microsoft Graph API** integration (Phase 2)
8. **Agregar tests** unitarios y de integración
