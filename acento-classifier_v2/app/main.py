"""
AcentoPartners Email Classifier - Main Application
FastAPI + Ollama LLM for intelligent email classification.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from app.core.config import settings
from app.models.database import init_db
from app.api.routes import router

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    logger.info("=" * 60)
    logger.info(f"  {settings.app_name}")
    logger.info(f"  Ollama: {settings.ollama_base_url} | Model: {settings.ollama_model}")
    logger.info(f"  Sample emails: {settings.sample_emails_path}")
    logger.info("=" * 60)

    # Create data directory
    Path("data").mkdir(exist_ok=True)

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Check Ollama
    from app.services.classifier.llm_classifier import classifier
    if await classifier.check_model_available():
        logger.info(f"Ollama model '{settings.ollama_model}' is ready")
    else:
        logger.warning(
            f"Ollama model '{settings.ollama_model}' not available! "
            f"Run: ollama pull {settings.ollama_model}"
        )

    yield

    logger.info("Shutting down...")


app = FastAPI(
    title=settings.app_name,
    description=(
        "AI-powered email classifier for AcentoPartners. "
        "Classifies incoming lender emails by lender name and waiver type "
        "using a local LLM (Ollama) with RAG-based knowledge base."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routes
app.include_router(router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "app": settings.app_name,
        "version": "0.1.0",
        "docs": "/docs",
        "endpoints": {
            "health": "/api/v1/health",
            "classify_upload": "POST /api/v1/classify/upload",
            "classify_batch": "POST /api/v1/classify/batch",
            "classify_outlook": "POST /api/v1/classify/outlook",
            "classifications": "/api/v1/classifications",
            "stats": "/api/v1/stats",
            "knowledge_base": "/api/v1/knowledge-base",
        },
    }
