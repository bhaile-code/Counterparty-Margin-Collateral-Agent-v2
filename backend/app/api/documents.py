"""API endpoints for document upload, parsing, and extraction."""

import os
import shutil
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, File, UploadFile, HTTPException, Query, BackgroundTasks, Body

from app.config import settings
from app.main import JSONResponse  # Custom JSONResponse with InfinityEncoder
from app.services.ade_service import ade_service
from app.services.collateral_normalizer import collateral_normalizer_service
from app.services.normalization_orchestrator import NormalizationOrchestrator
from app.services.ade_mapper import ade_mapper
from app.services.table_builder import TableBuilder
from app.services.job_manager import get_job_manager
from app.services.pipeline_orchestrator import get_pipeline_orchestrator, ProcessOptions
from app.utils.file_storage import FileStorage
from app.models.schemas import (
    DocumentUploadResponse,
    DocumentParseResponse,
    DocumentExtractionResponse,
    DocumentDetailResponse,
    ProcessingStatus,
    ArtifactIds,
    CSATerms,
)

router = APIRouter()


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...)):
    """
    Upload a CSA PDF document.

    The document is saved to the data/pdfs directory for processing.
    """
    # Validate file extension
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    # Read file content for validation
    file_content = await file.read()
    file_size = len(file_content)

    # Validate file size
    if file_size > settings.max_upload_size:
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds maximum allowed size of {settings.max_upload_size // (1024*1024)} MB",
        )

    # Validate PDF file signature (magic bytes)
    # PDF files start with %PDF- (hex: 25 50 44 46 2D)
    if not file_content.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="Invalid PDF file format")

    # Generate unique document ID
    document_id = str(uuid.uuid4())
    file_extension = os.path.splitext(file.filename)[1]
    saved_filename = f"{document_id}{file_extension}"
    file_path = os.path.join(settings.pdf_dir, saved_filename)

    try:
        # Save uploaded file
        with open(file_path, "wb") as buffer:
            buffer.write(file_content)

        return DocumentUploadResponse(
            document_id=document_id,
            filename=file.filename,
            file_size=file_size,
            upload_timestamp=datetime.utcnow(),
            status="uploaded",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")
    finally:
        file.file.close()


@router.post("/parse/{document_id}", response_model=DocumentParseResponse)
async def parse_document(
    document_id: str,
    save_parsed: bool = Query(True, description="Save parsed result to disk"),
):
    """
    Parse a previously uploaded document using LandingAI ADE (Step 1).

    The parsed document is saved to data/parsed for later extraction.
    """
    # Find the document file
    pdf_files = [f for f in os.listdir(settings.pdf_dir) if f.startswith(document_id)]

    if not pdf_files:
        raise HTTPException(
            status_code=404, detail=f"Document not found: {document_id}"
        )

    pdf_path = os.path.join(settings.pdf_dir, pdf_files[0])

    # Parse the document
    result = ade_service.parse_document(
        pdf_path=pdf_path, document_id=document_id, save_parsed=save_parsed
    )

    if result["status"] == "error":
        raise HTTPException(
            status_code=500, detail=f"Failed to parse document: {result.get('error')}"
        )

    return DocumentParseResponse(
        document_id=document_id,
        parse_id=result["parse_id"],
        status="parsed",
        page_count=result.get("page_count"),
        parsed_at=datetime.utcnow(),
    )


@router.post("/extract/{parse_id}")
async def extract_fields(
    parse_id: str,
    save_extraction: bool = Query(True, description="Save extraction result to disk"),
):
    """
    Extract CSA terms from a parsed document using LandingAI ADE (Step 2).

    The extraction result is saved to data/extractions for later use.
    """
    # Extract fields from parsed document
    result = ade_service.extract_fields(
        parse_id=parse_id,
        field_schema=None,  # Use default schema
        save_extraction=save_extraction,
    )

    if result["status"] == "error":
        raise HTTPException(
            status_code=500, detail=f"Failed to extract fields: {result.get('error')}"
        )

    return {
        "extraction_id": result["extraction_id"],
        "status": "extracted",
        "extracted_fields": result["extracted_fields"],
        "confidence_scores": result["confidence_scores"],
        "provenance": result["provenance"],
        "extracted_at": datetime.utcnow().isoformat(),
    }


@router.get("/extractions/{extraction_id}")
async def get_extraction(extraction_id: str):
    """
    Retrieve a previously saved extraction result.

    This allows testing with saved extractions without re-running ADE.
    """
    extraction_data = ade_service.load_saved_extraction(extraction_id)

    if not extraction_data:
        raise HTTPException(
            status_code=404, detail=f"Extraction not found: {extraction_id}"
        )

    return extraction_data


@router.post("/normalize/{extraction_id}")
async def normalize_collateral(
    extraction_id: str,
    save_normalized: bool = Query(True, description="Save normalized result to disk"),
):
    """
    Normalize collateral table from an extraction using AI.

    This endpoint uses Claude API to parse complex maturity buckets and
    standardize collateral types from the ADE extraction output.
    """
    # Load the extraction
    extraction_data = ade_service.load_saved_extraction(extraction_id)

    if not extraction_data:
        raise HTTPException(
            status_code=404, detail=f"Extraction not found: {extraction_id}"
        )

    # Get document_id from extraction
    document_id = extraction_data.get("document_id")
    if not document_id:
        raise HTTPException(status_code=400, detail="Extraction is missing document_id")

    try:
        # Normalize the collateral table
        normalized_table = collateral_normalizer_service.normalize_collateral_table(
            ade_extraction=extraction_data,
            document_id=document_id,
            extraction_id=extraction_id,
        )

        # Save to disk if requested
        if save_normalized:
            file_path = FileStorage.save_normalized_collateral(
                normalized_table, settings.normalized_collateral_dir
            )

        return {
            "document_id": document_id,
            "extraction_id": extraction_id,
            "status": "normalized",
            "rating_events": normalized_table.rating_events,
            "collateral_items_count": len(normalized_table.collateral_items),
            "collateral_types": [
                item.standardized_type.value
                for item in normalized_table.collateral_items
            ],
            "normalized_at": normalized_table.normalized_at.isoformat(),
            "normalization_model": normalized_table.normalization_model,
            "metadata": normalized_table.normalization_metadata,
        }

    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid extraction data: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to normalize collateral: {str(e)}"
        )


