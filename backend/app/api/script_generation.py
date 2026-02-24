"""
API endpoints for CSA audit script generation.

Provides endpoints to generate, retrieve, and manage annotated Python audit scripts
that document CSA calculation logic with clause citations and pattern annotations.
"""

import logging
import os
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field

from app.config import settings
from app.services.agents.script_generator_agent import ScriptGeneratorAgent
from app.services.pattern_extraction_service import PatternExtractionService
from app.models.formula_schemas import FormulaPatternResult
from app.models.schemas import CSATerms, MarginCall
from app.utils.file_storage import FileStorage

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response models
class GenerateScriptRequest(BaseModel):
    """Request to generate an audit script."""

    calculation_id: str = Field(description="Calculation ID for the margin call")
    force_regenerate: bool = Field(
        default=False,
        description="Force regeneration even if script already exists"
    )


class GenerateScriptResponse(BaseModel):
    """Response after generating an audit script."""

    status: str = Field(description="Status of the generation")
    calculation_id: str = Field(description="Calculation ID")
    script: str = Field(description="Generated Python script")
    script_path: str = Field(description="Path where script was saved")
    generation_time_seconds: float = Field(description="Time taken for generation")
    patterns_used: bool = Field(description="Whether formula patterns were used")
    patterns_auto_extracted: bool = Field(
        description="Whether patterns were automatically extracted (vs loaded from cache)"
    )
    pattern_extraction_time_seconds: Optional[float] = Field(
        default=None,
        description="Time taken for pattern extraction if it was performed"
    )
    script_stats: dict = Field(description="Statistics about the generated script")


class GetScriptResponse(BaseModel):
    """Response for retrieving a stored script."""

    script: str = Field(description="Generated Python script")
    generated_at: str = Field(description="ISO timestamp of generation")
    patterns_used: bool = Field(description="Whether formula patterns were used")
    script_stats: dict = Field(description="Statistics about the script")


class ScriptMetadata(BaseModel):
    """Metadata about a generated script."""

    calculation_id: str
    document_id: str
    generated_at: str
    script_path: str
    script_length: int
    script_lines: int
    patterns_used: bool


@router.post("/{calculation_id}/generate", response_model=GenerateScriptResponse)
async def generate_audit_script(
    calculation_id: str = Path(..., description="Calculation ID")
):
    """
    Generate an audit script for a margin calculation.

    This endpoint generates a transparent, annotated Python script that documents
    the CSA calculation logic with:
    - Clause citations and page numbers
    - Pattern-aware annotations
    - Step-by-step calculation logic
    - Comparisons to other CSA patterns

    The script is saved to disk and returned. It is NOT meant for execution,
    but rather as audit documentation.

    If formula patterns don't exist for the document, they will be automatically
    extracted before generating the script. This may extend the response time but
    ensures the script is always generated successfully.

    Args:
        calculation_id: Unique identifier for the margin calculation

    Returns:
        GenerateScriptResponse with the generated script and metadata,
        including information about whether patterns were auto-extracted

    Raises:
        HTTPException 404: If calculation, CSA terms, or required extraction data not found
        HTTPException 500: If pattern extraction or script generation fails
    """
    import time

    start_time = time.time()

    try:
        logger.info(f"Starting script generation for calculation {calculation_id}")

        # Step 1: Load margin call data
        try:
            margin_call_data = FileStorage.load_json(
                settings.calculations_dir,
                f"margin_call_{calculation_id}"
            )
            margin_call = MarginCall(**margin_call_data)
            logger.info(f"Loaded margin call for calculation {calculation_id}")
        except FileNotFoundError:
            raise HTTPException(
                status_code=404,
                detail=f"Calculation {calculation_id} not found"
            )

        # Step 2: Extract document_id from margin call
        # Try multiple potential fields
        document_id = (
            margin_call_data.get("document_id") or
            margin_call_data.get("csa_terms_id") or
            margin_call_data.get("doc_id")
        )

        if not document_id:
            raise HTTPException(
                status_code=400,
                detail="Cannot determine document_id from margin call data"
            )

        # Step 3: Load or extract formula patterns
        try:
            logger.info(f"Checking for formula patterns for document {document_id}")
            pattern_service = PatternExtractionService(settings.anthropic_api_key)

            # This will load existing patterns or extract new ones if missing
            formula_patterns, was_cached, extraction_time = await pattern_service.extract_or_load_patterns(
                document_id=document_id,
                force_reextract=False
            )

            patterns_used = True
            if was_cached:
                logger.info(f"Loaded cached formula patterns for document {document_id}")
            else:
                logger.info(
                    f"Extracted new formula patterns for document {document_id} "
                    f"in {extraction_time:.2f}s"
                )
        except FileNotFoundError as e:
            logger.error(f"Required data not found for pattern extraction: {str(e)}")
            raise HTTPException(
                status_code=404,
                detail=str(e)
            )
        except Exception as e:
            logger.error(f"Pattern extraction/loading failed: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Pattern extraction failed: {str(e)}"
            )

        # Step 4: Load CSA terms
        try:
            csa_terms_data = FileStorage.load_json(
                settings.csa_terms_dir,
                f"csa_terms_{document_id}"
            )
            csa_terms = CSATerms(**csa_terms_data)
            logger.info(f"Loaded CSA terms for document {document_id}")
        except FileNotFoundError:
            raise HTTPException(
                status_code=404,
                detail=f"CSA terms not found for document {document_id}"
            )

        # Step 5: Generate script using Script Generator Agent
        try:
            agent = ScriptGeneratorAgent(api_key=settings.anthropic_api_key)

            script = await agent.generate_audit_script(
                formula_patterns=formula_patterns,
                csa_terms=csa_terms,
                margin_call=margin_call,
                document_id=document_id
            )

            logger.info(
                f"Successfully generated script: {len(script)} chars, "
                f"{len(script.split(chr(10)))} lines"
            )

        except ValueError as e:
            logger.error(f"Script generation validation error: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Script generation validation failed: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Script generation error: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Script generation failed: {str(e)}"
            )

        # Step 6: Save script to disk
        script_filename = f"audit_{calculation_id}.py"
        script_path = os.path.join(settings.generated_scripts_dir, script_filename)

        try:
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(script)

            logger.info(f"Saved script to {script_path}")

        except Exception as e:
            logger.error(f"Failed to save script: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save script: {str(e)}"
            )

        # Step 7: Save metadata
        metadata = ScriptMetadata(
            calculation_id=calculation_id,
            document_id=document_id,
            generated_at=datetime.utcnow().isoformat(),
            script_path=script_path,
            script_length=len(script),
            script_lines=len(script.split('\n')),
            patterns_used=patterns_used
        )

        metadata_path = os.path.join(
            settings.generated_scripts_dir,
            f"metadata_{calculation_id}.json"
        )

        try:
            import json
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata.dict(), f, indent=2)

        except Exception as e:
            logger.warning(f"Failed to save metadata: {str(e)}")
            # Non-critical, continue

        # Step 8: Calculate stats
        generation_time = time.time() - start_time
        script_stats = {
            "length_chars": len(script),
            "length_lines": len(script.split('\n')),
            "has_docstring": '"""' in script or "'''" in script,
            "has_type_hints": "->" in script,
            "generation_time": generation_time
        }

        logger.info(
            f"Script generation complete for {calculation_id} in {generation_time:.2f}s"
        )

        return GenerateScriptResponse(
            status="success",
            calculation_id=calculation_id,
            script=script,
            script_path=script_path,
            generation_time_seconds=generation_time,
            patterns_used=patterns_used,
            patterns_auto_extracted=not was_cached,
            pattern_extraction_time_seconds=extraction_time if not was_cached else None,
            script_stats=script_stats
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in script generation: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )


