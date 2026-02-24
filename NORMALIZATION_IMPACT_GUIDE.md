# Normalization Impact Analysis

## Overview

The **Normalization Impact Analyzer** measures how much the multi-agent normalization system improves data quality by comparing accuracy **before normalization** (raw extraction) vs. **after normalization** (processed by agents).

This answers the critical question: **"Is the normalization pipeline worth the processing cost?"**

---

## What It Measures

### Before Normalization
- **Raw extraction accuracy** from LandingAI ADE
- Data as-is from PDF parsing
- No standardization, no validation, no type conversion

### After Normalization
- **Processed accuracy** after multi-agent normalization
- Data standardized by CollateralAgent, TemporalAgent, CurrencyAgent
- Includes self-corrections and validation

### The Difference
- **Absolute Improvement**: How many percentage points accuracy improved
- **Percentage Improvement**: Relative improvement rate
- **Field-level breakdown**: Which specific fields improved the most

---

## Key Metrics Provided

### 1. Overall Impact Metrics

```json
{
  "before_normalization": {
    "accuracy": 0.65  // 65% accuracy from raw extraction
  },
  "after_normalization": {
    "accuracy": 0.92  // 92% accuracy after normalization
  },
  "improvement": {
    "absolute": 0.27,      // +27 percentage points
    "percentage": 41.54,   // 41.54% relative improvement
    "description": "Substantial improvement - Normalization working well"
  }
}
```

### 2. Quality Level Assessment

**Before:**
- Excellent (≥95%)
- Good (≥90%)
- Acceptable (≥80%)
- Poor (≥70%)
- Inadequate (<70%)

**After:**
- Same scale showing quality improvement

### 3. Processing Value Assessment

Determines if normalization is worth the cost:

| Value Rating | Improvement | Justification |
|-------------|-------------|---------------|
| **High** | ≥10% | Normalization significantly improves data quality |
| **Medium** | 5-10% | Normalization provides measurable improvement |
| **Low** | 1-5% | Normalization provides minimal improvement |
| **Questionable** | <1% | Normalization may not justify processing cost |

### 4. Field-Level Impact

Shows which specific fields improved:

```
currency.base_currency      0.00% → 1.00%  (+1.00%)
temporal.notification_time  0.85% → 0.95%  (+0.10%)
collateral.overall          0.75% → 0.90%  (+0.15%)
```

### 5. Recommendations

Automated recommendations based on analysis:

- **Critical**: Normalization degrading quality (needs immediate fix)
- **High**: Specific fields degrading (targeted fixes needed)
- **Medium**: Minimal improvement (consider simplifying pipeline)
- **Low**: Normalization highly effective (continue approach)

---

## How to Use

### Option 1: API Endpoints

#### Get Impact for Specific Document

```bash
GET /api/v1/analytics/normalization-impact/{document_id}
```

**Response:**
```json
{
  "document_id": "e7f5357f...",
  "comparison_report": {
    "overall_impact": {
      "before_normalization": {"accuracy": 0.65},
      "after_normalization": {"accuracy": 0.92},
      "improvement": {
        "absolute": 0.27,
        "percentage": 41.54,
        "description": "Substantial improvement"
      }
    },
    "field_level_impact": {
      "field_improvements": {
        "currency.base_currency": {
          "before": 0.0,
          "after": 1.0,
          "improvement": 1.0
        }
      },
      "most_improved": ["currency.base_currency", "collateral.overall"],
      "degraded_fields": []
    },
    "processing_value": {
      "value_rating": "High",
      "justification": "Normalization significantly improves data quality",
      "worth_processing": true
    },
    "recommendations": [
      {
        "priority": "low",
        "category": "success",
        "message": "Normalization highly effective",
        "action": "Continue current approach"
      }
    ],
    "summary": {
      "before_quality": "Poor",
      "after_quality": "Excellent",
      "improvement_description": "Substantial improvement",
      "normalization_effective": true
    }
  }
}
```

#### Get Aggregate Impact Summary

```bash
GET /api/v1/analytics/normalization-impact-summary
```

**Response:**
```json
{
  "aggregate_impact": {
    "total_documents": 15,
    "average_metrics": {
      "before_normalization": 0.68,
      "after_normalization": 0.89,
      "average_improvement": 0.21
    },
    "quality_distribution": {
      "before": {
        "Poor": 8,
        "Acceptable": 5,
        "Good": 2
      },
      "after": {
        "Acceptable": 3,
        "Good": 7,
        "Excellent": 5
      }
    },
    "effectiveness": {
      "documents_improved": 14,
      "documents_degraded": 0,
      "documents_unchanged": 1,
      "improvement_rate": 0.933
    }
  }
}
```

### Option 2: Python Script

```bash
python test_normalization_impact.py
```

