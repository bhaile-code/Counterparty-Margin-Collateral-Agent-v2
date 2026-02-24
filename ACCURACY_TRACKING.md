# Accuracy Tracking System

This document describes the accuracy tracking system for the Counterparty Margin Collateral Agent, which measures the performance of document extraction and normalization against ground truth data.

## Overview

The accuracy tracking system provides **real accuracy percentages** at both extraction and normalization stages by comparing actual outputs against manually labeled ground truth datasets.

### What's Implemented

1. **Ground Truth Infrastructure** - Storage and schemas for expected extraction and normalization results
2. **AccuracyValidator Service** - Compares actual vs. expected results and calculates metrics
3. **Extended Data Models** - Accuracy metrics fields added to AgentResult and ProcessingSummary
4. **Analytics API Endpoints** - 7 new endpoints for querying accuracy metrics
5. **Benchmark Test Suite** - Automated tests that assert minimum accuracy thresholds
6. **Confidence Calibration** - Analysis of how well predicted confidence matches actual accuracy

## Directory Structure

```
backend/
├── tests/
│   ├── ground_truth/
│   │   ├── documents/                    # Source PDF files
│   │   ├── expected_extractions/         # Ground truth extraction data
│   │   │   ├── csa_credit_suisse_extraction.json
│   │   │   └── template_extraction.json
│   │   ├── expected_normalized/          # Ground truth normalization data
│   │   │   ├── csa_credit_suisse_normalized.json
│   │   │   └── template_normalized.json
│   │   └── README.md                     # Documentation on creating ground truth
│   └── benchmarks/
│       └── test_accuracy_benchmark.py    # Automated accuracy tests
├── app/
│   ├── services/
│   │   └── accuracy_validator.py         # Core validation service
│   ├── api/
│   │   └── analytics.py                  # Analytics API endpoints
│   └── models/
│       └── agent_schemas.py              # Extended with AccuracyMetrics
```

## Usage Guide

### 1. Creating Ground Truth Data

To measure accuracy, you must first create ground truth files for your test documents.

#### Step 1: Add Source Document

Copy your PDF to `backend/tests/ground_truth/documents/` with a unique ID (e.g., `csa_001.pdf`).

#### Step 2: Create Expected Extraction

Create `backend/tests/ground_truth/expected_extractions/csa_001_extraction.json`:

```json
{
  "document_id": "csa_001",
  "source_file": "csa_001.pdf",
  "expected_fields": {
    "agreement_info": {
      "agreement_title": "Credit Support Annex",
      "agreement_date": "2008-03-28",
      "party_a": "Party A Name",
      "party_b": "Party B Name"
    },
    "core_margin_terms": {
      "party_a_threshold": "$2,000,000",
      "party_b_threshold": "Infinity",
      "base_currency": "US Dollars"
    }
  }
}
```

#### Step 3: Create Expected Normalization

Create `backend/tests/ground_truth/expected_normalized/csa_001_normalized.json`:

```json
{
  "document_id": "csa_001",
  "expected_normalized_collateral": [
    {
      "standardized_type": "CASH_USD",
      "maturity_buckets": [{
        "valuation_percentage": 100.0,
        "haircut_percentage": 0.0
      }],
      "min_confidence": 0.95
    }
  ],
  "expected_currency": {
    "threshold_party_a": {
      "amount": 2000000.0,
      "currency_code": "USD"
    }
  }
}
```

See `backend/tests/ground_truth/README.md` for detailed instructions and template files.

### 2. Using the AccuracyValidator Service

```python
from app.services.accuracy_validator import AccuracyValidator

validator = AccuracyValidator()

# Validate extraction
extraction_result = validator.validate_extraction(
    document_id="csa_credit_suisse",
    extracted_fields=your_extracted_data
)

print(f"Extraction Accuracy: {extraction_result['overall_metrics']['accuracy']:.2%}")
print(f"Precision: {extraction_result['overall_metrics']['precision']:.2%}")
print(f"Recall: {extraction_result['overall_metrics']['recall']:.2%}")

# Validate normalization
normalization_result = validator.validate_normalization(
    document_id="csa_credit_suisse",
    normalized_data=your_normalized_data
)

print(f"Normalization Accuracy: {normalization_result['overall_metrics']['accuracy']:.2%}")
```