@router.get("/{calculation_id}/script", response_model=GetScriptResponse)
async def get_audit_script(
    calculation_id: str = Path(..., description="Calculation ID")
):
    """
    Retrieve a previously generated audit script.

    Args:
        calculation_id: Unique identifier for the margin calculation

    Returns:
        GetScriptResponse with the script and metadata

    Raises:
        HTTPException 404: If script not found
    """
    try:
        # Load script
        script_path = os.path.join(
            settings.generated_scripts_dir,
            f"audit_{calculation_id}.py"
        )

        if not os.path.exists(script_path):
            raise HTTPException(
                status_code=404,
                detail=f"Audit script not found for calculation {calculation_id}"
            )

        with open(script_path, 'r', encoding='utf-8') as f:
            script = f.read()

        # Load metadata if available
        metadata_path = os.path.join(
            settings.generated_scripts_dir,
            f"metadata_{calculation_id}.json"
        )

        if os.path.exists(metadata_path):
            import json
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

            generated_at = metadata.get("generated_at", "unknown")
            patterns_used = metadata.get("patterns_used", True)
        else:
            # Fallback if metadata missing
            generated_at = datetime.fromtimestamp(
                os.path.getmtime(script_path)
            ).isoformat()
            patterns_used = True

        # Calculate stats
        script_stats = {
            "length_chars": len(script),
            "length_lines": len(script.split('\n')),
            "has_docstring": '"""' in script or "'''" in script,
            "has_type_hints": "->" in script
        }

        return GetScriptResponse(
            script=script,
            generated_at=generated_at,
            patterns_used=patterns_used,
            script_stats=script_stats
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving script: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve script: {str(e)}"
        )


@router.delete("/{calculation_id}/script")
async def delete_audit_script(
    calculation_id: str = Path(..., description="Calculation ID")
):
    """
    Delete a generated audit script and its metadata.

    This forces regeneration on next request.

    Args:
        calculation_id: Unique identifier for the margin calculation

    Returns:
        Success message

    Raises:
        HTTPException 404: If script not found
    """
    try:
        script_path = os.path.join(
            settings.generated_scripts_dir,
            f"audit_{calculation_id}.py"
        )

        metadata_path = os.path.join(
            settings.generated_scripts_dir,
            f"metadata_{calculation_id}.json"
        )

        # Check if script exists
        if not os.path.exists(script_path):
            raise HTTPException(
                status_code=404,
                detail=f"Audit script not found for calculation {calculation_id}"
            )

        # Delete script
        os.remove(script_path)
        logger.info(f"Deleted script: {script_path}")

        # Delete metadata if exists
        if os.path.exists(metadata_path):
            os.remove(metadata_path)
            logger.info(f"Deleted metadata: {metadata_path}")

        return {
            "status": "success",
            "message": f"Audit script for calculation {calculation_id} deleted",
            "calculation_id": calculation_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting script: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete script: {str(e)}"
        )