**Output:**
```
================================================================================
NORMALIZATION IMPACT ANALYSIS
Document ID: e7f5357f-4419-478e-95fe-b65c80304394
================================================================================

ACCURACY COMPARISON
--------------------------------------------------------------------------------
Before Normalization (Raw Extraction):  65.00%
After Normalization (Multi-Agent):      92.00%

Absolute Improvement:    +27.00%
Percentage Improvement:  +41.54%

Improvement Description: Substantial improvement - Normalization working well

QUALITY ASSESSMENT
--------------------------------------------------------------------------------
Before Quality: Poor
After Quality:  Excellent
Normalization Effective: Yes

FIELD-LEVEL IMPROVEMENTS
--------------------------------------------------------------------------------
  ↑ currency.base_currency              0.00% → 1.00%  (+1.00%)
  ↑ collateral.overall                  0.75% → 0.90%  (+0.15%)
  ↑ temporal.notification_time          0.85% → 0.95%  (+0.10%)
```

### Option 3: Python Code

```python
from app.services.normalization_impact_analyzer import NormalizationImpactAnalyzer

analyzer = NormalizationImpactAnalyzer()

# Analyze impact
report = analyzer.generate_comparison_report(
    document_id="csa_credit_suisse",
    extraction_data=raw_extraction,
    normalized_data=normalized_result
)

# Check improvement
improvement = report["overall_impact"]["improvement"]["absolute"]
print(f"Normalization improved accuracy by {improvement:.1%}")

# Check if worth processing
worth_it = report["processing_value"]["worth_processing"]
if worth_it:
    print("Normalization is worth the processing cost")
else:
    print("Consider simplifying normalization pipeline")
```

---

## Use Cases

### 1. **Pipeline Evaluation**

**Question:** Is our multi-agent normalization system adding value?

**Answer:** Compare before/after accuracy across all documents:
- If average improvement > 10%: High value, keep system
- If average improvement < 3%: Low value, simplify pipeline
- If improvement negative: Fix broken normalization logic

### 2. **Cost-Benefit Analysis**

**Question:** Does normalization justify the API costs?

**Calculation:**
```
Cost per document:
- ADE extraction: $0.10
- Multi-agent normalization: $0.50 (3 Claude calls)
- Total: $0.60

Benefit:
- Without normalization: 65% accuracy → 35% need human review
- With normalization: 92% accuracy → 8% need human review

Human review cost: $5/document

Without normalization: 35% × $5 = $1.75
With normalization: 8% × $5 = $0.40

Savings: $1.75 - $0.40 - $0.50 = $0.85 per document
```

### 3. **Agent Optimization**

**Question:** Which normalization agent provides the most value?

**Answer:** Check field-level improvements:
- CurrencyAgent: +30% improvement on currency fields → Keep
- TemporalAgent: +15% improvement on temporal fields → Keep
- CollateralAgent: +2% improvement on collateral → Consider simplifying

### 4. **Quality Monitoring**

**Question:** Is normalization degrading over time?

**Answer:** Track improvement trends:
- Week 1: +25% average improvement
- Week 2: +20% average improvement
- Week 3: +12% average improvement

**Action:** Investigate what changed (data quality, prompt drift, etc.)

### 5. **Human Review Optimization**

**Question:** What confidence threshold should trigger human review?

**Answer:** Use normalization impact + confidence:
- Before normalization accuracy < 70% + After normalization confidence < 85% = Review
- Otherwise: Auto-approve

---

## Interpretation Guide

### High Improvement (≥20%)

**Meaning:** Normalization is highly effective

**Example:**
- Before: 60% (Poor)
- After: 85% (Good)
- Improvement: +25%

**Action:** Continue current approach, normalization is essential

**Typical Causes:**
- Raw extraction has format inconsistencies
- Multi-agent reasoning resolves ambiguities well
- Type conversions improve standardization

### Moderate Improvement (10-20%)

**Meaning:** Normalization adding value

**Example:**
- Before: 75% (Acceptable)
- After: 88% (Good)
- Improvement: +13%

**Action:** Keep normalization, monitor for optimization opportunities

**Typical Causes:**
- Some fields benefit from normalization
- Self-corrections fixing minor issues

### Low Improvement (1-10%)

**Meaning:** Normalization has minor impact

**Example:**
- Before: 88% (Good)
- After: 92% (Excellent)
- Improvement: +4%

**Action:** Consider simplifying pipeline to reduce costs

**Typical Causes:**
- Raw extraction already high quality
- Normalization mainly adds metadata (confidence, reasoning chains)

### No Improvement (<1%)

**Meaning:** Normalization not adding value

**Example:**
- Before: 90% (Good)
- After: 90% (Good)
- Improvement: +0%