### 3. Using the Analytics API

#### Get Extraction Accuracy for a Specific Document

```bash
GET /api/v1/analytics/extraction-accuracy/{extraction_id}
```

**Response:**
```json
{
  "extraction_id": "extract_...",
  "validation_result": {
    "overall_metrics": {
      "accuracy": 0.96,
      "precision": 0.97,
      "recall": 0.95,
      "f1_score": 0.96,
      "error_rate": 0.04
    },
    "field_scores": {
      "agreement_info": {
        "party_a": 1.0,
        "party_b": 1.0,
        "agreement_date": 1.0
      },
      "core_margin_terms": {
        "threshold": 0.95,
        "base_currency": 1.0
      }
    },
    "errors": [...]
  }
}
```

#### Get Normalization Accuracy

```bash
GET /api/v1/analytics/normalization-accuracy/{normalization_id}
```

**Response:**
```json
{
  "normalization_id": "norm_...",
  "validation_result": {
    "overall_metrics": {
      "accuracy": 0.92,
      "precision": 0.94,
      "recall": 0.90
    },
    "component_scores": {
      "collateral": {"average_score": 0.90},
      "temporal": {"notification_time": 0.95},
      "currency": {"base_currency": 1.0}
    }
  }
}
```

#### Get Overall Accuracy Statistics

```bash
GET /api/v1/analytics/overall-accuracy?limit=100
```

**Response:**
```json
{
  "total_documents_processed": 100,
  "documents_validated": 15,
  "aggregate_statistics": {
    "total_documents": 15,
    "documents_passed": 14,
    "documents_failed": 1,
    "pass_rate": 0.933,
    "aggregate_metrics": {
      "accuracy": 0.94,
      "precision": 0.95,
      "recall": 0.93
    }
  }
}
```

#### Get Accuracy by Field Type

```bash
GET /api/v1/analytics/accuracy-by-field
```

**Response:**
```json
{
  "field_accuracy": {
    "eligible_collateral_table": {
      "average_accuracy": 0.85,
      "sample_count": 12,
      "min_accuracy": 0.70,
      "max_accuracy": 0.98
    },
    "core_margin_terms.threshold": {
      "average_accuracy": 0.98,
      "sample_count": 15
    }
  }
}
```

#### Get Confidence Calibration Analysis

```bash
GET /api/v1/analytics/confidence-calibration?bins=10
```

**Response:**
```json
{
  "calibration_curve": [
    {
      "bin_min": 0.8,
      "bin_max": 0.9,
      "avg_confidence": 0.85,
      "avg_accuracy": 0.82,
      "correct_rate": 0.80,
      "calibration_error": 0.05
    }
  ],
  "expected_calibration_error": 0.04,
  "interpretation": {
    "ece_meaning": "Lower is better. < 0.05 is well-calibrated",
    "curve_ideal": "avg_confidence should equal correct_rate"
  }
}
```

#### Get Error Analysis

```bash
GET /api/v1/analytics/error-analysis
```

**Response:**
```json
{
  "error_statistics": {
    "total_errors": 25,
    "by_type": {
      "extraction_mismatch": 15,
      "extraction_failure": 8,
      "normalization_error": 2
    },
    "by_section": {
      "eligible_collateral_table": 12,
      "core_margin_terms": 8,
      "agreement_info": 5
    },
    "by_field": {
      "eligible_collateral_table.row_5": {
        "count": 6,
        "examples": [...]
      }
    }
  }
}
```

#### Health Check

```bash
GET /api/v1/analytics/health
```

**Response:**
```json
{
  "status": "healthy",
  "ground_truth_available": true,
  "ground_truth_extractions": 2,
  "ground_truth_normalized": 2,
  "total_extractions": 150,
  "total_normalized": 45,
  "accuracy_validation_enabled": true
}
```

### 4. Running Benchmark Tests

Run the automated accuracy tests:

```bash
cd backend
pytest tests/benchmarks/test_accuracy_benchmark.py -v
```

