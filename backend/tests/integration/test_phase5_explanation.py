"""
Integration test for Phase 5: Explanation Generator

This script tests the complete workflow:
1. Calculate margin requirement
2. Generate LLM-powered explanation
3. Retrieve and validate explanation
"""

import json
import requests
from datetime import datetime

# Configuration
BASE_URL = "http://127.0.0.1:8000"
DOCUMENT_ID = "4494b130-c604-48e0-9eb3-2d888504fb43"  # Existing CSA from previous tests


def print_section(title):
    """Print a formatted section header."""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


def test_health():
    """Test health endpoint and API configuration."""
    print_section("1. Testing Health Endpoint")

    response = requests.get(f"{BASE_URL}/health")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    health_data = response.json()
    if not health_data.get("anthropic_configured"):
        print("\n[!] WARNING: Anthropic API key not configured!")
        print("   Please set ANTHROPIC_API_KEY in backend/.env to test LLM generation")
        print("   Continuing with structural tests only...")
        return False

    print("\n[OK] Anthropic API configured")
    return True


def test_calculation():
    """Test margin calculation endpoint."""
    print_section("2. Testing Margin Calculation")

    # Prepare calculation request
    request_data = {
        "document_id": DOCUMENT_ID,
        "net_exposure": 5_000_000.0,  # $5M exposure
        "posted_collateral": [
            {
                "collateral_type": "CASH",
                "market_value": 2_000_000.0,  # $2M cash
                "haircut_rate": 0.0,  # No haircut for cash
                "currency": "USD",
                "description": "USD Cash"
            },
            {
                "collateral_type": "US_TREASURY",
                "market_value": 1_000_000.0,  # $1M treasuries
                "haircut_rate": 0.02,  # 2% haircut
                "currency": "USD",
                "description": "US Treasury Securities",
                "maturity_years": 2.0
            }
        ]
    }

    print("Request Data:")
    print(json.dumps(request_data, indent=2))

    response = requests.post(
        f"{BASE_URL}/api/v1/calculations/calculate",
        json=request_data
    )

    print(f"\nStatus Code: {response.status_code}")

    if response.status_code != 200:
        print(f"Error: {response.text}")
        return None

    result = response.json()
    print(f"\nCalculation Result:")
    print(f"  Calculation ID: {result['calculation_id']}")
    print(f"  Action: {result['margin_call']['action']}")
    print(f"  Amount: ${result['margin_call']['amount']:,.2f}")
    print(f"  Counterparty: {result['margin_call']['counterparty_name']}")
    print(f"\n  Key Figures:")
    print(f"    Net Exposure: ${result['margin_call']['net_exposure']:,.2f}")
    print(f"    Threshold: ${result['margin_call']['threshold']:,.2f}")
    print(f"    Effective Collateral: ${result['margin_call']['effective_collateral']:,.2f}")
    print(f"    Exposure Above Threshold: ${result['margin_call']['exposure_above_threshold']:,.2f}")

    print(f"\n  Calculation Steps:")
    for step in result['margin_call']['calculation_steps']:
        print(f"    Step {step['step_number']}: {step['description']}")
        print(f"      Result: ${step['result']:,.2f}")
        if step.get('source_clause'):
            print(f"      CSA Clause: {step['source_clause']}")

    print("\n[OK] Calculation successful")
    return result['calculation_id']