**Action:** Skip normalization for this document type, use raw extraction

**Typical Causes:**
- Data already standardized
- Ground truth matches extraction format
- Normalization pipeline not needed

### Negative Improvement (Degradation)

**Meaning:** Normalization is breaking data

**Example:**
- Before: 85% (Good)
- After: 75% (Acceptable)
- Improvement: -10% ⚠️

**Action:** **CRITICAL** - Fix normalization logic immediately

**Typical Causes:**
- Agent prompts overcorrecting
- Type conversion bugs
- Validation errors rejecting good data

---

## Best Practices

### 1. Measure Regularly

Run normalization impact analysis:
- **Daily**: For production pipelines
- **Per batch**: For large processing jobs
- **After changes**: When updating agent prompts or logic

### 2. Set Thresholds

Define minimum acceptable improvement:
```python
MIN_IMPROVEMENT_THRESHOLD = 0.05  # 5%

if improvement < MIN_IMPROVEMENT_THRESHOLD:
    logger.warning("Normalization not providing sufficient value")
    # Consider skipping normalization or simplifying
```

### 3. Monitor Degradation

Alert on negative improvements:
```python
if improvement < -0.02:  # 2% degradation
    alert_team("CRITICAL: Normalization degrading data quality")
    # Automatic rollback to previous version
```

### 4. Track Field-Level Patterns

Identify which fields benefit most:
```python
field_impact = analyzer.analyze_field_level_impact(...)

for field, data in field_impact["field_improvements"].items():
    if data["improvement"] > 0.20:
        # This field benefits greatly from normalization
        priority_fields.add(field)
```

### 5. A/B Testing

Compare normalization strategies:
```python
# Strategy A: Full multi-agent normalization
report_a = analyzer.analyze_impact(doc_id, extraction, normalized_full)

# Strategy B: Rule-based only
report_b = analyzer.analyze_impact(doc_id, extraction, normalized_rules)

# Choose better strategy
if report_a["improvement"] > report_b["improvement"]:
    use_strategy = "multi-agent"
else:
    use_strategy = "rule-based"
```

---

## Integration with Production

### Automatic Impact Tracking

```python
# In normalization orchestrator
def normalize_with_tracking(self, extraction_id: str):
    # Load extraction
    extraction = self.load_extraction(extraction_id)

    # Normalize
    normalized = self.normalize_all_fields(extraction_id)

    # Track impact (if ground truth available)
    impact = self.impact_analyzer.analyze_impact(
        document_id=extraction["document_id"],
        extraction_data=extraction["extracted_fields"],
        normalized_data=normalized
    )

    if impact:
        # Store impact metrics
        normalized["normalization_impact"] = impact.to_dict()

        # Log for monitoring
        logger.info(
            f"Normalization improved accuracy by {impact.improvement_absolute:.1%}"
        )

        # Alert if degradation
        if impact.improvement_absolute < -0.02:
            alert_team(f"Normalization degraded quality: {impact.improvement_absolute:.1%}")

    return normalized
```

### Dashboard Integration

Create a monitoring dashboard showing:
1. **Trend Chart**: Improvement over time
2. **Distribution**: Before/after quality levels
3. **ROI Calculation**: Cost vs. human review savings
4. **Field Heatmap**: Which fields improve most
5. **Alerts**: Degradation warnings

---

## Troubleshooting

### Issue: No improvement detected

**Symptoms:** Improvement = 0% consistently

**Causes:**
1. Raw extraction already perfect
2. Ground truth matches extraction format exactly
3. Normalization not making substantive changes

**Solutions:**
- Check if normalization is actually running
- Verify ground truth format expectations
- Review agent outputs for actual changes

### Issue: Negative improvement

**Symptoms:** After < Before accuracy

**Causes:**
1. Agents overcorrecting good data
2. Type conversion bugs
3. Validation rejecting valid values

**Solutions:**
- Review agent reasoning chains for specific documents
- Check error logs in validation report
- Add unit tests for edge cases
- Adjust agent prompts to be less aggressive

### Issue: Inconsistent improvements

**Symptoms:** Some documents improve greatly, others degrade

**Causes:**
1. Document format variations
2. Agent prompts optimized for specific format
3. Ground truth quality variations

**Solutions:**
- Segment documents by type
- Create type-specific normalization pipelines
- Improve ground truth consistency

---

## Summary

The **Normalization Impact Analyzer** provides critical insights into your normalization pipeline's effectiveness:

✅ **Quantifies improvement** from raw extraction to normalized data
✅ **Identifies valuable agents** that provide the most improvement
✅ **Detects degradation** when normalization breaks data
✅ **Justifies processing costs** with measurable quality gains
✅ **Guides optimization** by showing which fields benefit most

Use it to continuously monitor and improve your document processing pipeline!
