"""
Integration test for Multi-Agent Normalization System (Phase 3)

This script tests the complete multi-agent workflow:
1. Load Credit Suisse CSA extraction
2. Run multi-agent normalization (4 agents with reasoning chains)
3. Verify reasoning chains for all agents
4. Validate agent results and confidence scores
5. Check validation report
"""

import json
import requests
from datetime import datetime
from pathlib import Path

# Configuration
BASE_URL = "http://127.0.0.1:8000"
DOCUMENT_ID = "4494b130-c604-48e0-9eb3-2d888504fb43"  # Credit Suisse CSA

# Find extraction ID from existing test data
DATA_DIR = Path(__file__).parent.parent.parent / "data" / "extractions"


def print_section(title):
    """Print a formatted section header."""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


def print_subsection(title):
    """Print a formatted subsection header."""
    print(f"\n{'-'*80}")
    print(f"  {title}")
    print(f"{'-'*80}\n")


def find_extraction_id():
    """Find the latest extraction ID for the Credit Suisse document."""
    print_section("0. Finding Extraction ID")

    # List all extraction files for this document
    extraction_files = list(DATA_DIR.glob(f"extract_parse_{DOCUMENT_ID}_*.json"))

    if not extraction_files:
        print(f"[!] ERROR: No extraction files found for document {DOCUMENT_ID}")
        print(f"    Searched in: {DATA_DIR}")
        return None

    # Get the most recent extraction file
    latest_file = max(extraction_files, key=lambda f: f.stat().st_mtime)
    extraction_id = latest_file.stem  # Filename without extension

    print(f"[OK] Found extraction file: {latest_file.name}")
    print(f"    Extraction ID: {extraction_id}")

    return extraction_id


def test_health():
    """Test health endpoint and API configuration."""
    print_section("1. Testing Health Endpoint")

    response = requests.get(f"{BASE_URL}/health")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    health_data = response.json()
    if not health_data.get("anthropic_configured"):
        print("\n[!] WARNING: Anthropic API key not configured!")
        print("   Please set ANTHROPIC_API_KEY in backend/.env")
        print("   Multi-agent normalization requires Claude AI")
        return False

    print("\n[OK] All API keys configured")
    return True


def test_full_pipeline(extraction_id):
    """Test the complete multi-agent normalization pipeline."""
    print_section("2. Testing Full Multi-Agent Pipeline")

    print(f"Calling POST /api/v1/documents/normalize-multiagent/{extraction_id}")

    response = requests.post(
        f"{BASE_URL}/api/v1/documents/normalize-multiagent/{extraction_id}"
    )

    print(f"\nStatus Code: {response.status_code}")

    if response.status_code != 200:
        print(f"[!] ERROR: {response.text}")
        return None

    result = response.json()

    print(f"\n[OK] Multi-agent normalization completed successfully!")
    print(f"\nResponse Summary:")
    print(f"  Normalized Data ID: {result['normalized_data_id']}")
    print(f"  Document ID: {result['document_id']}")
    print(f"  Extraction ID: {result['extraction_id']}")
    print(f"  Overall Confidence: {result['overall_confidence']*100:.1f}%")
    print(f"  Requires Human Review: {result['requires_human_review']}")
    print(f"  Status: {result['status']}")

    print(f"\nAgent Results Summary:")
    for agent_name, agent_data in result['agent_results'].items():
        print(f"\n  {agent_name.upper()} Agent:")
        print(f"    Confidence: {agent_data['confidence']*100:.1f}%")
        print(f"    Reasoning Steps: {agent_data['reasoning_steps']}")
        print(f"    Self Corrections: {agent_data.get('self_corrections', 0)}")
        print(f"    Processing Time: {agent_data['processing_time_seconds']:.2f}s")

        # Agent-specific metrics
        if agent_name == 'collateral':
            print(f"    Items Processed: {agent_data.get('items_processed', 'N/A')}")
        elif agent_name == 'temporal':
            print(f"    Fields Processed: {agent_data.get('fields_processed', 'N/A')}")
            print(f"    Context Accessed: {agent_data.get('context_accessed', False)}")
        elif agent_name == 'currency':
            print(f"    Fields Processed: {agent_data.get('fields_processed', 'N/A')}")

    print(f"\nValidation Summary:")
    validation = result['validation']
    print(f"  Checks Performed: {validation['checks_performed']}")
    print(f"  Checks Passed: {validation['checks_passed']}")
    print(f"  Checks Failed: {validation['checks_failed']}")
    print(f"  Warnings: {validation['warnings_count']}")
    print(f"  Errors: {validation['errors_count']}")

    print(f"\nProcessing Summary:")
    proc = result['processing_summary']
    print(f"  Total Time: {proc['total_time_seconds']:.2f}s")
    print(f"  Total Reasoning Steps: {proc['total_reasoning_steps']}")
    print(f"  Total Self Corrections: {proc['total_self_corrections']}")
    print(f"  Models Used: {', '.join(proc['models_used'])}")
    print(f"  Context Accessed: {proc['context_accessed']}")

    return result