@router.get("/normalized/{document_id}")
async def get_normalized_collateral(document_id: str):
    """
    Retrieve a previously saved normalized collateral table.

    This allows using normalized data without re-running the AI normalization.
    """
    normalized_table = FileStorage.load_normalized_collateral(
        document_id, settings.normalized_collateral_dir
    )

    if not normalized_table:
        raise HTTPException(
            status_code=404,
            detail=f"Normalized collateral not found for document: {document_id}",
        )

    # Return as dict
    return normalized_table.model_dump(mode="json")


@router.post("/normalize-multiagent/{extraction_id}")
async def normalize_with_multiagent(
    extraction_id: str,
    save_results: bool = Query(True, description="Save normalized result to disk"),
):
    """
    Normalize extraction using multi-agent system with specialized agents.

    Uses 4 specialized agents:
    - CollateralNormalizerAgent: 6-step reasoning for collateral table
    - TemporalNormalizerAgent: Context-aware time/date normalization
    - CurrencyNormalizerAgent: Currency and amount standardization
    - ValidationAgent: Cross-field consistency validation

    Returns detailed results including reasoning chains from each agent.
    """
    # Load extraction
    extraction_data = ade_service.load_saved_extraction(extraction_id)

    if not extraction_data:
        raise HTTPException(
            status_code=404, detail=f"Extraction not found: {extraction_id}"
        )

    # Get document_id and parse_id
    document_id = extraction_data.get("document_id")
    if not document_id:
        raise HTTPException(status_code=400, detail="Extraction is missing document_id")

    parse_id = extraction_data.get("parse_id")
    if not parse_id:
        raise HTTPException(status_code=400, detail="Extraction is missing parse_id")

    # Load parsed document for context access
    parsed_document = ade_service.load_saved_parse(parse_id)

    if not parsed_document:
        raise HTTPException(
            status_code=404,
            detail=f"Parsed document not found for context access: {parse_id}"
        )

    try:
        # Initialize orchestrator
        orchestrator = NormalizationOrchestrator(api_key=settings.anthropic_api_key)

        # Run multi-agent normalization
        result = await orchestrator.normalize_extraction(
            extraction=extraction_data,
            parsed_document=parsed_document
        )

        # Save if requested
        if save_results:
            # Save the complete result
            result_dict = result.model_dump(mode="json")
            normalized_dir = os.path.join(
                settings.data_dir,
                "normalized_multiagent"
            )
            os.makedirs(normalized_dir, exist_ok=True)

            result_path = os.path.join(
                normalized_dir,
                f"{result.normalized_data_id}.json"
            )

            import json
            with open(result_path, "w") as f:
                json.dump(result_dict, f, indent=2)

        # Build response summary
        agent_summaries = {}
        for agent_name, agent_result in result.agent_results.items():
            agent_summaries[agent_name] = {
                "confidence": agent_result.confidence,
                "reasoning_steps": len(agent_result.reasoning_chain),
                "self_corrections": agent_result.self_corrections,
                "requires_review": agent_result.requires_human_review,
                "processing_time_seconds": agent_result.processing_time_seconds
            }

        # Build table view for collateral if present
        table_view = None
        collateral_metadata = None
        if "collateral" in result.agent_results:
            # Extract column info from extraction data
            extracted_fields = extraction_data.get("extracted_fields", {})
            column_info = extracted_fields.get("column_info", {})
            column_count = column_info.get("valuation_column_count", 1)
            column_names = column_info.get("valuation_column_names", [])

            rating_events = column_names if column_count > 1 else ["Base Valuation Percentage"]
            is_multi_column = column_count > 1

            # Extract normalized items
            collateral_result = result.agent_results["collateral"]
            normalized_items = collateral_result.data.get("normalized_items", [])

            # Build table view
            table_view = TableBuilder.build_table_view(
                normalized_items=normalized_items,
                rating_events=rating_events,
                is_multi_column=is_multi_column
            )

            # Build metadata
            collateral_metadata = {
                "rating_events": rating_events,
                "rating_event_count": column_count,
                "is_multi_column": is_multi_column,
                "total_items": len(normalized_items),
                "total_collateral_types": len(set(
                    item.get("standardized_type") for item in normalized_items
                ))
            }

        response = {
            "normalized_data_id": result.normalized_data_id,
            "document_id": document_id,
            "extraction_id": extraction_id,
            "status": "normalized",
            "overall_confidence": result.overall_confidence,
            "requires_human_review": result.requires_human_review,
            "agent_results": agent_summaries,
            "validation": {
                "passed": result.validation_report.passed,
                "checks_performed": result.validation_report.checks_performed,
                "checks_passed": result.validation_report.checks_passed,
                "checks_failed": result.validation_report.checks_failed,
                "warnings_count": len(result.validation_report.warnings),
                "errors_count": len(result.validation_report.errors)
            },
            "processing_summary": {
                "total_time_seconds": result.processing_summary.total_processing_time_seconds,
                "agents_used": result.processing_summary.agents_used,
                "total_reasoning_steps": result.processing_summary.total_reasoning_steps,
                "total_self_corrections": result.processing_summary.total_self_corrections,
                "models_used": result.processing_summary.models_used,
                "context_accessed": result.processing_summary.context_accessed
            },
            "created_at": result.created_at,
            "links": {
                "reasoning_chains": f"/api/v1/documents/normalized-multiagent/{result.normalized_data_id}/reasoning",
                "validation_report": f"/api/v1/documents/normalized-multiagent/{result.normalized_data_id}/validation"
            }
        }

        # Add collateral table view if available
        if table_view is not None:
            response["collateral_table"] = {
                "metadata": collateral_metadata,
                "table_view": table_view
            }

        return response

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Multi-agent normalization failed: {str(e)}"
        )


