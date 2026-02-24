"""
Base class for all normalizer agents.

Provides common functionality:
- Claude API integration
- Reasoning chain tracking
- Quality assessment
- Result formatting
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import json
import re
import time
import asyncio
from anthropic import AsyncAnthropic

from app.models.agent_schemas import (
    AgentResult,
    ReasoningStep,
)


class BaseNormalizerAgent(ABC):
    """Abstract base class for all normalizer agents"""

    # Class-level semaphore for rate limiting API calls across all agent instances
    _api_semaphore: Optional[asyncio.Semaphore] = None

    def __init__(self, api_key: str):
        self.client = AsyncAnthropic(api_key=api_key)
        self.agent_name: str = self.__class__.__name__
        self.reasoning_chain: List[ReasoningStep] = []
        self.haiku_model = "claude-haiku-4-5-20251001"
        self.sonnet_model = "claude-sonnet-4-5-20250929"

        # Initialize class-level semaphore if not already created
        if BaseNormalizerAgent._api_semaphore is None:
            # Import config to get max_concurrent_llm_calls
            try:
                from app.config import settings
                max_concurrent = settings.max_concurrent_llm_calls
            except ImportError:
                max_concurrent = 10  # Fallback default

            BaseNormalizerAgent._api_semaphore = asyncio.Semaphore(max_concurrent)

    @abstractmethod
    async def normalize(
        self,
        data: Dict[str, Any],
        document_context: Optional[Dict[str, Any]] = None
    ) -> AgentResult:
        """
        Main normalization method - must be implemented by subclasses.

        Args:
            data: Field data to normalize
            document_context: Optional parsed document with chunks for context access

        Returns:
            AgentResult with normalized data and reasoning chain
        """
        pass

    async def _call_claude(
        self,
        prompt: str,
        model: str = "claude-3-5-haiku-20241022",
        temperature: float = 0,
        max_tokens: int = 4000
    ) -> Dict[str, Any]:
        """
        Helper to call Claude API with rate limiting.

        Args:
            prompt: The prompt to send
            model: Model to use (haiku or sonnet)
            temperature: Temperature for sampling (0 = deterministic)
            max_tokens: Maximum tokens in response

        Returns:
            Parsed JSON response or dict with raw_text if not JSON
        """
        # Use semaphore to limit concurrent API calls
        async with self._api_semaphore:
            response = await self.client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}]
            )

            text = response.content[0].text

            # Strip markdown code blocks if present
            # Pattern matches: ```json\n{...}\n``` (with optional text after)
            # Remove the $ anchor to allow text after the code block
            markdown_pattern = r'```(?:json)?\s*\n(.*?)\n```'
            match = re.search(markdown_pattern, text, re.DOTALL)
            if match:
                text = match.group(1)

            # Try to parse as JSON
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                # If not JSON, return as text wrapper
                return {"raw_text": text, "parsed": False}

    def _add_reasoning_step(
        self,
        step_number: int,
        step_name: str,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        reasoning: str,
        model_used: str,
        confidence: Optional[float] = None,
        duration_seconds: Optional[float] = None
    ):
        """
        Add step to reasoning chain.

        Args:
            step_number: Sequential step number
            step_name: Name of the step (e.g., "initial_parse")
            input_data: Input to this step
            output_data: Output from this step
            reasoning: Explanation of what happened in this step
            model_used: "haiku", "sonnet", or "rule-based"
            confidence: Optional confidence score for this step
            duration_seconds: Optional execution time
        """
        step = ReasoningStep(
            step_number=step_number,
            step_name=step_name,
            input=input_data,
            output=output_data,
            model_used=model_used,
            reasoning=reasoning,
            confidence=confidence,
            duration_seconds=duration_seconds
        )
        self.reasoning_chain.append(step)

    def _clear_reasoning_chain(self):
        """Clear reasoning chain for new normalization"""
        self.reasoning_chain = []

    def assess_quality(self, result: Dict[str, Any]) -> float:
        """
        Assess quality of normalized result.

        Default implementation - can be overridden by subclasses.

        Args:
            result: Normalized result to assess

        Returns:
            Quality score between 0.0 and 1.0
        """
        # Default: high confidence if no obvious issues
        return 0.9

    def _count_corrections(self) -> int:
        """
        Count number of self-corrections in reasoning chain.

        Returns:
            Number of corrections made
        """
        corrections = 0
        for step in self.reasoning_chain:
            if "corrections" in step.output:
                corrections += len(step.output.get("corrections", []))
        return corrections

    def _get_overall_confidence(self) -> float:
        """
        Calculate overall confidence from reasoning chain.

        Returns:
            Average confidence across all steps that have confidence scores
        """
        confidences = [
            step.confidence for step in self.reasoning_chain
            if step.confidence is not None
        ]

        if not confidences:
            return 0.8  # Default moderate confidence

        return sum(confidences) / len(confidences)

    def _needs_human_review(self, confidence: float, threshold: float = 0.85) -> bool:
        """
        Determine if result needs human review based on confidence.

        Args:
            confidence: Overall confidence score
            threshold: Minimum confidence to avoid review

        Returns:
            True if human review needed
        """
        return confidence < threshold

    def _format_result(
        self,
        data: Dict[str, Any],
        processing_time: float,
        confidence: Optional[float] = None
    ) -> AgentResult:
        """
        Format final agent result.

        Args:
            data: Normalized data
            processing_time: Total processing time in seconds
            confidence: Optional overall confidence (calculated if not provided)

        Returns:
            Formatted AgentResult
        """
        final_confidence = confidence if confidence is not None else self._get_overall_confidence()

        return AgentResult(
            agent_name=self.agent_name,
            data=data,
            confidence=final_confidence,
            reasoning_chain=self.reasoning_chain.copy(),
            self_corrections=self._count_corrections(),
            requires_human_review=self._needs_human_review(final_confidence),
            human_review_reason=(
                f"Low confidence ({final_confidence:.2f}) below threshold (0.85)"
                if self._needs_human_review(final_confidence)
                else None
            ),
            processing_time_seconds=processing_time
        )

    def _get_chunk_by_id(
        self,
        chunk_id: str,
        document_context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific chunk from parsed document.

        Args:
            chunk_id: ID of chunk to retrieve
            document_context: Parsed document with chunks

        Returns:
            Chunk dict or None if not found
        """
        if not document_context or "chunks" not in document_context:
            return None

        for chunk in document_context.get("chunks", []):
            if chunk.get("id") == chunk_id:
                return chunk

        return None

    def _get_surrounding_chunks(
        self,
        chunk_id: str,
        document_context: Dict[str, Any],
        before: int = 1,
        after: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Get surrounding chunks for context.

        Args:
            chunk_id: Target chunk ID
            document_context: Parsed document
            before: Number of chunks before target
            after: Number of chunks after target

        Returns:
            List of chunks including target and surrounding
        """
        if not document_context or "chunks" not in document_context:
            return []

        chunks = document_context.get("chunks", [])

        # Find target chunk index
        target_idx = None
        for idx, chunk in enumerate(chunks):
            if chunk.get("id") == chunk_id:
                target_idx = idx
                break

        if target_idx is None:
            return []

        # Get surrounding chunks
        start_idx = max(0, target_idx - before)
        end_idx = min(len(chunks), target_idx + after + 1)

        return chunks[start_idx:end_idx]
