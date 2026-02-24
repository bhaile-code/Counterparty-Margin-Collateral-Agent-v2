"""Main FastAPI application."""

import os
import json
import logging
from contextlib import asynccontextmanager
from typing import Any
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse as StarletteJSONResponse

from app.config import settings
from app.utils.file_storage import InfinityEncoder

logger = logging.getLogger(__name__)


class JSONResponse(StarletteJSONResponse):
    """Custom JSON response that handles NaN and Infinity values.

    Standard JSON spec doesn't support NaN/Infinity. This response uses
    InfinityEncoder to convert them to JSON-compatible strings:

    - float('inf') -> "Infinity" (properly quoted string in JSON)
    - float('-inf') -> "-Infinity" (properly quoted string in JSON)
    - float('nan') -> null

    Frontend will parse these strings back to JavaScript Infinity values.
    """

    def render(self, content: Any) -> bytes:
        # Pre-process: convert infinity floats to strings BEFORE JSON encoding
        # This ensures they are properly quoted in the output JSON
        content = InfinityEncoder.convert_infinity(content)
        return json.dumps(
            content,
            ensure_ascii=False,
            indent=None,
            separators=(",", ":"),
        ).encode("utf-8")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup: Create data directories
    os.makedirs(settings.pdf_dir, exist_ok=True)
    os.makedirs(settings.parsed_dir, exist_ok=True)
    os.makedirs(settings.extractions_dir, exist_ok=True)
    os.makedirs(settings.normalized_collateral_dir, exist_ok=True)
    os.makedirs(settings.csa_terms_dir, exist_ok=True)
    os.makedirs(settings.formula_patterns_dir, exist_ok=True)
    os.makedirs(settings.generated_scripts_dir, exist_ok=True)
    os.makedirs(settings.calculations_dir, exist_ok=True)
    os.makedirs(settings.explanations_dir, exist_ok=True)
    jobs_dir = os.path.join(settings.data_dir, "jobs")
    os.makedirs(jobs_dir, exist_ok=True)
    logger.info("Data directories initialized")
    logger.info(f"  - PDFs: {settings.pdf_dir}")
    logger.info(f"  - Parsed: {settings.parsed_dir}")
    logger.info(f"  - Extractions: {settings.extractions_dir}")
    logger.info(f"  - Normalized Collateral: {settings.normalized_collateral_dir}")
    logger.info(f"  - CSA Terms: {settings.csa_terms_dir}")
    logger.info(f"  - Formula Patterns: {settings.formula_patterns_dir}")
    logger.info(f"  - Generated Scripts: {settings.generated_scripts_dir}")
    logger.info(f"  - Calculations: {settings.calculations_dir}")
    logger.info(f"  - Explanations: {settings.explanations_dir}")
    logger.info(f"  - Jobs: {jobs_dir}")

    yield

    # Shutdown: Cleanup if needed
    logger.info("Shutting down...")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="AI-powered agent for OTC derivatives collateral management under ISDA/CSA agreements",
    version="0.2.0",
    lifespan=lifespan,
    default_response_class=JSONResponse,  # Use custom response to support Infinity/NaN
)

# Configure CORS - include both localhost and 127.0.0.1 to handle browser origin differences
cors_origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5175",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Margin Collateral Agent API",
        "version": "0.2.0",
        "status": "operational",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "landingai_configured": bool(settings.landingai_api_key),
        "anthropic_configured": bool(settings.anthropic_api_key),
    }


# Import and include routers
from app.api import documents, calculations, exports, collateral, formula_analysis, script_generation, analytics

app.include_router(documents.router, prefix="/api/v1/documents", tags=["documents"])
app.include_router(
    calculations.router, prefix="/api/v1/calculations", tags=["calculations"]
)
app.include_router(exports.router, prefix="/api/v1", tags=["exports"])
app.include_router(collateral.router, prefix="/api/v1/collateral", tags=["collateral"])
app.include_router(
    formula_analysis.router, prefix="/api/v1/formula-analysis", tags=["formula-analysis"]
)
app.include_router(
    script_generation.router, prefix="/api/v1/script-generation", tags=["script-generation"]
)
app.include_router(analytics.router, tags=["analytics"])