@router.post("/map/{document_id}")
async def map_to_csa_terms_endpoint(
    document_id: str,
    save_csa_terms: bool = Query(True, description="Save CSATerms to disk"),
):
    """
    Map extraction and normalized collateral to CSATerms.

    IMPORTANT: This endpoint requires that normalization has been completed first.
    It will fail if normalized collateral doesn't exist for the document.

    Workflow:
    1. Load extraction for document_id
    2. Load normalized collateral for document_id (REQUIRED)
    3. Map to CSATerms using ADEMapper
    4. Save CSATerms (optional)
    5. Return CSATerms summary

    Args:
        document_id: Document identifier
        save_csa_terms: Whether to save CSATerms to disk (default: True)

    Returns:
        CSATerms summary with collateral information

    Raises:
        HTTP 400: If normalized collateral doesn't exist (normalization required)
        HTTP 404: If extraction not found
        HTTP 500: If mapping fails
    """
    # Find extraction for this document
    extraction_files = FileStorage.list_files(settings.extractions_dir)
    extraction_id = None
    for filename in extraction_files:
        if filename.startswith(f"extract_") and document_id in filename:
            extraction_id = filename
            break

    if not extraction_id:
        raise HTTPException(
            status_code=404, detail=f"No extraction found for document: {document_id}"
        )

    # Load extraction
    extraction_data = ade_service.load_saved_extraction(extraction_id)
    if not extraction_data:
        raise HTTPException(
            status_code=404, detail=f"Extraction data not found: {extraction_id}"
        )

    # Load normalized collateral from multi-agent (REQUIRED)
    multiagent_result = FileStorage.load_normalized_collateral_multiagent(
        document_id, settings.normalized_multiagent_dir
    )

    if not multiagent_result:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Multi-agent normalized collateral not found for document: {document_id}. "
                f"Normalization is REQUIRED before mapping. "
                f"Please run: POST /api/v1/documents/normalize-multiagent/{extraction_id}"
            ),
        )

    # Convert multi-agent result to NormalizedCollateralTable format
    normalized_table = FileStorage.convert_multiagent_to_collateral_table(
        multiagent_result
    )

    try:
        # Map to CSATerms using ADEMapper
        csa_terms = ade_mapper.map_to_csa_terms(
            ade_extraction=extraction_data,
            document_id=document_id,
            normalized_collateral_table=normalized_table,
        )

        # Save CSATerms if requested
        if save_csa_terms:
            file_path = FileStorage.save_csa_terms(csa_terms, settings.csa_terms_dir)

        # Return mapped CSA terms with party information
        return {
            "document_id": document_id,
            "status": "mapped",
            "party_a": csa_terms.party_a,
            "party_b": csa_terms.party_b,
            "party_a_threshold": csa_terms.party_a_threshold,
            "party_b_threshold": csa_terms.party_b_threshold,
            "party_a_minimum_transfer_amount": csa_terms.party_a_minimum_transfer_amount,
            "party_b_minimum_transfer_amount": csa_terms.party_b_minimum_transfer_amount,
            "party_a_independent_amount": csa_terms.party_a_independent_amount,
            "party_b_independent_amount": csa_terms.party_b_independent_amount,
            "rounding": csa_terms.rounding,
            "normalized_collateral_id": csa_terms.normalized_collateral_id,
            "collateral_items_count": len(csa_terms.eligible_collateral),
            "collateral_types": list(
                set(
                    item.standardized_type.value
                    for item in csa_terms.eligible_collateral
                )
            ),
            "valuation_agent": csa_terms.valuation_agent,
            "effective_date": (
                csa_terms.effective_date.isoformat()
                if csa_terms.effective_date
                else None
            ),
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to map to CSATerms: {str(e)}"
        )


