"""
Intelligence Chain Orchestrator V2 - Rock-solid, cached, auditable

Upgraded version with:
- Typed pydantic models with schema versioning
- Content-addressed caching for idempotent reruns
- DAG-based step execution with dependencies
- Provenance tracking and explainability
- Quality gates with fail-soft mechanisms
- CLI support for --force, --from-step, --until-step
"""

import asyncio
import hashlib
import json
import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from .config import PipelineConfig
from .logging import get_logger
from .models import EpisodeObject
from .exceptions import ProcessingError

from .intelligence_models import ChainContext, ChainResult
from .intelligence_cache import IntelligenceCache
from .intelligence_executor import IntelligenceExecutor, StepRegistry, StepDefinition
from .intelligence_quality import QualityGateManager
from .intelligence_adapters import (
    adapt_diarization_result,
    adapt_entities_result,
    adapt_resolution_result,
    adapt_proficiency_result,
    load_and_adapt_json
)

logger = get_logger('pipeline.intelligence_chain_v2')


class IntelligenceChainOrchestratorV2:
    """
    V2 Orchestrator with caching, provenance, and quality gates
    """
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.logger = logger
        
        # Setup paths
        self.utils_dir = Path(__file__).parent.parent.parent / "utils"
        self.cache_dir = Path("data/cache")
        self.meta_dir = Path("data/meta")
        self.explain_dir = Path("data/meta")
        
        # Initialize components
        self.cache = IntelligenceCache(self.cache_dir)
        self.registry = StepRegistry()
        self.executor = IntelligenceExecutor(
            self.cache,
            self.registry,
            self.meta_dir,
            self.explain_dir
        )
        self.quality_manager = QualityGateManager()
        
        # Register steps
        self._register_steps()
        
        # Validate utilities
        self._validate_utilities()
    
    def _validate_utilities(self) -> None:
        """Validate that all utility scripts exist"""
        scripts = [
            self.utils_dir / "diarize.py",
            self.utils_dir / "extract_entities.py",
            self.utils_dir / "disambiguate.py",
            self.utils_dir / "score_people.py"
        ]
        
        missing = [script for script in scripts if not script.exists()]
        if missing:
            raise ProcessingError(
                f"Missing utility scripts: {[str(s) for s in missing]}",
                stage="intelligence_chain_init"
            )
    
    def _register_steps(self) -> None:
        """Register intelligence chain steps with dependencies"""
        from .intelligence_models import (
            DiarizationResult, EntitiesResult, ResolutionResult, ProficiencyResult
        )
        
        # Step 1: Diarization (no dependencies)
        self.registry.register(StepDefinition(
            name="diarization",
            executor=self._execute_diarization,
            result_type=DiarizationResult,
            requires=[],
            version="1.0.0"
        ))
        
        # Step 2: Entity Extraction (no dependencies)
        self.registry.register(StepDefinition(
            name="extract_entities",
            executor=self._execute_entity_extraction,
            result_type=EntitiesResult,
            requires=[],
            version="1.0.0"
        ))
        
        # Step 3: Disambiguation (requires entities)
        self.registry.register(StepDefinition(
            name="disambiguate",
            executor=self._execute_disambiguation,
            result_type=ResolutionResult,
            requires=["extract_entities"],
            version="1.0.0"
        ))
        
        # Step 4: Proficiency Scoring (requires disambiguation and entities)
        self.registry.register(StepDefinition(
            name="score_people",
            executor=self._execute_proficiency_scoring,
            result_type=ProficiencyResult,
            requires=["disambiguate", "extract_entities"],
            version="1.0.0"
        ))
    
    async def process_episode(
        self,
        episode: EpisodeObject,
        audio_path: str,
        transcript_text: str,
        force_rerun: bool = False,
        start_from_step: Optional[str] = None,
        stop_at_step: Optional[str] = None
    ) -> ChainResult:
        """
        Process episode through intelligence chain
        
        Args:
            episode: Episode object
            audio_path: Path to audio file
            transcript_text: Transcript text
            force_rerun: Force rerun (ignore cache)
            start_from_step: Start from this step
            stop_at_step: Stop at this step
            
        Returns:
            ChainResult with all outputs and metadata
        """
        # Generate job ID
        job_id = f"{episode.episode_id}-{uuid.uuid4().hex[:8]}"
        
        # Compute hashes
        video_hash = self.cache.compute_video_hash(audio_path)
        config_hash = self._compute_config_hash()
        
        # Create context
        context = ChainContext(
            job_id=job_id,
            episode_id=episode.episode_id,
            video_hash=video_hash,
            config_hash=config_hash,
            paths={
                'audio': audio_path,
                'transcript': transcript_text
            },
            force_rerun=force_rerun,
            start_from_step=start_from_step,
            stop_at_step=stop_at_step
        )
        
        self.logger.info(
            "Starting intelligence chain V2",
            job_id=job_id,
            episode_id=episode.episode_id,
            video_hash=video_hash[:16],
            force_rerun=force_rerun
        )
        
        # Prepare initial inputs
        initial_inputs = {
            'audio_path': audio_path,
            'transcript_text': transcript_text,
            'episode': episode
        }
        
        # Run chain
        result = await self.executor.run_chain(context, initial_inputs)
        
        # Run quality gates
        if result.success:
            quality_results = {}
            if result.diarization:
                quality_results['diarization'] = result.diarization
            if result.entities:
                quality_results['extract_entities'] = result.entities
            if result.resolution:
                quality_results['disambiguate'] = result.resolution
            if result.proficiency:
                quality_results['score_people'] = result.proficiency
            
            quality_report = self.quality_manager.generate_quality_report(quality_results)
            
            # Write quality report
            self._write_quality_report(job_id, quality_report)
            
            self.logger.info(
                "Quality assessment complete",
                job_id=job_id,
                overall_quality=quality_report['overall_quality']
            )
        
        return result
    
    def _compute_config_hash(self) -> str:
        """Compute hash of configuration affecting intelligence chain"""
        config_dict = {
            'whisper_model': self.config.models.whisper,
            'llm_model': self.config.models.llm,
            'diarization_device': self.config.models.diarization_device,
            'num_speakers': self.config.models.num_speakers,
            'confidence_min': self.config.thresholds.confidence_min,
            'entity_confidence': self.config.thresholds.entity_confidence,
            'expert_score': self.config.thresholds.expert_score,
            'publish_score': self.config.thresholds.publish_score,
            'ollama_url': self.config.ollama_url
        }
        return self.cache.compute_config_hash(config_dict)
    
    async def _execute_diarization(
        self,
        context: ChainContext,
        inputs: Dict[str, Any]
    ):
        """Execute diarization step"""
        audio_path = inputs['audio_path']
        
        with tempfile.TemporaryDirectory(prefix="diarization_") as temp_dir:
            temp_path = Path(temp_dir)
            segments_file = temp_path / "diarization_segments.json"
            
            # Build command
            cmd = [
                "python", str(self.utils_dir / "diarize.py"),
                "--audio", audio_path,
                "--segments_out", str(segments_file),
                "--device", self.config.models.diarization_device,
                "--merge_gap", "2.0"
            ]
            
            if self.config.hf_token:
                cmd.extend(["--hf_token", self.config.hf_token])
            
            if self.config.models.num_speakers > 0:
                cmd.extend(["--num_speakers", str(self.config.models.num_speakers)])
            
            # Execute
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Diarization failed"
                raise ProcessingError(error_msg, stage="diarization")
            
            if not segments_file.exists():
                raise ProcessingError("Diarization output not created", stage="diarization")
            
            # Load and adapt result
            result = load_and_adapt_json(segments_file, adapt_diarization_result)
            
            return result
    
    async def _execute_entity_extraction(
        self,
        context: ChainContext,
        inputs: Dict[str, Any]
    ):
        """Execute entity extraction step"""
        transcript_text = inputs['transcript_text']
        
        with tempfile.TemporaryDirectory(prefix="entities_") as temp_dir:
            temp_path = Path(temp_dir)
            transcript_file = temp_path / "transcript.txt"
            entities_file = temp_path / "entities.json"
            
            # Write transcript
            with open(transcript_file, 'w', encoding='utf-8') as f:
                f.write(transcript_text)
            
            # Build command (try LLM first)
            cmd = [
                "python", str(self.utils_dir / "extract_entities.py"),
                "--transcript", str(transcript_file),
                "--output", str(entities_file),
                "--method", "llm",
                "--model", self.config.models.llm,
                "--ollama_url", self.config.ollama_url
            ]
            
            # Execute
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            # Try spaCy fallback if LLM fails
            if process.returncode != 0:
                self.logger.warning("LLM extraction failed, trying spaCy fallback")
                
                cmd = [
                    "python", str(self.utils_dir / "extract_entities.py"),
                    "--transcript", str(transcript_file),
                    "--output", str(entities_file),
                    "--method", "spacy"
                ]
                
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Entity extraction failed"
                raise ProcessingError(error_msg, stage="extract_entities")
            
            if not entities_file.exists():
                raise ProcessingError("Entity extraction output not created", stage="extract_entities")
            
            # Load and adapt result
            result = load_and_adapt_json(entities_file, adapt_entities_result)
            
            return result
    
    async def _execute_disambiguation(
        self,
        context: ChainContext,
        inputs: Dict[str, Any]
    ):
        """Execute disambiguation step"""
        entities_result = inputs.get('extract_entities')
        if not entities_result:
            raise ProcessingError("Missing entities input", stage="disambiguate")
        
        with tempfile.TemporaryDirectory(prefix="disambiguate_") as temp_dir:
            temp_path = Path(temp_dir)
            candidates_file = temp_path / "candidates.json"
            enriched_file = temp_path / "enriched.json"
            
            # Write candidates
            with open(candidates_file, 'w', encoding='utf-8') as f:
                f.write(entities_result.model_dump_json(indent=2))
            
            # Build command
            cmd = [
                "python", str(self.utils_dir / "disambiguate.py"),
                "--candidates", str(candidates_file),
                "--output", str(enriched_file),
                "--min_confidence", str(self.config.thresholds.confidence_min),
                "--rate_limit", str(self.config.api_rate_limit_delay)
            ]
            
            # Execute
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Disambiguation failed"
                raise ProcessingError(error_msg, stage="disambiguate")
            
            if not enriched_file.exists():
                raise ProcessingError("Disambiguation output not created", stage="disambiguate")
            
            # Load and adapt result
            result = load_and_adapt_json(enriched_file, adapt_resolution_result)
            
            return result
    
    async def _execute_proficiency_scoring(
        self,
        context: ChainContext,
        inputs: Dict[str, Any]
    ):
        """Execute proficiency scoring step"""
        resolution_result = inputs.get('disambiguate')
        entities_result = inputs.get('extract_entities')
        
        if not resolution_result:
            raise ProcessingError("Missing resolution input", stage="score_people")
        
        with tempfile.TemporaryDirectory(prefix="scoring_") as temp_dir:
            temp_path = Path(temp_dir)
            enriched_file = temp_path / "enriched.json"
            scored_file = temp_path / "scored.json"
            
            # Write enriched data
            with open(enriched_file, 'w', encoding='utf-8') as f:
                f.write(resolution_result.model_dump_json(indent=2))
            
            # Build command
            cmd = [
                "python", str(self.utils_dir / "score_people.py"),
                "--enriched", str(enriched_file),
                "--output", str(scored_file)
            ]
            
            # Add topics if available
            if entities_result and entities_result.topics:
                cmd.extend(["--topics"] + entities_result.topics[:10])
            
            # Execute
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Proficiency scoring failed"
                raise ProcessingError(error_msg, stage="score_people")
            
            if not scored_file.exists():
                raise ProcessingError("Proficiency scoring output not created", stage="score_people")
            
            # Load and adapt result
            result = load_and_adapt_json(scored_file, adapt_proficiency_result)
            
            return result
    
    def _write_quality_report(self, job_id: str, report: Dict[str, Any]) -> None:
        """Write quality report to meta directory"""
        try:
            report_path = self.meta_dir / f"{job_id}.quality.json"
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2)
            
            self.logger.debug(f"Wrote quality report: {report_path}")
        
        except Exception as e:
            self.logger.error(f"Failed to write quality report: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return self.cache.get_cache_stats()
    
    def clear_cache(self, step_name: Optional[str] = None) -> int:
        """Clear cache for specific step or all steps"""
        if step_name:
            return self.cache.clear_step_cache(step_name)
        else:
            return self.cache.clear_all_cache()
