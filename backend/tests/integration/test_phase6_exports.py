"""
Integration tests for Phase 6 export endpoints.

Tests the following functionality:
- Document detail endpoint (processing status)
- Margin call notice export (JSON and PDF formats)
- Audit trail export (JSON and CSV formats)

These tests require:
- FastAPI server running on http://127.0.0.1:8000
  Start with: cd backend && uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
- Existing calculation data from Phase 5 tests
  The test uses: calc_4494b130-c604-48e0-9eb3-2d888504fb43_20251106_192151
"""

import pytest
import httpx
from pathlib import Path

# Test configuration
BASE_URL = "http://127.0.0.1:8000/api/v1"
TIMEOUT = 30.0

# Test data - uses existing calculation from Phase 5 tests
CALCULATION_ID = "calc_4494b130-c604-48e0-9eb3-2d888504fb43_20251106_192151"
DOCUMENT_ID = "4494b130-c604-48e0-9eb3-2d888504fb43"


@pytest.mark.integration
def test_document_detail_endpoint():
    """
    Test GET /api/v1/documents/{document_id}/detail endpoint.

    Verifies that the endpoint returns comprehensive document information including:
    - File metadata (name, size, upload timestamp)
    - Processing status flags for all 6 pipeline stages
    - Related artifact IDs
    """
    url = f"{BASE_URL}/documents/{DOCUMENT_ID}/detail"

    response = httpx.get(url, timeout=TIMEOUT)

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    data = response.json()

    # Verify response structure
    assert "document_id" in data
    assert "filename" in data
    assert "file_size" in data
    assert "uploaded_at" in data
    assert "processing_status" in data
    assert "artifact_ids" in data

    # Verify processing status structure
    status = data["processing_status"]
    assert "uploaded" in status
    assert "parsed" in status
    assert "extracted" in status
    assert "normalized" in status
    assert "mapped_to_csa_terms" in status
    assert "has_calculations" in status

    # Document should be uploaded
    assert status["uploaded"] is True

    # Verify artifact IDs structure
    artifacts = data["artifact_ids"]
    assert "parse_id" in artifacts
    assert "extraction_id" in artifacts
    assert "calculation_ids" in artifacts


@pytest.mark.integration
def test_margin_call_notice_json_export():
    """
    Test GET /api/v1/export/margin-call-notice/{calculation_id}?format=json endpoint.

    Verifies that the endpoint returns a structured margin call notice with:
    - Counterparty information
    - Exposure and collateral summary
    - Margin call action and amount
    - Calculation breakdown
    """
    url = f"{BASE_URL}/export/margin-call-notice/{CALCULATION_ID}?format=json"

    response = httpx.get(url, timeout=TIMEOUT)

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    data = response.json()

    # Verify margin call notice structure
    assert "calculation_id" in data
    assert "document_id" in data
    assert "generated_at" in data
    assert "party_a" in data
    assert "party_b" in data
    assert "current_exposure" in data
    assert "threshold" in data
    assert "posted_collateral_value" in data
    assert "margin_call_action" in data
    assert "margin_call_amount" in data
    assert "delivery_amount" in data
    assert "valuation_date" in data
    assert "calculation_breakdown" in data
    assert "legal_disclaimer" in data

    # Verify data types
    assert isinstance(data["current_exposure"], (int, float))
    assert isinstance(data["margin_call_amount"], (int, float))
    assert data["margin_call_action"] in ["CALL", "RETURN", "NO_ACTION"]
    assert isinstance(data["calculation_breakdown"], list)


@pytest.mark.integration
def test_margin_call_notice_pdf_export():
    """
    Test GET /api/v1/export/margin-call-notice/{calculation_id}?format=pdf endpoint.

    Verifies that the endpoint:
    - Returns a valid PDF file
    - PDF has correct magic bytes signature
    - PDF is downloadable with proper headers
    """
    url = f"{BASE_URL}/export/margin-call-notice/{CALCULATION_ID}?format=pdf"

    response = httpx.get(url, timeout=TIMEOUT)

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    # Verify content type
    assert "application/pdf" in response.headers.get("content-type", "")

    # Verify PDF signature (magic bytes)
    assert response.content[:4] == b'%PDF', "Invalid PDF signature"

    # Verify file size is reasonable (not empty, not too large)
    assert len(response.content) > 1000, "PDF file too small"
    assert len(response.content) < 10 * 1024 * 1024, "PDF file too large (>10MB)"

    # Verify Content-Disposition header for download
    assert "attachment" in response.headers.get("content-disposition", "")
    assert "margin_call_notice" in response.headers.get("content-disposition", "")

    # Optional: Save PDF for manual inspection (in test output directory)
    # pdf_path = Path(__file__).parent.parent.parent / "test_output" / "test_margin_call_notice.pdf"
    # pdf_path.parent.mkdir(exist_ok=True)
    # pdf_path.write_bytes(response.content)


