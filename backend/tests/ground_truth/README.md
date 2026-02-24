# Ground Truth Dataset

This directory contains manually labeled CSA documents used to measure the accuracy of the extraction and normalization pipeline.

## Directory Structure

```
ground_truth/
├── documents/               # Source PDF documents
│   ├── csa_001.pdf
│   └── ...
├── expected_extractions/    # Expected extraction results
│   ├── csa_001_extraction.json
│   └── ...
├── expected_normalized/     # Expected normalization results
│   ├── csa_001_normalized.json
│   └── ...
└── README.md               # This file
```

## Creating Ground Truth Data

### Step 1: Add Source Document
Place the CSA PDF in `documents/` with a unique identifier (e.g., `csa_001.pdf`).

### Step 2: Create Expected Extraction
Manually review the PDF and create `expected_extractions/csa_001_extraction.json` with the expected field values that should be extracted by LandingAI ADE.

**Template:**
```json
{
  "document_id": "csa_001",
  "source_file": "csa_001.pdf",
  "expected_fields": {
    "agreement_info": {
      "agreement_title": "Credit Support Annex",
      "agreement_date": "2008-03-28",
      "party_a": "Credit Suisse International",
      "party_b": "Fifth Third Auto Trust 2008-1"
    },
    "core_margin_terms": {
      "party_a_threshold": "$2,000,000",
      "party_b_threshold": "Infinity",
      "party_a_mta": "$100,000",
      "party_b_mta": "Not Applicable",
      "rounding": "$10,000",
      "base_currency": "US Dollars"
    },
    "eligible_collateral_table": [
      {
        "collateral_type": "Cash in US Dollars",
        "valuation_percentages": ["100%"]
      }
    ]
  }
}
```

### Step 3: Create Expected Normalization
Create `expected_normalized/csa_001_normalized.json` with the expected normalized values after agent processing.

**Template:**
```json
{
  "document_id": "csa_001",
  "expected_normalized_collateral": [
    {
      "standardized_type": "CASH_USD",
      "maturity_buckets": [
        {
          "min_maturity_years": null,
          "max_maturity_years": null,
          "valuation_percentage": 100.0,
          "haircut_percentage": 0.0
        }
      ],
      "confidence": 1.0
    }
  ],
  "expected_temporal": {
    "notification_time": {
      "time": "13:00:00",
      "timezone": "America/New_York",
      "confidence": 0.95
    }
  },
  "expected_currency": {
    "base_currency": {
      "currency_code": "USD",
      "confidence": 1.0
    },
    "threshold_party_a": {
      "amount": 2000000.0,
      "currency_code": "USD"
    }
  }
}
```

## Using Ground Truth for Accuracy Testing

Ground truth data is used by:
1. **AccuracyValidator** - Compares actual extraction/normalization against expected values
2. **Benchmark Tests** - Automated tests that assert minimum accuracy thresholds
3. **Analytics Dashboard** - Displays aggregate accuracy metrics across all ground truth documents

## Accuracy Metrics

For each ground truth document, we calculate:

### Extraction Accuracy
- **Field-level Precision**: Correctly extracted fields / Total extracted fields
- **Field-level Recall**: Correctly extracted fields / Total expected fields
- **F1 Score**: Harmonic mean of precision and recall

### Normalization Accuracy
- **Type Classification Accuracy**: Correctly classified collateral types / Total items
- **Maturity Bucket Accuracy**: Correctly parsed maturity ranges / Total buckets
- **Currency Standardization Accuracy**: Correctly standardized currencies / Total currency fields

### Overall Accuracy
- **End-to-End Accuracy**: Documents with 100% correct final CSATerms / Total documents
- **Error Rate**: Documents with any errors / Total documents

## Best Practices

1. **Quality over Quantity**: Start with 10-20 high-quality labeled documents
2. **Diversity**: Include documents with various formats, collateral types, and edge cases
3. **Double-Check**: Have multiple reviewers verify ground truth labels
4. **Version Control**: Commit ground truth files to git for reproducibility
5. **Update Regularly**: Add new ground truth cases when errors are discovered