@router.get("/csa-terms/{document_id}")
async def get_csa_terms(document_id: str):
    """
    Retrieve saved CSATerms for a document.

    Returns the complete CSATerms object with normalized collateral data.
    Uses explicit JSONResponse to ensure InfinityEncoder handles float('inf') values.
    """
    csa_terms = FileStorage.load_csa_terms(document_id, settings.csa_terms_dir)

    if not csa_terms:
        raise HTTPException(
            status_code=404, detail=f"CSATerms not found for document: {document_id}"
        )

    # Use explicit JSONResponse to ensure InfinityEncoder converts float('inf') -> "Infinity"
    return JSONResponse(content=csa_terms.model_dump(mode="json"))


@router.get("/parses/{parse_id}")
async def get_parse(parse_id: str):
    """
    Retrieve a previously saved parse result.
    """
    parse_data = ade_service.load_saved_parse(parse_id)

    if not parse_data:
        raise HTTPException(status_code=404, detail=f"Parse not found: {parse_id}")

    return parse_data


@router.get("/list")
async def list_documents():
    """
    List all uploaded documents with processing status.
    """
    try:
        documents = []
        for filename in os.listdir(settings.pdf_dir):
            if filename.endswith(".pdf"):
                file_path = os.path.join(settings.pdf_dir, filename)
                file_size = os.path.getsize(file_path)
                file_mtime = os.path.getmtime(file_path)

                # Extract document_id from filename (before extension)
                document_id = os.path.splitext(filename)[0]

                # Check processing status
                parse_files = [f for f in os.listdir(settings.parsed_dir) if document_id in f]
                extraction_files = [f for f in os.listdir(settings.extractions_dir) if document_id in f]

                # Check for normalized collateral
                normalized_collateral = FileStorage.load_normalized_collateral(
                    document_id, settings.normalized_collateral_dir
                )

                # Check for CSA terms
                csa_terms = FileStorage.load_csa_terms(document_id, settings.csa_terms_dir)

                # Check for calculations
                calc_files = []
                if os.path.exists(settings.calculations_dir):
                    for f in os.listdir(settings.calculations_dir):
                        if f.endswith(".json"):
                            calc_data = FileStorage.load_json(settings.calculations_dir, f)
                            if calc_data and calc_data.get("csa_terms_id") == document_id:
                                calc_files.append(f)

                # Build processing status
                processing_status = ProcessingStatus(
                    uploaded=True,
                    parsed=len(parse_files) > 0,
                    extracted=len(extraction_files) > 0,
                    normalized=normalized_collateral is not None,
                    mapped_to_csa_terms=csa_terms is not None,
                    has_calculations=len(calc_files) > 0,
                )

                # Extract party names from CSA terms if available
                counterparty_name = None
                party_a = None
                party_b = None
                if csa_terms:
                    party_a = csa_terms.party_a
                    party_b = csa_terms.party_b
                    # Keep counterparty_name for backward compatibility
                    counterparty_name = getattr(csa_terms, 'counterparty_name', None)

                documents.append(
                    {
                        "document_id": document_id,
                        "filename": filename,
                        "file_size": file_size,
                        "uploaded_at": datetime.fromtimestamp(file_mtime).isoformat(),
                        "counterparty_name": counterparty_name,
                        "party_a": party_a,
                        "party_b": party_b,
                        "status": "processed" if csa_terms else "uploaded",
                        "has_csa_terms": csa_terms is not None,
                        "has_calculations": len(calc_files) > 0,
                        "processing_status": processing_status.model_dump(),
                    }
                )

        return {"documents": documents, "count": len(documents)}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list documents: {str(e)}"
        )