**Test Categories:**

1. **TestExtractionAccuracy**
   - `test_agreement_info_extraction_accuracy` - Tests >95% accuracy on agreement fields
   - `test_core_margin_terms_extraction_accuracy` - Tests critical field accuracy
   - `test_overall_extraction_accuracy_threshold` - Tests overall >95% threshold
   - `test_no_critical_extraction_failures` - Ensures critical fields always extract

2. **TestNormalizationAccuracy**
   - `test_collateral_type_classification_accuracy` - Tests >90% type classification
   - `test_temporal_normalization_accuracy` - Tests >85% temporal field accuracy
   - `test_currency_normalization_accuracy` - Tests >95% currency accuracy
   - `test_maturity_bucket_accuracy` - Tests no overlapping buckets

3. **TestAggregateAccuracy**
   - `test_aggregate_accuracy_calculation` - Tests aggregate metric calculation
   - `test_pass_rate_calculation` - Tests pass rate computation

4. **TestErrorAnalysis**
   - `test_error_categorization` - Tests error type classification
   - `test_field_level_error_tracking` - Tests field-level error tracking

## Accuracy Metrics Explained

### Precision
**Formula:** `TP / (TP + FP)`

Measures how many extracted values were correct.
- High precision = Few false positives (incorrect extractions)
- **Target: >90%**

### Recall
**Formula:** `TP / (TP + FN)`

Measures how many expected values were found.
- High recall = Few false negatives (missed fields)
- **Target: >90%**

### F1 Score
**Formula:** `2 * (Precision * Recall) / (Precision + Recall)`

Harmonic mean balancing precision and recall.
- **Target: >90%**

### Accuracy
**Formula:** `TP / Total Fields`

Overall correctness rate.
- **Target for Extraction: >95%**
- **Target for Normalization: >90%**

### Error Rate
**Formula:** `Errors / Total Fields`

Percentage of fields with errors.
- **Target: <5%**

## Confidence Calibration

Confidence calibration measures how well the AI's predicted confidence scores match actual accuracy.

**Expected Calibration Error (ECE):**
- **< 0.05** - Well-calibrated (confidence matches accuracy)
- **0.05 - 0.15** - Moderately calibrated
- **> 0.15** - Poorly calibrated (confidence misleading)

**Use Case:** Optimize the confidence threshold for human review escalation.

Example: If documents with 85% confidence have only 70% actual accuracy, the system is overconfident and the threshold should be raised.

## Integration with Existing Workflow

The accuracy tracking system integrates seamlessly with your existing pipeline:

### Extraction Stage
```python
# Existing code
extraction_result = ade_service.extract_fields(parse_id)

# NEW: Validate accuracy if ground truth available
accuracy_result = accuracy_validator.validate_extraction(
    document_id=document_id,
    extracted_fields=extraction_result["extracted_fields"]
)

# Store accuracy metrics with extraction
extraction_result["accuracy_metrics"] = accuracy_result.get("overall_metrics")
```

### Normalization Stage
```python
# Existing code
normalized_result = orchestrator.normalize(extraction_id)

# NEW: Validate accuracy if ground truth available
accuracy_result = accuracy_validator.validate_normalization(
    document_id=document_id,
    normalized_data=normalized_result
)

# Store accuracy metrics with normalization
normalized_result["processing_summary"]["accuracy_metrics"] = accuracy_result.get("overall_metrics")
normalized_result["processing_summary"]["accuracy_available"] = True
```

## Best Practices

### Creating Ground Truth

1. **Quality over Quantity** - Start with 10-20 well-labeled documents
2. **Diversity** - Include various document formats and edge cases
3. **Double-Check** - Have multiple reviewers verify ground truth labels
4. **Version Control** - Commit ground truth files to git for reproducibility
5. **Update Regularly** - Add new ground truth when errors are discovered

### Using Accuracy Metrics

1. **Track Trends** - Monitor accuracy over time to detect regressions
2. **Identify Weak Points** - Use field-level accuracy to find problem areas
3. **Optimize Thresholds** - Use calibration data to set review thresholds
4. **Continuous Improvement** - Use error analysis to improve prompts/agents