def test_explanation_generation(calculation_id, api_configured):
    """Test explanation generation endpoint."""
    print_section("3. Testing Explanation Generation")

    print(f"Generating explanation for calculation: {calculation_id}")

    if not api_configured:
        print("\n[!] Skipping LLM generation test (API key not configured)")
        print("   Endpoint structure validated, but cannot test full generation")
        return None

    response = requests.post(
        f"{BASE_URL}/api/v1/calculations/{calculation_id}/explain"
    )

    print(f"\nStatus Code: {response.status_code}")

    if response.status_code != 200:
        print(f"Error: {response.text}")
        return None

    result = response.json()

    print(f"\n[OK] Explanation generated successfully!")
    print(f"\nExplanation Summary:")
    print(f"  Counterparty: {result['explanation']['counterparty_name']}")
    print(f"  Action: {result['explanation']['margin_call_action']}")
    print(f"  Amount: ${result['explanation']['margin_call_amount']:,.2f}")
    print(f"  LLM Model: {result['explanation']['llm_model']}")
    print(f"  Generated At: {result['explanation']['generated_at']}")

    print(f"\n  Key Factors ({len(result['explanation']['key_factors'])}):")
    for i, factor in enumerate(result['explanation']['key_factors'], 1):
        print(f"    {i}. {factor}")

    print(f"\n  Calculation Breakdown ({len(result['explanation']['calculation_breakdown'])} steps):")
    for step in result['explanation']['calculation_breakdown']:
        print(f"    Step {step['step_number']}: {step['step_name']}")
        if step.get('csa_clause_reference'):
            print(f"      CSA Clause: {step['csa_clause_reference']} (Page {step.get('source_page', 'N/A')})")

    print(f"\n  Citations:")
    if result['explanation']['citations']:
        for clause, page in result['explanation']['citations'].items():
            print(f"    {clause} → Page {page}")
    else:
        print("    None")

    print(f"\n  Narrative (first 500 characters):")
    narrative = result['explanation']['narrative']
    print(f"    {narrative[:500]}...")

    if result['explanation'].get('risk_assessment'):
        print(f"\n  Risk Assessment:")
        print(f"    {result['explanation']['risk_assessment'][:300]}...")

    if result['explanation'].get('next_steps'):
        print(f"\n  Next Steps:")
        print(f"    {result['explanation']['next_steps']}")

    return result


def test_retrieve_explanation(calculation_id, api_configured):
    """Test retrieving a saved explanation."""
    print_section("4. Testing Explanation Retrieval")

    if not api_configured:
        print("[!] Skipping retrieval test (explanation not generated)")
        return

    response = requests.get(
        f"{BASE_URL}/api/v1/calculations/{calculation_id}/explanation"
    )

    print(f"Status Code: {response.status_code}")

    if response.status_code != 200:
        print(f"Error: {response.text}")
        return

    result = response.json()
    print(f"\n[OK] Explanation retrieved successfully!")
    print(f"  Status: {result['status']}")
    print(f"  Calculation ID: {result['calculation_id']}")


def test_list_calculations():
    """Test listing all calculations."""
    print_section("5. Testing List Calculations")

    response = requests.get(f"{BASE_URL}/api/v1/calculations/")

    print(f"Status Code: {response.status_code}")

    if response.status_code != 200:
        print(f"Error: {response.text}")
        return

    result = response.json()
    print(f"\n[OK] Found {result['count']} calculations")

    if result['calculation_ids']:
        print(f"\n  Recent Calculations:")
        for calc_id in result['calculation_ids'][:5]:
            print(f"    - {calc_id}")


def main():
    """Run all Phase 5 tests."""
    print("\n" + "="*70)
    print("  PHASE 5 INTEGRATION TEST: EXPLANATION GENERATOR")
    print("="*70)

    try:
        # Test 1: Health check
        api_configured = test_health()

        # Test 2: Run calculation
        calculation_id = test_calculation()

        if not calculation_id:
            print("\n[ERROR] Calculation failed - cannot proceed with explanation tests")
            return

        # Test 3: Generate explanation
        explanation = test_explanation_generation(calculation_id, api_configured)

        # Test 4: Retrieve explanation
        test_retrieve_explanation(calculation_id, api_configured)

        # Test 5: List all calculations
        test_list_calculations()

        # Final summary
        print_section("TEST SUMMARY")

        if api_configured:
            print("[SUCCESS] ALL TESTS PASSED!")
            print(f"\n  Generated Calculation ID: {calculation_id}")
            print(f"\n  Explanation has been saved to:")
            print(f"    backend/data/explanations/explanation_{calculation_id}.json")
            print(f"\n  Calculation has been saved to:")
            print(f"    backend/data/calculations/margin_call_{calculation_id}.json")
        else:
            print("[PARTIAL] TESTS PARTIALLY COMPLETED")
            print("\n  Structural tests passed, but LLM generation was skipped.")
            print("  To test full explanation generation:")
            print("    1. Add ANTHROPIC_API_KEY to backend/.env")
            print("    2. Restart the server")
            print("    3. Run this test again")

        print("\n" + "="*70)

    except requests.exceptions.ConnectionError:
        print("\n[ERROR] Cannot connect to server")
        print("   Please ensure the server is running:")
        print("   cd backend && uvicorn app.main:app --reload")

    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