@router.get("/{document_id}/detail", response_model=DocumentDetailResponse)
async def get_document_detail(document_id: str):
    """
    Get detailed information about a document and its processing status.

    Returns:
    - File metadata (name, size, upload time)
    - Processing status (which stages completed)
    - Related artifact IDs (parse_id, extraction_id, etc.)
    - Any processing errors
    """
    try:
        # Check if document exists
        pdf_files = [
            f for f in os.listdir(settings.pdf_dir) if f.startswith(document_id)
        ]
        if not pdf_files:
            raise HTTPException(
                status_code=404,
                detail=f"Document {document_id} not found. No PDF file exists.",
            )

        pdf_file = pdf_files[0]
        pdf_path = os.path.join(settings.pdf_dir, pdf_file)

        # Get file metadata
        file_stat = os.stat(pdf_path)
        filename = pdf_file.replace(f"{document_id}_", "")
        file_size = file_stat.st_size
        uploaded_at = datetime.fromtimestamp(file_stat.st_ctime)

        # Check processing status across all layers
        parse_files = [f for f in os.listdir(settings.parsed_dir) if document_id in f]
        extraction_files = [
            f for f in os.listdir(settings.extractions_dir) if document_id in f
        ]

        # Check for normalized collateral
        normalized_collateral = FileStorage.load_normalized_collateral(
            document_id, settings.normalized_collateral_dir
        )

        # Check for CSA terms
        csa_terms = FileStorage.load_csa_terms(document_id, settings.csa_terms_dir)

        # Check for calculations
        calc_files = []
        if os.path.exists(settings.calculations_dir):
            for f in os.listdir(settings.calculations_dir):
                if f.endswith(".json"):
                    calc_data = FileStorage.load_json(settings.calculations_dir, f)
                    if calc_data and calc_data.get("csa_terms_id") == document_id:
                        calc_files.append(f)

        # Build processing status
        processing_status = ProcessingStatus(
            uploaded=True,
            parsed=len(parse_files) > 0,
            extracted=len(extraction_files) > 0,
            normalized=normalized_collateral is not None,
            mapped_to_csa_terms=csa_terms is not None,
            has_calculations=len(calc_files) > 0,
        )

        # Extract artifact IDs
        parse_id = None
        extraction_id = None
        if parse_files:
            parse_id = parse_files[0].replace(".json", "").replace("parse_", "")
        if extraction_files:
            extraction_id = (
                extraction_files[0].replace(".json", "").replace("extraction_", "")
            )

        calculation_ids = [f.replace(".json", "").replace("margin_call_", "") for f in calc_files]

        artifact_ids = ArtifactIds(
            parse_id=parse_id,
            extraction_id=extraction_id,
            normalized_collateral_id=document_id if normalized_collateral else None,
            csa_terms_id=document_id if csa_terms else None,
            calculation_ids=calculation_ids,
        )

        # Build response
        return DocumentDetailResponse(
            document_id=document_id,
            filename=filename,
            file_size=file_size,
            uploaded_at=uploaded_at,
            processing_status=processing_status,
            artifact_ids=artifact_ids,
            errors=[],  # TODO: Implement error tracking
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve document details: {str(e)}",
        )


