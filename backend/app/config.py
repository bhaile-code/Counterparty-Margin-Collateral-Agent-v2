"""Application configuration using pydantic-settings."""

import logging
from pathlib import Path
from typing import Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Calculate base directory (backend/)
BASE_DIR = Path(__file__).parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "Margin Collateral Agent"
    debug: bool = False

    # API Keys
    landingai_api_key: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # LandingAI ADE API URLs
    landingai_parse_url: str = "https://api.va.landing.ai/v1/ade/parse"
    landingai_extract_url: str = "https://api.va.landing.ai/v1/ade/extract"
    landingai_timeout: int = 300  # 5 minutes for complex PDF parsing

    # File Storage (absolute paths)
    data_dir: str = str(BASE_DIR / "data")
    pdf_dir: str = str(BASE_DIR / "data" / "pdfs")
    parsed_dir: str = str(BASE_DIR / "data" / "parsed")
    extractions_dir: str = str(BASE_DIR / "data" / "extractions")
    normalized_collateral_dir: str = str(BASE_DIR / "data" / "normalized_collateral")
    normalized_multiagent_dir: str = str(BASE_DIR / "data" / "normalized_multiagent")
    csa_terms_dir: str = str(BASE_DIR / "data" / "csa_terms")
    formula_patterns_dir: str = str(BASE_DIR / "data" / "formula_patterns")
    generated_scripts_dir: str = str(BASE_DIR / "data" / "generated_scripts")
    calculations_dir: str = str(BASE_DIR / "data" / "calculations")
    explanations_dir: str = str(BASE_DIR / "data" / "explanations")
    max_upload_size: int = 52428800  # 50 MB in bytes

    # CORS
    cors_origins: Union[list[str], str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:5176",
        "http://localhost:5177",
        "http://localhost:5178",
    ]

    # Parallel Processing Optimization
    enable_parallel_processing: bool = True
    enable_parallel_item_processing: bool = True
    enable_parallel_agent_execution: bool = True

    # Dynamic concurrency based on API tier and document size
    max_concurrent_llm_calls: int = 60  # Base limit for medium documents (10-20 items)
    max_concurrent_llm_calls_burst: int = 150  # Burst capacity for large documents (requires Tier 3)
    api_calls_per_collateral_item: int = 4  # Average API calls per item

    # Batch processing for very large documents
    parallel_batch_size: int = 25  # Max items per batch for documents >50 items
    auto_batch_threshold: int = 50  # Item count threshold for automatic batching

    @field_validator("landingai_api_key", mode="after")
    @classmethod
    def validate_landingai_key(cls, v):
        """Validate LandingAI API key is configured."""
        if not v or v == "":
            logger.warning(
                "LandingAI API key not configured - document parsing will fail"
            )
        return v

    @field_validator("anthropic_api_key", mode="after")
    @classmethod
    def validate_anthropic_key(cls, v):
        """Validate Anthropic API key is configured."""
        if not v or v == "":
            logger.warning(
                "Anthropic API key not configured - explanation generation will fail"
            )
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse comma-separated CORS origins string."""
        if isinstance(v, str):
            # Split by comma and strip whitespace
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"), env_file_encoding="utf-8", case_sensitive=False
    )


# Global settings instance
settings = Settings()
