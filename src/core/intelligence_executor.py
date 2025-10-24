"""
Step execution orchestrator for intelligence chain

Provides run_step() scaffold with caching, timing, error capture,
and artifact generation. Supports DAG-based execution with dependencies.
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Callable, TypeVar, List, Tuple
from pydantic import BaseModel

from .intelligence_models import (
    ChainContext, ChainMetadata, StepMetrics, StepWarning,
    ExplainabilityPayload, ChainResult,
    DiarizationResult, EntitiesResult, ResolutionResult, ProficiencyResult
)
from .intelligence_cache import IntelligenceCache, CacheKey
from .logging import get_logger
from .exceptions import ProcessingError

logger = get_logger('pipeline.intelligence_executor')

T = TypeVar('T', bound=BaseModel)


class StepDefinition:
    """Definition of a single intelligence chain step"""
    
    def __init__(
        self,
        name: str,
        executor: Callable,
        result_type: type[BaseModel],
        requires: Optional[List[str]] = None,
        version: str = "1.0.0"
    ):
        self.name = name
        self.executor = executor
        self.result_type = result_type
        self.requires = requires or []
        self.version = version
    
    def __repr__(self) -> str:
        return f"StepDefinition(name={self.name}, requires={self.requires})"


class StepRegistry:
    """Registry of intelligence chain steps with dependency tracking"""
    
    def __init__(self):
        self.steps: Dict[str, StepDefinition] = {}
        self.logger = logger
    
    def register(self, step: StepDefinition) -> None:
        """Register a step"""
        if step.name in self.steps:
            self.logger.warning(f"Overwriting step definition: {step.name}")
        
        self.steps[step.name] = step
        self.logger.debug(f"Registered step: {step.name}")
    
    def get(self, name: str) -> Optional[StepDefinition]:
        """Get step definition by name"""
        return self.steps.get(name)
    
    def get_execution_order(self, start_from: Optional[str] = None, stop_at: Optional[str] = None) -> List[str]:
        """
        Get topologically sorted execution order
        
        Args:
            start_from: Start from this step (skip earlier steps)
            stop_at: Stop at this step (skip later steps)
            
        Returns:
            List of step names in execution order
        """
        # Simple topological sort (assumes no cycles)
        order = []
        visited = set()
        
        def visit(name: str):
            if name in visited:
                return
            
            step = self.steps.get(name)
            if not step:
                raise ValueError(f"Unknown step: {name}")
            
            # Visit dependencies first
            for dep in step.requires:
                visit(dep)
            
            visited.add(name)
            order.append(name)
        
        # Visit all steps
        for name in self.steps:
            visit(name)
        
        # Apply start_from and stop_at filters
        if start_from:
            try:
                start_idx = order.index(start_from)
                order = order[start_idx:]
            except ValueError:
                raise ValueError(f"start_from step not found: {start_from}")
        
        if stop_at:
            try:
                stop_idx = order.index(stop_at)
                order = order[:stop_idx + 1]
            except ValueError:
                raise ValueError(f"stop_at step not found: {stop_at}")
        
        return order
    
    def list_steps(self) -> List[str]:
        """List all registered step names"""
        return list(self.steps.keys())


class IntelligenceExecutor:
    """
    Orchestrates intelligence chain execution with caching and provenance
    """
    
    def __init__(
        self,
        cache: IntelligenceCache,
        registry: StepRegistry,
        meta_dir: Path,
        explain_dir: Path
    ):
        self.cache = cache
        self.registry = registry
        self.meta_dir = Path(meta_dir)
        self.explain_dir = Path(explain_dir)
        self.logger = logger
        
        # Create directories
        self.meta_dir.mkdir(parents=True, exist_ok=True)
        self.explain_dir.mkdir(parents=True, exist_ok=True)
    
    async def run_step(
        self,
        step_name: str,
        context: ChainContext,
        inputs: Optional[Dict[str, Any]] = None,
        metadata: Optional[ChainMetadata] = None,
        explain: Optional[ExplainabilityPayload] = None
    ) -> Tuple[BaseModel, StepMetrics, Optional[Dict[str, Any]]]:
        """
        Run a single step with caching, timing, and error capture
        
        Args:
            step_name: Name of step to run
            context: Chain execution context
            inputs: Input data for step
            metadata: Chain metadata (updated in place)
            explain: Explainability payload (updated in place)
            
        Returns:
            Tuple of (result, metrics, explain_data)
        """
        start_time = time.time()
        inputs = inputs or {}
        
        # Get step definition
        step_def = self.registry.get(step_name)
        if not step_def:
            raise ValueError(f"Unknown step: {step_name}")
        
        self.logger.info(f"Running step: {step_name}", job_id=context.job_id)
        
        # Create cache key
        cache_key = CacheKey(
            step_name=step_name,
            video_hash=context.video_hash,
            config_hash=context.config_hash,
            step_version=step_def.version
        )
        
        # Check cache (unless force_rerun)
        cached_result = None
        cache_hit = False
        
        if not context.force_rerun:
            cached_result = self.cache.get_cache(cache_key, step_def.result_type)
            if cached_result:
                cache_hit = True
                duration_ms = (time.time() - start_time) * 1000
                
                self.logger.info(
                    f"Using cached result: {step_name}",
                    cache_key=cache_key.to_string()
                )
                
                # Create metrics
                metrics = StepMetrics(
                    step_name=step_name,
                    duration_ms=duration_ms,
                    cache_hit=True,
                    cache_key=cache_key.to_string()
                )
                
                # Update metadata
                if metadata:
                    metadata.steps_cached.append(step_name)
                    metadata.cache_hits += 1
                    metadata.metrics.append(metrics)
                
                return cached_result, metrics, None
        
        # Execute step
        try:
            # Compute input hash for provenance
            input_hash = self.cache.compute_data_hash(inputs) if inputs else None
            
            # Run executor
            result = await step_def.executor(context, inputs)
            
            # Validate result type
            if not isinstance(result, step_def.result_type):
                raise TypeError(
                    f"Step {step_name} returned {type(result)}, expected {step_def.result_type}"
                )
            
            duration_ms = (time.time() - start_time) * 1000
            
            # Cache result
            self.cache.set_cache(
                cache_key,
                result,
                duration_ms=duration_ms,
                input_hash=input_hash
            )
            
            # Compute output hash
            output_hash = self.cache.compute_data_hash(result)
            
            # Create metrics
            metrics = StepMetrics(
                step_name=step_name,
                duration_ms=duration_ms,
                cache_hit=False,
                cache_key=cache_key.to_string(),
                input_hash=input_hash,
                output_hash=output_hash
            )
            
            # Update metadata
            if metadata:
                metadata.steps_completed.append(step_name)
                metadata.cache_misses += 1
                metadata.metrics.append(metrics)
            
            # Extract explainability data
            explain_data = self._extract_explain_data(step_name, result, inputs)
            
            self.logger.info(
                f"Step completed: {step_name}",
                duration_ms=duration_ms,
                output_hash=output_hash[:16]
            )
            
            return result, metrics, explain_data
        
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.error(
                f"Step failed: {step_name}",
                exception=e,
                duration_ms=duration_ms
            )
            
            # Create error metrics
            metrics = StepMetrics(
                step_name=step_name,
                duration_ms=duration_ms,
                cache_hit=False
            )
            
            # Update metadata
            if metadata:
                metadata.steps_failed.append(step_name)
                metadata.metrics.append(metrics)
                metadata.warnings.append(StepWarning(
                    step_name=step_name,
                    severity="error",
                    message=str(e)
                ))
            
            raise ProcessingError(
                f"Step {step_name} failed: {e}",
                stage=step_name
            ) from e
    
    def _extract_explain_data(
        self,
        step_name: str,
        result: BaseModel,
        inputs: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Extract explainability data from step result"""
        explain_data = {
            'step': step_name,
            'timestamp': datetime.now().isoformat()
        }
        
        # Step-specific extraction
        if step_name == 'diarization' and isinstance(result, DiarizationResult):
            explain_data['num_speakers'] = result.num_speakers
            explain_data['total_duration'] = result.total_duration
            explain_data['validation'] = result.validation
            explain_data['consistency'] = result.consistency
        
        elif step_name == 'extract_entities' and isinstance(result, EntitiesResult):
            explain_data['num_candidates'] = len(result.candidates)
            explain_data['extraction_method'] = result.extraction_method
            explain_data['filtering_applied'] = result.editorial_filtering_applied
            explain_data['candidate_names'] = [c.name for c in result.candidates[:10]]
        
        elif step_name == 'disambiguate' and isinstance(result, ResolutionResult):
            explain_data['num_enriched'] = len(result.enriched_people)
            explain_data['success_rate'] = result.summary.get('success_rate', 0)
            explain_data['authority_stats'] = result.summary.get('authority_verification', {})
            
            # Include decision traces for top candidates
            explain_data['decisions'] = []
            for person in result.enriched_people[:5]:
                explain_data['decisions'].append({
                    'name': person.name,
                    'confidence': person.confidence,
                    'authority_level': person.authority_level,
                    'decision_rule': person.decision_rule,
                    'candidates_considered': len(person.candidates_considered)
                })
        
        elif step_name == 'score_people' and isinstance(result, ProficiencyResult):
            explain_data['num_scored'] = len(result.scored_people)
            explain_data['avg_score'] = result.summary.get('avg_score', 0)
            
            # Include score breakdowns for top people
            explain_data['score_details'] = []
            for person in result.scored_people[:5]:
                explain_data['score_details'].append({
                    'name': person.name,
                    'score': person.proficiencyScore,
                    'badge': person.credibilityBadge,
                    'breakdown': person.scoreBreakdown.model_dump(),
                    'reasoning': person.reasoning
                })
        
        return explain_data
    
    async def run_chain(
        self,
        context: ChainContext,
        initial_inputs: Optional[Dict[str, Any]] = None
    ) -> ChainResult:
        """
        Run complete intelligence chain with dependency resolution
        
        Args:
            context: Chain execution context
            initial_inputs: Initial inputs (e.g., audio_path, transcript_text)
            
        Returns:
            ChainResult with all stage results and metadata
        """
        start_time = datetime.now()
        
        # Initialize metadata
        metadata = ChainMetadata(
            job_id=context.job_id,
            episode_id=context.episode_id,
            video_hash=context.video_hash,
            config_hash=context.config_hash,
            started_at=start_time
        )
        
        # Initialize explainability payload
        explain = ExplainabilityPayload(
            job_id=context.job_id,
            episode_id=context.episode_id
        )
        
        # Get execution order
        try:
            execution_order = self.registry.get_execution_order(
                start_from=context.start_from_step,
                stop_at=context.stop_at_step
            )
        except ValueError as e:
            return ChainResult(
                success=False,
                metadata=metadata,
                error=str(e)
            )
        
        self.logger.info(
            f"Starting chain execution: {len(execution_order)} steps",
            job_id=context.job_id,
            steps=execution_order
        )
        
        # Execute steps
        results = {}
        inputs = initial_inputs or {}
        
        try:
            for step_name in execution_order:
                # Run step
                result, metrics, explain_data = await self.run_step(
                    step_name,
                    context,
                    inputs,
                    metadata,
                    explain
                )
                
                # Store result
                results[step_name] = result
                
                # Update explainability
                if explain_data:
                    explain.decision_traces.append(explain_data)
                    
                    # Store in step-specific field
                    if step_name == 'diarization':
                        explain.diarization_explain = explain_data
                    elif step_name == 'extract_entities':
                        explain.entities_explain = explain_data
                    elif step_name == 'disambiguate':
                        explain.disambiguation_explain = explain_data
                    elif step_name == 'score_people':
                        explain.proficiency_explain = explain_data
                
                # Prepare inputs for next step
                inputs = {step_name: result}
            
            # All steps completed
            metadata.completed_at = datetime.now()
            metadata.total_duration_ms = (
                (metadata.completed_at - metadata.started_at).total_seconds() * 1000
            )
            
            # Write artifacts
            self._write_metadata(metadata)
            self._write_explain(explain)
            
            self.logger.info(
                f"Chain completed successfully",
                job_id=context.job_id,
                duration_ms=metadata.total_duration_ms,
                cache_hits=metadata.cache_hits,
                cache_misses=metadata.cache_misses
            )
            
            return ChainResult(
                success=True,
                metadata=metadata,
                diarization=results.get('diarization'),
                entities=results.get('extract_entities'),
                resolution=results.get('disambiguate'),
                proficiency=results.get('score_people')
            )
        
        except Exception as e:
            metadata.completed_at = datetime.now()
            metadata.total_duration_ms = (
                (metadata.completed_at - metadata.started_at).total_seconds() * 1000
            )
            
            # Write partial artifacts
            self._write_metadata(metadata)
            self._write_explain(explain)
            
            self.logger.error(
                f"Chain failed",
                job_id=context.job_id,
                exception=e,
                duration_ms=metadata.total_duration_ms
            )
            
            return ChainResult(
                success=False,
                metadata=metadata,
                diarization=results.get('diarization'),
                entities=results.get('extract_entities'),
                resolution=results.get('disambiguate'),
                proficiency=results.get('score_people'),
                error=str(e),
                error_step=metadata.steps_failed[-1] if metadata.steps_failed else None
            )
    
    def _write_metadata(self, metadata: ChainMetadata) -> None:
        """Write metadata to meta/{job_id}.json"""
        try:
            meta_path = self.meta_dir / f"{metadata.job_id}.json"
            with open(meta_path, 'w', encoding='utf-8') as f:
                f.write(metadata.model_dump_json(indent=2))
            
            self.logger.debug(f"Wrote metadata: {meta_path}")
        
        except Exception as e:
            self.logger.error(f"Failed to write metadata: {e}")
    
    def _write_explain(self, explain: ExplainabilityPayload) -> None:
        """Write explainability data to meta/{job_id}.explain.json"""
        try:
            explain_path = self.explain_dir / f"{explain.job_id}.explain.json"
            with open(explain_path, 'w', encoding='utf-8') as f:
                f.write(explain.model_dump_json(indent=2))
            
            self.logger.debug(f"Wrote explainability: {explain_path}")
        
        except Exception as e:
            self.logger.error(f"Failed to write explainability: {e}")