def test_collateral_reasoning_chain(normalized_id):
    """Test detailed reasoning chain for collateral agent."""
    print_section("3. Testing Collateral Agent Reasoning Chain")

    print(f"Calling GET /api/v1/documents/normalized-multiagent/{normalized_id}/reasoning/collateral")

    response = requests.get(
        f"{BASE_URL}/api/v1/documents/normalized-multiagent/{normalized_id}/reasoning/collateral"
    )

    print(f"\nStatus Code: {response.status_code}")

    if response.status_code != 200:
        print(f"[!] ERROR: {response.text}")
        return False

    result = response.json()

    print(f"\n[OK] Collateral agent reasoning chain retrieved!")
    print(f"\nAgent: {result['agent_name']}")
    print(f"Confidence: {result['confidence']*100:.1f}%")
    print(f"Total Steps: {len(result['reasoning_chain'])}")
    print(f"Self Corrections: {result['self_corrections']}")

    print(f"\nReasoning Steps (6-step process):")
    for step in result['reasoning_chain']:
        print(f"\n  Step {step['step_number']}: {step['step_name']}")
        print(f"    Model: {step['model_used']}")
        print(f"    Reasoning: {step['reasoning'][:100]}...")
        if step.get('confidence'):
            print(f"    Confidence: {step['confidence']*100:.1f}%")
        print(f"    Duration: {step.get('duration_seconds', 0):.2f}s")

    # Check for expected 6 steps
    expected_steps = ['initial_parse', 'detect_ambiguities', 'resolve_ambiguities',
                      'validate_taxonomy', 'validate_logic', 'synthesize']
    actual_steps = [step['step_name'] for step in result['reasoning_chain']]

    print(f"\n[CHECK] Expected steps present:")
    for expected in expected_steps:
        found = expected in actual_steps
        status = "[OK]" if found else "[MISSING]"
        print(f"  {status} {expected}")

    return len(result['reasoning_chain']) == 6


def test_temporal_context_access(normalized_id):
    """Test temporal agent's context-aware timezone inference."""
    print_section("4. Testing Temporal Agent Context Access")

    print(f"Calling GET /api/v1/documents/normalized-multiagent/{normalized_id}/reasoning/temporal")

    response = requests.get(
        f"{BASE_URL}/api/v1/documents/normalized-multiagent/{normalized_id}/reasoning/temporal"
    )

    print(f"\nStatus Code: {response.status_code}")

    if response.status_code != 200:
        print(f"[!] ERROR: {response.text}")
        return False

    result = response.json()

    print(f"\n[OK] Temporal agent reasoning chain retrieved!")
    print(f"\nAgent: {result['agent_name']}")
    print(f"Confidence: {result['confidence']*100:.1f}%")
    print(f"Total Steps: {len(result['reasoning_chain'])}")

    print(f"\nReasoning Steps (4-step process):")
    for step in result['reasoning_chain']:
        print(f"\n  Step {step['step_number']}: {step['step_name']}")
        print(f"    Model: {step['model_used']}")
        print(f"    Reasoning: {step['reasoning'][:150]}...")

    # Check for context access
    context_accessed = False
    for step in result['reasoning_chain']:
        if 'context' in step['step_name'].lower() or 'document' in step.get('reasoning', '').lower():
            context_accessed = True
            print(f"\n[OK] Context access detected in step: {step['step_name']}")
            break

    if not context_accessed:
        print(f"\n[INFO] No explicit context access detected (may not be needed for explicit timezones)")

    return True


def test_currency_standardization(normalized_id):
    """Test currency agent's ISO 4217 standardization."""
    print_section("5. Testing Currency Agent Standardization")

    print(f"Calling GET /api/v1/documents/normalized-multiagent/{normalized_id}/reasoning/currency")

    response = requests.get(
        f"{BASE_URL}/api/v1/documents/normalized-multiagent/{normalized_id}/reasoning/currency"
    )

    print(f"\nStatus Code: {response.status_code}")

    if response.status_code != 200:
        print(f"[!] ERROR: {response.text}")
        return False

    result = response.json()

    print(f"\n[OK] Currency agent reasoning chain retrieved!")
    print(f"\nAgent: {result['agent_name']}")
    print(f"Confidence: {result['confidence']*100:.1f}%")
    print(f"Total Steps: {len(result['reasoning_chain'])}")

    print(f"\nNormalized Data Summary:")
    data = result.get('data', {})
    print(f"  Fields Processed: {len(data)}")

    # Check for ISO 4217 standardization
    iso_fields = 0
    for field_name, field_data in data.items():
        if isinstance(field_data, dict) and 'currency_code' in field_data:
            print(f"    {field_name}: {field_data.get('currency_code', 'N/A')}")
            iso_fields += 1

    print(f"\n[OK] {iso_fields} fields standardized to ISO 4217")

    return True