@router.delete("/{document_id}")
async def delete_document(document_id: str):
    """
    Delete a document and all associated parsed/extracted data.
    """
    try:
        # Delete PDF file
        pdf_files = [
            f for f in os.listdir(settings.pdf_dir) if f.startswith(document_id)
        ]
        for pdf_file in pdf_files:
            os.remove(os.path.join(settings.pdf_dir, pdf_file))

        # Delete parsed files
        parse_files = [f for f in os.listdir(settings.parsed_dir) if document_id in f]
        for parse_file in parse_files:
            os.remove(os.path.join(settings.parsed_dir, parse_file))

        # Delete extraction files
        extraction_files = [
            f for f in os.listdir(settings.extractions_dir) if document_id in f
        ]
        for extraction_file in extraction_files:
            os.remove(os.path.join(settings.extractions_dir, extraction_file))

        return {
            "status": "deleted",
            "document_id": document_id,
            "files_deleted": len(pdf_files) + len(parse_files) + len(extraction_files),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete document: {str(e)}"
        )


# ===== Multi-Agent Reasoning Retrieval Endpoints =====


@router.get("/normalized-multiagent/{normalized_id}/reasoning")
async def get_all_reasoning_chains(normalized_id: str):
    """
    Get complete reasoning chains from all agents for a normalized result.

    Returns the full reasoning chain from each agent including:
    - Step-by-step reasoning
    - Models used
    - Confidence scores
    - Processing times
    """
    # Load the normalized result
    normalized_dir = os.path.join(settings.data_dir, "normalized_multiagent")
    result_path = os.path.join(normalized_dir, f"{normalized_id}.json")

    if not os.path.exists(result_path):
        raise HTTPException(
            status_code=404,
            detail=f"Normalized result not found: {normalized_id}"
        )

    import json
    with open(result_path, "r") as f:
        result_data = json.load(f)

    # Extract reasoning chains from each agent
    reasoning_chains = {}
    agent_results = result_data.get("agent_results", {})

    for agent_name, agent_result in agent_results.items():
        reasoning_chains[agent_name] = {
            "agent_name": agent_name,
            "confidence": agent_result.get("confidence"),
            "self_corrections": agent_result.get("self_corrections", 0),
            "processing_time_seconds": agent_result.get("processing_time_seconds"),
            "reasoning_chain": agent_result.get("reasoning_chain", [])
        }

    return {
        "normalized_data_id": normalized_id,
        "agent_reasoning_chains": reasoning_chains,
        "total_agents": len(reasoning_chains),
        "total_reasoning_steps": sum(
            len(chain.get("reasoning_chain", []))
            for chain in reasoning_chains.values()
        )
    }


