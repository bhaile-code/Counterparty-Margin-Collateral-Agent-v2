"""
Data models for multi-agent normalization system.

Defines schemas for:
- Reasoning steps and chains
- Ambiguity detection and resolution
- Validation results
- Agent results and orchestration
- Normalized field types
"""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime


class AmbiguitySeverity(str, Enum):
    """Severity level for detected ambiguities"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ReasoningStep(BaseModel):
    """Single step in an agent's reasoning chain"""
    step_number: int
    step_name: str
    input: Dict[str, Any]
    output: Dict[str, Any]
    model_used: str  # "haiku", "sonnet", "rule-based"
    reasoning: str
    confidence: Optional[float] = None
    duration_seconds: Optional[float] = None


class Ambiguity(BaseModel):
    """Single ambiguity detected in data"""
    issue: str
    severity: AmbiguitySeverity
    field: str
    suggested_resolution: Optional[str] = None


class AmbiguityDetection(BaseModel):
    """Result of ambiguity detection step"""
    step_number: int = 2
    ambiguities: List[Ambiguity]
    needs_context: bool
    needs_resolution: bool
    reasoning: str


class Resolution(BaseModel):
    """Resolution for a detected ambiguity"""
    ambiguity: str
    interpretation: str
    reasoning: str
    confidence: float
    sources_used: List[str]  # ["csa_convention", "document_context", "domain_knowledge"]


class AmbiguityResolution(BaseModel):
    """Result of ambiguity resolution step"""
    step_number: int = 3
    resolutions: List[Resolution]
    model_used: str = "sonnet"


class Correction(BaseModel):
    """Self-correction made by agent"""
    correction_type: str  # "taxonomy", "logic", "format"
    original_value: Any
    corrected_value: Any
    reasoning: str
    confidence: float


class ValidationResult(BaseModel):
    """Result of validation step"""
    step_number: int
    passed: bool
    issues: List[str] = []
    corrections: List[Correction] = []
    suggestions: List[str] = []
    reasoning: str


class AccuracyMetrics(BaseModel):
    """Accuracy metrics for validation against ground truth"""
    precision: float = Field(..., description="TP / (TP + FP)")
    recall: float = Field(..., description="TP / (TP + FN)")
    f1_score: float = Field(..., description="Harmonic mean of precision and recall")
    accuracy: float = Field(..., description="Overall accuracy: TP / Total")
    error_rate: float = Field(..., description="Errors / Total")
    true_positives: int
    false_positives: int
    false_negatives: int
    total_fields: int
    error_count: int


class AgentResult(BaseModel):
    """Result from a single normalizer agent"""
    agent_name: str
    data: Dict[str, Any]  # Normalized data
    confidence: float
    reasoning_chain: List[ReasoningStep]
    self_corrections: int = 0
    requires_human_review: bool = False
    human_review_reason: Optional[str] = None
    processing_time_seconds: float
    accuracy_metrics: Optional[AccuracyMetrics] = Field(
        None,
        description="Accuracy metrics if ground truth is available"
    )


class ContextChunk(BaseModel):
    """Document context chunk accessed by agent"""
    chunk_id: str
    text: str
    page: int
    bounding_box: Optional[Dict[str, float]] = None


class NormalizedTime(BaseModel):
    """Normalized time field with timezone"""
    time: str  # HH:MM:SS format
    timezone: Optional[str] = None  # IANA timezone name (e.g., "America/New_York")
    description: Optional[str] = None  # "close of business", "end of day", etc.
    raw_value: str
    confidence: float
    inference_source: Optional[str] = None  # "explicit", "context", "counterparty"
    requires_human_review: bool = False
    reasoning_chain: Optional[List[ReasoningStep]] = None


class NormalizedCurrency(BaseModel):
    """Normalized currency/amount field"""
    amount: Optional[float] = None  # None for "Not Applicable"
    currency_code: Optional[str] = None  # ISO 4217, None for special values
    is_infinity: bool = False
    is_not_applicable: bool = False
    raw_value: str
    confidence: float = 1.0
    reasoning_chain: Optional[List[ReasoningStep]] = None


class NormalizedDate(BaseModel):
    """Normalized date field"""
    date: str  # YYYY-MM-DD format
    format_detected: str
    raw_value: str
    confidence: float = 1.0


class ValidationCheck(BaseModel):
    """Single validation check result"""
    check_name: str
    category: str  # "currency", "timezone", "date", "business_rules", "collateral"
    status: Literal["passed", "failed", "warning"]
    details: str
    affected_fields: Optional[List[str]] = None


class ValidationWarning(BaseModel):
    """Validation warning"""
    check: str
    severity: Literal["low", "medium", "high"]
    message: str
    affected_fields: List[str]
    recommendation: str


class ValidationError(BaseModel):
    """Validation error"""
    check: str
    message: str
    affected_fields: List[str]
    blocking: bool  # If True, prevents further processing


class ValidationReport(BaseModel):
    """Cross-field validation report"""
    passed: bool
    checks_performed: int
    checks_passed: int
    checks_failed: int
    warnings: List[ValidationWarning] = []
    errors: List[ValidationError] = []
    recommendations: List[str] = []
    detailed_checks: List[ValidationCheck] = []


class ProcessingSummary(BaseModel):
    """Summary of processing across all agents"""
    total_processing_time_seconds: float
    agents_used: List[str]
    total_reasoning_steps: int
    total_self_corrections: int
    models_used: List[str]
    context_accessed: bool
    items_requiring_review: int
    accuracy_metrics: Optional[AccuracyMetrics] = Field(
        None,
        description="Aggregate accuracy metrics across all agents if ground truth is available"
    )
    accuracy_available: bool = Field(
        False,
        description="Whether ground truth data was available for accuracy calculation"
    )


class NormalizedResult(BaseModel):
    """Final aggregated result from all agents"""
    normalized_data_id: str
    document_id: str
    extraction_id: str
    overall_confidence: float
    requires_human_review: bool
    agent_results: Dict[str, AgentResult]  # {"collateral": ..., "temporal": ..., "currency": ...}
    validation_report: ValidationReport
    processing_summary: ProcessingSummary
    created_at: str

    class Config:
        json_schema_extra = {
            "example": {
                "normalized_data_id": "norm_abc123",
                "document_id": "doc_xyz789",
                "extraction_id": "ext_abc123",
                "overall_confidence": 0.94,
                "requires_human_review": False,
                "agent_results": {
                    "collateral": {
                        "agent_name": "CollateralNormalizerAgent",
                        "confidence": 0.92,
                        "self_corrections": 2,
                        "processing_time_seconds": 35.5
                    }
                }
            }
        }