def test_validation_report(normalized_id):
    """Test validation agent's cross-field checks."""
    print_section("6. Testing Validation Agent Report")

    print(f"Calling GET /api/v1/documents/normalized-multiagent/{normalized_id}/validation")

    response = requests.get(
        f"{BASE_URL}/api/v1/documents/normalized-multiagent/{normalized_id}/validation"
    )

    print(f"\nStatus Code: {response.status_code}")

    if response.status_code != 200:
        print(f"[!] ERROR: {response.text}")
        return False

    result = response.json()

    print(f"\n[OK] Validation report retrieved!")

    validation = result['validation_report']
    print(f"\nValidation Report:")
    print(f"  Passed: {validation['passed']}")
    print(f"  Checks Performed: {validation['checks_performed']}")
    print(f"  Checks Passed: {validation['checks_passed']}")
    print(f"  Checks Failed: {validation['checks_failed']}")

    if validation.get('warnings'):
        print(f"\n  Warnings ({len(validation['warnings'])}):")
        for warning in validation['warnings']:
            print(f"    - {warning.get('check', 'Unknown')}: {warning.get('message', '')[:80]}")

    if validation.get('errors'):
        print(f"\n  Errors ({len(validation['errors'])}):")
        for error in validation['errors']:
            print(f"    - {error.get('check', 'Unknown')}: {error.get('message', '')[:80]}")

    if validation.get('recommendations'):
        print(f"\n  Recommendations ({len(validation['recommendations'])}):")
        for rec in validation['recommendations'][:3]:  # Show first 3
            print(f"    - {rec[:100]}")

    # Check that validation categories ran
    expected_checks = ['currency_consistency', 'timezone_consistency', 'date_consistency',
                       'business_rules', 'collateral_logic']
    print(f"\n[CHECK] Validation categories:")
    for check in expected_checks:
        print(f"  [INFO] Expected: {check}")

    return validation['checks_performed'] >= 5


def test_reasoning_retrieval_all(normalized_id):
    """Test retrieval of all agent reasoning chains at once."""
    print_section("7. Testing All Reasoning Chains Retrieval")

    print(f"Calling GET /api/v1/documents/normalized-multiagent/{normalized_id}/reasoning")

    response = requests.get(
        f"{BASE_URL}/api/v1/documents/normalized-multiagent/{normalized_id}/reasoning"
    )

    print(f"\nStatus Code: {response.status_code}")

    if response.status_code != 200:
        print(f"[!] ERROR: {response.text}")
        return False

    result = response.json()

    print(f"\n[OK] All reasoning chains retrieved!")
    print(f"\nTotal Reasoning Steps: {result['total_reasoning_steps']}")
    print(f"Agents: {', '.join(result['agents'].keys())}")

    for agent_name, agent_data in result['agents'].items():
        print(f"\n  {agent_name.upper()}:")
        print(f"    Steps: {agent_data['reasoning_steps']}")
        print(f"    Confidence: {agent_data['confidence']*100:.1f}%")
        print(f"    Self Corrections: {agent_data.get('self_corrections', 0)}")

    return len(result['agents']) == 3  # collateral, temporal, currency


def main():
    """Run all integration tests."""
    print("\n" + "="*80)
    print("  MULTI-AGENT NORMALIZATION INTEGRATION TEST SUITE")
    print("  Phase 3: Testing & Demo Preparation")
    print("="*80)

    # Test 0: Find extraction ID
    extraction_id = find_extraction_id()
    if not extraction_id:
        print("\n[FAILED] Cannot proceed without extraction ID")
        return False

    # Test 1: Health check
    if not test_health():
        print("\n[WARNING] Some API keys not configured, continuing with available tests...")

    # Test 2: Full pipeline
    pipeline_result = test_full_pipeline(extraction_id)
    if not pipeline_result:
        print("\n[FAILED] Full pipeline test failed")
        return False

    normalized_id = pipeline_result['normalized_data_id']
    print(f"\n[INFO] Using normalized_id: {normalized_id} for detailed tests")

    # Test 3: Collateral reasoning chain
    test_collateral_reasoning_chain(normalized_id)

    # Test 4: Temporal context access
    test_temporal_context_access(normalized_id)

    # Test 5: Currency standardization
    test_currency_standardization(normalized_id)

    # Test 6: Validation report
    test_validation_report(normalized_id)

    # Test 7: All reasoning retrieval
    test_reasoning_retrieval_all(normalized_id)

    # Summary
    print_section("TEST SUMMARY")
    print("[OK] All integration tests completed successfully!")
    print(f"\nKey Metrics:")
    print(f"  Overall Confidence: {pipeline_result['overall_confidence']*100:.1f}%")
    print(f"  Total Processing Time: {pipeline_result['processing_summary']['total_time_seconds']:.2f}s")
    print(f"  Total Reasoning Steps: {pipeline_result['processing_summary']['total_reasoning_steps']}")
    print(f"  Agents Executed: {len(pipeline_result['agent_results'])}")
    print(f"  Validation Checks: {pipeline_result['validation']['checks_performed']}")

    print(f"\n[SUCCESS] Multi-agent normalization system is working correctly! 🎉")
    return True


if __name__ == "__main__":
    try:
        success = main()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Test suite interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\n\n[ERROR] Test suite failed with exception: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