@router.get("/normalized-multiagent/{normalized_id}/reasoning/{agent_name}")
async def get_agent_reasoning(normalized_id: str, agent_name: str):
    """
    Get reasoning chain for a specific agent.

    Args:
        normalized_id: ID of normalized result
        agent_name: Agent name (collateral, temporal, currency)

    Returns detailed reasoning chain for the specified agent.
    """
    # Load the normalized result
    normalized_dir = os.path.join(settings.data_dir, "normalized_multiagent")
    result_path = os.path.join(normalized_dir, f"{normalized_id}.json")

    if not os.path.exists(result_path):
        raise HTTPException(
            status_code=404,
            detail=f"Normalized result not found: {normalized_id}"
        )

    import json
    with open(result_path, "r") as f:
        result_data = json.load(f)

    # Get specific agent result
    agent_results = result_data.get("agent_results", {})

    if agent_name not in agent_results:
        available_agents = list(agent_results.keys())
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_name}' not found. Available agents: {available_agents}"
        )

    agent_result = agent_results[agent_name]

    return {
        "normalized_data_id": normalized_id,
        "agent_name": agent_name,
        "confidence": agent_result.get("confidence"),
        "self_corrections": agent_result.get("self_corrections", 0),
        "requires_human_review": agent_result.get("requires_human_review", False),
        "human_review_reason": agent_result.get("human_review_reason"),
        "processing_time_seconds": agent_result.get("processing_time_seconds"),
        "reasoning_chain": agent_result.get("reasoning_chain", []),
        "normalized_data": agent_result.get("data", {})
    }


@router.get("/normalized-multiagent/{normalized_id}/validation")
async def get_validation_report(normalized_id: str):
    """
    Get validation report for a normalized result.

    Returns:
    - Validation checks performed
    - Warnings and errors
    - Recommendations
    """
    # Load the normalized result
    normalized_dir = os.path.join(settings.data_dir, "normalized_multiagent")
    result_path = os.path.join(normalized_dir, f"{normalized_id}.json")

    if not os.path.exists(result_path):
        raise HTTPException(
            status_code=404,
            detail=f"Normalized result not found: {normalized_id}"
        )

    import json
    with open(result_path, "r") as f:
        result_data = json.load(f)

    validation_report = result_data.get("validation_report", {})

    return {
        "normalized_data_id": normalized_id,
        "validation_report": validation_report
    }


# ===== Unified Processing Pipeline =====