@pytest.mark.integration
def test_audit_trail_json_export():
    """
    Test GET /api/v1/export/audit-trail/{calculation_id}?format=json endpoint.

    Verifies that the endpoint returns a complete audit trail with:
    - Calculation ID
    - Event count
    - Chronological event list with timestamps
    """
    url = f"{BASE_URL}/export/audit-trail/{CALCULATION_ID}?format=json"

    response = httpx.get(url, timeout=TIMEOUT)

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    data = response.json()

    # Verify audit trail structure
    assert "calculation_id" in data
    assert "generated_at" in data
    assert "event_count" in data
    assert "audit_trail" in data

    # Verify calculation ID matches
    assert data["calculation_id"] == CALCULATION_ID

    # Verify audit trail events
    audit_trail = data["audit_trail"]
    assert isinstance(audit_trail, list)
    assert len(audit_trail) > 0, "Audit trail should not be empty"
    assert data["event_count"] == len(audit_trail)

    # Verify event structure
    for event in audit_trail:
        assert "timestamp" in event
        assert "event" in event
        assert "details" in event
        assert isinstance(event["timestamp"], str)
        assert isinstance(event["event"], str)
        assert isinstance(event["details"], str)


@pytest.mark.integration
def test_audit_trail_csv_export():
    """
    Test GET /api/v1/export/audit-trail/{calculation_id}?format=csv endpoint.

    Verifies that the endpoint:
    - Returns a valid CSV file
    - CSV has proper headers
    - CSV is downloadable with proper headers
    """
    url = f"{BASE_URL}/export/audit-trail/{CALCULATION_ID}?format=csv"

    response = httpx.get(url, timeout=TIMEOUT)

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    # Verify content type
    assert "text/csv" in response.headers.get("content-type", "")

    # Verify Content-Disposition header for download
    assert "attachment" in response.headers.get("content-disposition", "")
    assert "audit_trail" in response.headers.get("content-disposition", "")

    # Decode and verify CSV content
    csv_content = response.content.decode('utf-8')
    lines = csv_content.strip().split('\n')

    # Verify CSV has content
    assert len(lines) > 1, "CSV should have headers and at least one data row"

    # Verify CSV headers
    headers = lines[0]
    assert "timestamp" in headers
    assert "event" in headers
    assert "details" in headers

    # Verify data rows exist
    assert len(lines) > 1, "CSV should have at least one event"

    # Optional: Verify data row format (should have 3 columns)
    # for line in lines[1:]:
    #     columns = line.split(',')
    #     assert len(columns) >= 3, f"CSV row should have at least 3 columns: {line}"


@pytest.mark.integration
def test_export_with_invalid_calculation_id():
    """
    Test export endpoints with invalid calculation ID.

    Verifies that endpoints return 404 for non-existent calculations.
    """
    invalid_id = "calc_nonexistent_12345"

    # Test margin call notice endpoint
    url = f"{BASE_URL}/export/margin-call-notice/{invalid_id}?format=json"
    response = httpx.get(url, timeout=TIMEOUT)
    assert response.status_code == 404, f"Expected 404 for invalid ID, got {response.status_code}"

    # Test audit trail endpoint
    url = f"{BASE_URL}/export/audit-trail/{invalid_id}?format=json"
    response = httpx.get(url, timeout=TIMEOUT)
    assert response.status_code == 404, f"Expected 404 for invalid ID, got {response.status_code}"


@pytest.mark.integration
def test_export_format_validation():
    """
    Test that export endpoints validate format parameter.

    Valid formats:
    - margin-call-notice: json, pdf
    - audit-trail: json, csv
    """
    # Valid formats should work
    url = f"{BASE_URL}/export/margin-call-notice/{CALCULATION_ID}?format=json"
    response = httpx.get(url, timeout=TIMEOUT)
    assert response.status_code == 200

    url = f"{BASE_URL}/export/margin-call-notice/{CALCULATION_ID}?format=pdf"
    response = httpx.get(url, timeout=TIMEOUT)
    assert response.status_code == 200

    url = f"{BASE_URL}/export/audit-trail/{CALCULATION_ID}?format=json"
    response = httpx.get(url, timeout=TIMEOUT)
    assert response.status_code == 200

    url = f"{BASE_URL}/export/audit-trail/{CALCULATION_ID}?format=csv"
    response = httpx.get(url, timeout=TIMEOUT)
    assert response.status_code == 200

    # Invalid format should return 422 (validation error)
    url = f"{BASE_URL}/export/margin-call-notice/{CALCULATION_ID}?format=invalid"
    response = httpx.get(url, timeout=TIMEOUT)
    assert response.status_code == 422, f"Expected 422 for invalid format, got {response.status_code}"