### Setting Thresholds

**Recommended Accuracy Thresholds:**
- **Critical Fields** (party names, amounts, dates): >98%
- **Standard Fields** (other agreement terms): >95%
- **Complex Fields** (collateral tables, formulas): >90%
- **Overall Extraction**: >95%
- **Overall Normalization**: >90%

**Human Review Triggers:**
- Overall confidence < 85%
- Any agent confidence < 70%
- Accuracy (if available) < 90%
- Validation errors > 0

## Example: Complete Workflow with Accuracy Tracking

```python
from app.services.ade_service import ADEService
from app.services.normalization_orchestrator import NormalizationOrchestrator
from app.services.accuracy_validator import AccuracyValidator

# Initialize services
ade = ADEService()
orchestrator = NormalizationOrchestrator()
validator = AccuracyValidator()

# 1. Extract document
extraction = ade.extract_fields(parse_id)
print(f"Extracted {len(extraction['extracted_fields'])} sections")

# 2. Validate extraction accuracy
extraction_accuracy = validator.validate_extraction(
    document_id="csa_credit_suisse",
    extracted_fields=extraction["extracted_fields"]
)

if extraction_accuracy.get("available"):
    print(f"Extraction Accuracy: {extraction_accuracy['overall_metrics']['accuracy']:.2%}")
    print(f"Errors: {len(extraction_accuracy['errors'])}")

# 3. Normalize data
normalized = orchestrator.normalize_all_fields(extraction_id)
print(f"Normalized {len(normalized['normalized_collateral_table'])} collateral items")

# 4. Validate normalization accuracy
norm_accuracy = validator.validate_normalization(
    document_id="csa_credit_suisse",
    normalized_data=normalized
)

if norm_accuracy.get("available"):
    print(f"Normalization Accuracy: {norm_accuracy['overall_metrics']['accuracy']:.2%}")
    print(f"Component Scores: {norm_accuracy['component_scores']}")

# 5. Decide on human review
needs_review = (
    extraction_accuracy['overall_metrics']['accuracy'] < 0.90 or
    norm_accuracy['overall_metrics']['accuracy'] < 0.85 or
    normalized['overall_confidence'] < 0.80
)

if needs_review:
    print("Flagging for human review")
else:
    print("Accuracy acceptable, proceeding to calculation")
```

## Troubleshooting

### "No ground truth found" Error

**Cause:** Ground truth file doesn't exist for the document ID.

**Solution:**
1. Check that ground truth file exists: `backend/tests/ground_truth/expected_extractions/{document_id}_extraction.json`
2. Verify document_id matches the filename (without `_extraction.json`)
3. Create ground truth file if missing (see templates)

### Low Accuracy Scores

**Cause:** Mismatch between expected and actual values.

**Solution:**
1. Review errors: `result['errors']` shows specific mismatches
2. Check field-level scores: `result['field_scores']` shows which fields are problematic
3. Update ground truth if expected values were incorrect
4. Improve extraction/normalization if actual values are incorrect

### Calibration Shows Overconfidence

**Cause:** System reports high confidence but actual accuracy is lower.

**Solution:**
1. Increase human review threshold (e.g., from 0.85 to 0.90)
2. Add more diverse ground truth documents
3. Review agent prompts to reduce false confidence

## Future Enhancements

Potential additions to the accuracy tracking system:

1. **Automated Ground Truth Generation** - Use human corrections from production
2. **Active Learning** - Prioritize documents for labeling based on uncertainty
3. **Per-Document-Type Accuracy** - Track accuracy separately for different CSA types
4. **Temporal Tracking** - Monitor how accuracy changes over time
5. **A/B Testing Framework** - Compare different normalization strategies
6. **Cost vs. Accuracy Tradeoff** - Analyze relationship between model costs and accuracy

## Support

For questions or issues with the accuracy tracking system:

1. Review this documentation and `backend/tests/ground_truth/README.md`
2. Check the Analytics API health endpoint: `GET /api/v1/analytics/health`
3. Run benchmark tests: `pytest tests/benchmarks/test_accuracy_benchmark.py -v`
4. Review error logs in validation results