@router.post("/process/{document_id}")
async def process_document_unified(
    document_id: str,
    background_tasks: BackgroundTasks,
    normalize_method: str = Query("multi-agent", description="Normalization method: 'simple' or 'multi-agent'"),
    save_intermediate_steps: bool = Query(False, description="Save intermediate files for debugging"),
    calculate_margin: bool = Query(False, description="Calculate margin call as final step"),
    portfolio_value: Optional[float] = Query(None, description="Portfolio value for margin calculation")
):
    """
    Unified document processing endpoint - orchestrates entire pipeline.

    This endpoint eliminates the need for users to manually chain together
    parse -> extract -> normalize -> map steps. Instead, it orchestrates
    the entire pipeline server-side and returns a job_id for tracking.

    Workflow:
    1. Parse PDF using ADE (Step 1)
    2. Extract CSA terms using ADE (Step 2)
    3. Normalize extracted data using AI (Step 3)
    4. Map to CSATerms model (Step 4)
    5. Calculate margin call (Step 5, optional)

    Processing happens in the background. Use GET /jobs/{job_id} to poll for status.

    Args:
        document_id: Document to process (must be uploaded first)
        background_tasks: FastAPI background tasks
        normalize_method: "simple" or "multi-agent" (default: "multi-agent")
        save_intermediate_steps: Save intermediate files for debugging (default: False)
        calculate_margin: Run margin calculation as final step (default: False)
        portfolio_value: Portfolio value for margin calculation (required if calculate_margin=True)

    Returns:
        Job information with job_id for polling

    Example:
        POST /api/v1/documents/process/abc-123?normalize_method=multi-agent

        Response:
        {
            "job_id": "job_abc-123_1234567890",
            "document_id": "abc-123",
            "status": "processing",
            "polling_url": "/api/v1/jobs/job_abc-123_1234567890"
        }
    """
    # Validate document exists
    pdf_files = [f for f in os.listdir(settings.pdf_dir) if f.startswith(document_id)]
    if not pdf_files:
        raise HTTPException(
            status_code=404,
            detail=f"Document not found: {document_id}"
        )

    # Create process options
    try:
        options = ProcessOptions(
            normalize_method=normalize_method,
            save_intermediate_steps=save_intermediate_steps,
            calculate_margin=calculate_margin,
            portfolio_value=portfolio_value
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Create job
    job_manager = get_job_manager()
    timestamp = int(datetime.utcnow().timestamp() * 1000)
    job_id = f"job_{document_id}_{timestamp}"

    job_state = job_manager.create_job(
        job_id=job_id,
        document_id=document_id,
        options={
            "normalize_method": normalize_method,
            "save_intermediate_steps": save_intermediate_steps,
            "calculate_margin": calculate_margin,
            "portfolio_value": portfolio_value
        }
    )

    # Start background processing
    orchestrator = get_pipeline_orchestrator(job_manager)
    background_tasks.add_task(
        orchestrator.run_pipeline,
        job_id=job_id,
        document_id=document_id,
        options=options
    )

    return {
        "job_id": job_id,
        "document_id": document_id,
        "status": "processing",
        "polling_url": f"/api/v1/jobs/{job_id}",
        "created_at": job_state["created_at"]
    }


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """
    Get status of a background processing job.

    Poll this endpoint to track progress of unified document processing.

    Args:
        job_id: Job identifier (returned from POST /process/{document_id})

    Returns:
        Job state including:
        - status: "pending", "processing", "completed", "failed", or "cancelled"
        - current_step: Current processing step
        - progress: Progress percentage (0-100)
        - results: Partial or complete results
        - errors: Any errors encountered
        - step_timings: Time taken for each step

    Example Response (In Progress):
        {
            "job_id": "job_abc-123_1234567890",
            "document_id": "abc-123",
            "status": "processing",
            "current_step": "normalize",
            "progress": 60,
            "created_at": "2025-01-07T10:00:00",
            "started_at": "2025-01-07T10:00:01",
            "results": {
                "parse_id": "parse_abc-123_1234567890",
                "extraction_id": "extract_parse_abc-123_1234567890"
            },
            "step_timings": {
                "parse": 2.5,
                "extract": 3.2
            }
        }

    Example Response (Completed):
        {
            "job_id": "job_abc-123_1234567890",
            "document_id": "abc-123",
            "status": "completed",
            "current_step": "done",
            "progress": 100,
            "created_at": "2025-01-07T10:00:00",
            "completed_at": "2025-01-07T10:02:30",
            "results": {
                "parse_id": "parse_abc-123_1234567890",
                "extraction_id": "extract_parse_abc-123_1234567890",
                "normalized_collateral": [...],
                "csa_terms": {...}
            },
            "step_timings": {
                "parse": 2.5,
                "extract": 3.2,
                "normalize": 85.4,
                "map": 1.1,
                "total": 92.2
            }
        }
    """
    try:
        job_manager = get_job_manager()
        job_state = job_manager.get_job(job_id)

        if not job_state:
            raise HTTPException(
                status_code=404,
                detail=f"Job not found: {job_id}"
            )

        return job_state

    except HTTPException:
        # Re-raise HTTP exceptions (like 404)
        raise
    except Exception as e:
        logger.error(f"Error retrieving job status for {job_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve job status: {str(e)}"
        )


@router.get("/jobs")
async def list_jobs(
    document_id: Optional[str] = Query(None, description="Filter by document ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(100, description="Maximum number of jobs to return")
):
    """
    List background processing jobs.

    Args:
        document_id: Filter by document ID (optional)
        status: Filter by status: pending, processing, completed, failed (optional)
        limit: Maximum number of jobs to return (default: 100)

    Returns:
        List of jobs sorted by created_at descending
    """
    job_manager = get_job_manager()
    jobs = job_manager.list_jobs(
        document_id=document_id,
        status=status,
        limit=limit
    )

    return {
        "jobs": jobs,
        "count": len(jobs)
    }


@router.delete("/jobs/{job_id}")
async def cancel_job(job_id: str):
    """
    Cancel a running job.

    Note: This marks the job as cancelled but does not immediately stop
    the background task. The task should check job status periodically
    and stop if cancelled.

    Args:
        job_id: Job identifier

    Returns:
        Updated job state
    """
    job_manager = get_job_manager()
    job_state = job_manager.cancel_job(job_id)

    if not job_state:
        raise HTTPException(
            status_code=404,
            detail=f"Job not found: {job_id}"
        )

    return {
        "status": "cancelled",
        "job_id": job_id,
        "message": "Job has been marked as cancelled"
    }
