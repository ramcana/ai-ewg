"""
Intelligence Chain Orchestrator for the Video Processing Pipeline

Coordinates the four-stage AI processing pipeline: diarization, entity extraction,
disambiguation, and proficiency scoring with error handling and fallback mechanisms.
"""

import asyncio
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass

from .config import PipelineConfig
from .logging import get_logger
from .models import EpisodeObject, EnrichmentResult
from .exceptions import ProcessingError, TransientError

logger = get_logger('pipeline.intelligence_chain')


@dataclass
class ChainStageResult:
    """Result of a single intelligence chain stage"""
    stage: str
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration: float = 0.0
    metrics: Optional[Dict[str, Any]] = None


@dataclass
class IntelligenceChainResult:
    """Complete result of intelligence chain processing"""
    success: bool
    diarization: Optional[ChainStageResult] = None
    entities: Optional[ChainStageResult] = None
    disambiguation: Optional[ChainStageResult] = None
    proficiency_scores: Optional[ChainStageResult] = None
    total_duration: float = 0.0
    error: Optional[str] = None


class IntelligenceChainOrchestrator:
    """
    Orchestrates the four-stage AI processing pipeline
    
    Stages:
    1. Speaker Diarization - Identify speakers in audio
    2. Entity Extraction - Extract people, organizations, topics
    3. Disambiguation - Enrich entities with external data
    4. Proficiency Scoring - Calculate credibility scores
    """
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.logger = logger
        
        # Paths to utility scripts
        self.utils_dir = Path(__file__).parent.parent.parent / "utils"
        self.diarize_script = self.utils_dir / "diarize.py"
        self.extract_entities_script = self.utils_dir / "extract_entities.py"
        self.disambiguate_script = self.utils_dir / "disambiguate.py"
        self.score_people_script = self.utils_dir / "score_people.py"
        
        # Validate utility scripts exist
        self._validate_utilities()
    
    def _validate_utilities(self) -> None:
        """Validate that all utility scripts exist"""
        scripts = [
            self.diarize_script,
            self.extract_entities_script,
            self.disambiguate_script,
            self.score_people_script
        ]
        
        missing = [script for script in scripts if not script.exists()]
        if missing:
            raise ProcessingError(
                f"Missing utility scripts: {[str(s) for s in missing]}",
                stage="intelligence_chain_init"
            )
    
    async def process_episode(self, episode: EpisodeObject, 
                            audio_path: str, 
                            transcript_text: str) -> IntelligenceChainResult:
        """
        Process an episode through the complete intelligence chain
        
        Args:
            episode: Episode object with metadata
            audio_path: Path to audio file for diarization
            transcript_text: Plain text transcript for entity extraction
            
        Returns:
            IntelligenceChainResult: Complete processing results
        """
        start_time = time.time()
        
        self.logger.info(
            "Starting intelligence chain processing",
            episode_id=episode.episode_id,
            audio_path=audio_path
        )
        
        result = IntelligenceChainResult(success=False)
        
        try:
            # Create temporary directory for intermediate files
            with tempfile.TemporaryDirectory(prefix="intelligence_chain_") as temp_dir:
                temp_path = Path(temp_dir)
                
                # Stage 1: Speaker Diarization
                diarization_result = await self._run_diarization(
                    audio_path, temp_path, episode.episode_id
                )
                result.diarization = diarization_result
                
                if not diarization_result.success:
                    result.error = f"Diarization failed: {diarization_result.error}"
                    return result
                
                # Stage 2: Entity Extraction
                entities_result = await self._run_entity_extraction(
                    transcript_text, temp_path, episode.episode_id
                )
                result.entities = entities_result
                
                if not entities_result.success:
                    result.error = f"Entity extraction failed: {entities_result.error}"
                    return result
                
                # Stage 3: Disambiguation
                disambiguation_result = await self._run_disambiguation(
                    entities_result.data, temp_path, episode.episode_id
                )
                result.disambiguation = disambiguation_result
                
                if not disambiguation_result.success:
                    result.error = f"Disambiguation failed: {disambiguation_result.error}"
                    return result
                
                # Stage 4: Proficiency Scoring
                scoring_result = await self._run_proficiency_scoring(
                    disambiguation_result.data, 
                    entities_result.data.get('topics', []),
                    temp_path, 
                    episode.episode_id
                )
                result.proficiency_scores = scoring_result
                
                if not scoring_result.success:
                    result.error = f"Proficiency scoring failed: {scoring_result.error}"
                    return result
                
                # Success - all stages completed
                result.success = True
                result.total_duration = time.time() - start_time
                
                self.logger.info(
                    "Intelligence chain processing completed successfully",
                    episode_id=episode.episode_id,
                    duration=result.total_duration,
                    num_speakers=len(diarization_result.data.get('segments', [])),
                    num_entities=len(entities_result.data.get('candidates', [])),
                    num_enriched=len(disambiguation_result.data.get('enriched_people', [])),
                    num_scored=len(scoring_result.data.get('scored_people', []))
                )
                
                return result
        
        except Exception as e:
            result.error = str(e)
            result.total_duration = time.time() - start_time
            
            self.logger.error(
                "Intelligence chain processing failed",
                episode_id=episode.episode_id,
                exception=e,
                duration=result.total_duration
            )
            
            return result
    
    async def _run_diarization(self, audio_path: str, temp_path: Path, 
                             episode_id: str) -> ChainStageResult:
        """Run speaker diarization stage"""
        start_time = time.time()
        stage = "diarization"
        
        try:
            self.logger.info(f"Running {stage}", episode_id=episode_id)
            
            # Prepare output file
            segments_file = temp_path / "diarization_segments.json"
            
            # Build command
            cmd = [
                "python", str(self.diarize_script),
                "--audio", audio_path,
                "--segments_out", str(segments_file),
                "--device", self.config.models.diarization_device,
                "--merge_gap", "2.0"
            ]
            
            # Add HF token if available
            if self.config.hf_token:
                cmd.extend(["--hf_token", self.config.hf_token])
            
            # Add number of speakers if configured
            if self.config.models.num_speakers > 0:
                cmd.extend(["--num_speakers", str(self.config.models.num_speakers)])
            
            # Execute command
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Diarization process failed"
                return ChainStageResult(
                    stage=stage,
                    success=False,
                    error=error_msg,
                    duration=time.time() - start_time
                )
            
            # Load and validate results
            if not segments_file.exists():
                return ChainStageResult(
                    stage=stage,
                    success=False,
                    error="Diarization output file not created",
                    duration=time.time() - start_time
                )
            
            with open(segments_file, 'r', encoding='utf-8') as f:
                diarization_data = json.load(f)
            
            # Validate diarization quality
            validation_result = self._validate_diarization(diarization_data)
            
            duration = time.time() - start_time
            
            return ChainStageResult(
                stage=stage,
                success=True,
                data=diarization_data,
                duration=duration,
                metrics={
                    'num_segments': len(diarization_data.get('segments', [])),
                    'num_speakers': diarization_data.get('num_speakers', 0),
                    'total_duration': diarization_data.get('total_duration', 0),
                    'validation': validation_result
                }
            )
        
        except Exception as e:
            return ChainStageResult(
                stage=stage,
                success=False,
                error=str(e),
                duration=time.time() - start_time
            )
    
    async def _run_entity_extraction(self, transcript_text: str, temp_path: Path,
                                   episode_id: str) -> ChainStageResult:
        """Run entity extraction stage"""
        start_time = time.time()
        stage = "entity_extraction"
        
        try:
            self.logger.info(f"Running {stage}", episode_id=episode_id)
            
            # Prepare input and output files
            transcript_file = temp_path / "transcript.txt"
            entities_file = temp_path / "entities.json"
            
            # Write transcript to file
            with open(transcript_file, 'w', encoding='utf-8') as f:
                f.write(transcript_text)
            
            # Build command - try LLM first, fallback to spaCy
            cmd = [
                "python", str(self.extract_entities_script),
                "--transcript", str(transcript_file),
                "--output", str(entities_file),
                "--method", "llm",
                "--model", self.config.models.llm,
                "--ollama_url", self.config.ollama_url
            ]
            
            # Execute command
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            # If LLM method failed, try spaCy fallback
            if process.returncode != 0:
                self.logger.warning(
                    "LLM entity extraction failed, trying spaCy fallback",
                    episode_id=episode_id,
                    error=stderr.decode() if stderr else "Unknown error"
                )
                
                # Try spaCy method
                cmd[cmd.index("llm")] = "spacy"  # Replace method
                # Remove LLM-specific arguments
                if "--model" in cmd:
                    model_idx = cmd.index("--model")
                    cmd.pop(model_idx + 1)  # Remove model value
                    cmd.pop(model_idx)      # Remove --model flag
                if "--ollama_url" in cmd:
                    url_idx = cmd.index("--ollama_url")
                    cmd.pop(url_idx + 1)    # Remove URL value
                    cmd.pop(url_idx)        # Remove --ollama_url flag
                
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Entity extraction process failed"
                return ChainStageResult(
                    stage=stage,
                    success=False,
                    error=error_msg,
                    duration=time.time() - start_time
                )
            
            # Load and validate results
            if not entities_file.exists():
                return ChainStageResult(
                    stage=stage,
                    success=False,
                    error="Entity extraction output file not created",
                    duration=time.time() - start_time
                )
            
            with open(entities_file, 'r', encoding='utf-8') as f:
                entities_data = json.load(f)
            
            # Apply journalistic relevance filtering
            filtered_data = self._filter_journalistic_entities(entities_data)
            
            duration = time.time() - start_time
            
            return ChainStageResult(
                stage=stage,
                success=True,
                data=filtered_data,
                duration=duration,
                metrics={
                    'num_candidates': len(filtered_data.get('candidates', [])),
                    'num_topics': len(filtered_data.get('topics', [])),
                    'extraction_method': filtered_data.get('extraction_method', 'unknown'),
                    'filtered_candidates': len(entities_data.get('candidates', [])) - len(filtered_data.get('candidates', []))
                }
            )
        
        except Exception as e:
            return ChainStageResult(
                stage=stage,
                success=False,
                error=str(e),
                duration=time.time() - start_time
            )
    
    async def _run_disambiguation(self, entities_data: Dict[str, Any], temp_path: Path,
                                episode_id: str) -> ChainStageResult:
        """Run disambiguation stage"""
        start_time = time.time()
        stage = "disambiguation"
        
        try:
            self.logger.info(f"Running {stage}", episode_id=episode_id)
            
            # Prepare input and output files
            candidates_file = temp_path / "candidates.json"
            enriched_file = temp_path / "enriched.json"
            
            # Write candidates to file
            with open(candidates_file, 'w', encoding='utf-8') as f:
                json.dump(entities_data, f, indent=2, ensure_ascii=False)
            
            # Build command
            cmd = [
                "python", str(self.disambiguate_script),
                "--candidates", str(candidates_file),
                "--output", str(enriched_file),
                "--min_confidence", str(self.config.thresholds.confidence_min),
                "--rate_limit", str(self.config.api_rate_limit_delay)
            ]
            
            # Execute command
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Disambiguation process failed"
                return ChainStageResult(
                    stage=stage,
                    success=False,
                    error=error_msg,
                    duration=time.time() - start_time
                )
            
            # Load and validate results
            if not enriched_file.exists():
                return ChainStageResult(
                    stage=stage,
                    success=False,
                    error="Disambiguation output file not created",
                    duration=time.time() - start_time
                )
            
            with open(enriched_file, 'r', encoding='utf-8') as f:
                enriched_data = json.load(f)
            
            # Add authority verification
            verified_data = self._verify_authority_sources(enriched_data)
            
            duration = time.time() - start_time
            
            return ChainStageResult(
                stage=stage,
                success=True,
                data=verified_data,
                duration=duration,
                metrics={
                    'num_enriched': len(verified_data.get('enriched_people', [])),
                    'success_rate': verified_data.get('summary', {}).get('success_rate', 0),
                    'authority_verified': sum(1 for p in verified_data.get('enriched_people', []) 
                                            if p.get('authority_verified', False))
                }
            )
        
        except Exception as e:
            return ChainStageResult(
                stage=stage,
                success=False,
                error=str(e),
                duration=time.time() - start_time
            )
    
    async def _run_proficiency_scoring(self, enriched_data: Dict[str, Any], 
                                     topics: List[str], temp_path: Path,
                                     episode_id: str) -> ChainStageResult:
        """Run proficiency scoring stage"""
        start_time = time.time()
        stage = "proficiency_scoring"
        
        try:
            self.logger.info(f"Running {stage}", episode_id=episode_id)
            
            # Prepare input and output files
            enriched_file = temp_path / "enriched_for_scoring.json"
            scored_file = temp_path / "scored.json"
            
            # Write enriched data to file
            with open(enriched_file, 'w', encoding='utf-8') as f:
                json.dump(enriched_data, f, indent=2, ensure_ascii=False)
            
            # Build command
            cmd = [
                "python", str(self.score_people_script),
                "--enriched", str(enriched_file),
                "--output", str(scored_file)
            ]
            
            # Add topics if available
            if topics:
                cmd.extend(["--topics"] + topics)
            
            # Execute command
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Proficiency scoring process failed"
                return ChainStageResult(
                    stage=stage,
                    success=False,
                    error=error_msg,
                    duration=time.time() - start_time
                )
            
            # Load and validate results
            if not scored_file.exists():
                return ChainStageResult(
                    stage=stage,
                    success=False,
                    error="Proficiency scoring output file not created",
                    duration=time.time() - start_time
                )
            
            with open(scored_file, 'r', encoding='utf-8') as f:
                scored_data = json.load(f)
            
            # Apply journalistic credibility standards
            credibility_data = self._apply_journalistic_standards(scored_data)
            
            duration = time.time() - start_time
            
            return ChainStageResult(
                stage=stage,
                success=True,
                data=credibility_data,
                duration=duration,
                metrics={
                    'num_scored': len(credibility_data.get('scored_people', [])),
                    'avg_score': credibility_data.get('summary', {}).get('avg_score', 0),
                    'verified_experts': credibility_data.get('summary', {}).get('verified_experts', 0),
                    'identified_contributors': credibility_data.get('summary', {}).get('identified_contributors', 0)
                }
            )
        
        except Exception as e:
            return ChainStageResult(
                stage=stage,
                success=False,
                error=str(e),
                duration=time.time() - start_time
            )
    
    def _validate_diarization(self, diarization_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate diarization quality and consistency"""
        segments = diarization_data.get('segments', [])
        issues = []
        
        if len(segments) < 5:
            issues.append("Too few segments - possible diarization failure")
        
        # Check speaker balance
        speakers = {}
        for seg in segments:
            speaker = seg.get('speaker', 'unknown')
            speakers[speaker] = speakers.get(speaker, 0) + seg.get('duration', 0)
        
        if len(speakers) < 2:
            issues.append("Only one speaker detected")
        
        # Check reasonable speaker distribution
        total_time = sum(speakers.values())
        for speaker, time in speakers.items():
            ratio = time / total_time if total_time > 0 else 0
            if ratio < 0.05:
                issues.append(f"{speaker} speaks < 5% of time - possible error")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'speaker_distribution': speakers,
            'quality_score': max(0, 1.0 - len(issues) * 0.2)
        }
    
    def _filter_journalistic_entities(self, entities_data: Dict[str, Any]) -> Dict[str, Any]:
        """Filter entities for journalistic relevance"""
        candidates = entities_data.get('candidates', [])
        topics = entities_data.get('topics', [])
        
        # Filter candidates by confidence and journalistic relevance
        filtered_candidates = []
        
        for candidate in candidates:
            confidence = candidate.get('confidence', 0)
            
            # Apply minimum confidence threshold
            if confidence < self.config.thresholds.entity_confidence:
                continue
            
            # Check for journalistic relevance indicators
            name = candidate.get('name', '').lower()
            role = candidate.get('role_guess', '').lower()
            quotes = candidate.get('quotes', [])
            
            # Skip if name is too generic or short
            if len(name.split()) < 2 or len(name) < 4:
                continue
            
            # Boost confidence for authoritative roles
            authority_roles = [
                'minister', 'secretary', 'director', 'chief', 'president',
                'professor', 'doctor', 'economist', 'analyst', 'expert'
            ]
            
            if any(role_term in role for role_term in authority_roles):
                candidate['confidence'] = min(1.0, confidence + 0.1)
                candidate['journalistic_relevance'] = 'high'
            elif role:
                candidate['journalistic_relevance'] = 'medium'
            else:
                candidate['journalistic_relevance'] = 'low'
            
            # Add contextual quote extraction for credibility
            if quotes:
                candidate['credibility_quotes'] = self._extract_credibility_quotes(quotes)
            
            filtered_candidates.append(candidate)
        
        # Sort by confidence and journalistic relevance
        filtered_candidates.sort(
            key=lambda x: (x.get('confidence', 0), 
                          {'high': 3, 'medium': 2, 'low': 1}.get(x.get('journalistic_relevance', 'low'), 1)),
            reverse=True
        )
        
        return {
            **entities_data,
            'candidates': filtered_candidates,
            'filtering_applied': True,
            'original_count': len(candidates),
            'filtered_count': len(filtered_candidates)
        }
    
    def _extract_credibility_quotes(self, quotes: List[str]) -> List[str]:
        """Extract quotes that enhance credibility"""
        credibility_quotes = []
        
        # Look for quotes that establish expertise or authority
        credibility_indicators = [
            'according to', 'research shows', 'data indicates', 'study found',
            'analysis reveals', 'evidence suggests', 'statistics show',
            'my experience', 'we found', 'our research'
        ]
        
        for quote in quotes[:3]:  # Limit to first 3 quotes
            quote_lower = quote.lower()
            if any(indicator in quote_lower for indicator in credibility_indicators):
                credibility_quotes.append(quote.strip())
        
        return credibility_quotes[:2]  # Return top 2 credibility quotes
    
    def _verify_authority_sources(self, enriched_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add authority verification for journalistic credibility"""
        enriched_people = enriched_data.get('enriched_people', [])
        
        for person in enriched_people:
            # Check for authoritative sources
            same_as = person.get('same_as', [])
            affiliation = person.get('affiliation', '').lower()
            
            authority_verified = False
            authority_sources = []
            
            # Check URLs for authority domains
            authority_domains = ['.gov', '.gc.ca', '.edu', '.ac.uk', '.org']
            for url in same_as:
                for domain in authority_domains:
                    if domain in url.lower():
                        authority_verified = True
                        authority_sources.append(domain)
            
            # Check affiliation for authority indicators
            authority_orgs = [
                'government', 'university', 'college', 'bank of canada',
                'federal reserve', 'european central bank', 'imf', 'world bank'
            ]
            
            for org in authority_orgs:
                if org in affiliation:
                    authority_verified = True
                    authority_sources.append(org)
            
            person['authority_verified'] = authority_verified
            person['authority_sources'] = list(set(authority_sources))
            
            # Boost confidence for verified authorities
            if authority_verified:
                person['confidence'] = min(1.0, person.get('confidence', 0) + 0.1)
        
        return enriched_data
    
    def _apply_journalistic_standards(self, scored_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply journalistic credibility standards to scoring"""
        scored_people = scored_data.get('scored_people', [])
        
        for person in scored_people:
            score = person.get('proficiencyScore', 0)
            badge = person.get('credibilityBadge', 'Unverified')
            
            # Apply journalistic standards for badge assignment
            authority_verified = person.get('authority_verified', False)
            
            if authority_verified and score >= self.config.thresholds.expert_score:
                person['credibilityBadge'] = 'Verified Expert'
                person['editorial_decision'] = 'Recommend for prominent attribution'
            elif authority_verified and score >= self.config.thresholds.publish_score:
                person['credibilityBadge'] = 'Identified Contributor'
                person['editorial_decision'] = 'Suitable for standard attribution'
            elif score >= self.config.thresholds.publish_score:
                person['credibilityBadge'] = 'Guest'
                person['editorial_decision'] = 'Use with context and verification'
            else:
                person['credibilityBadge'] = 'Unverified'
                person['editorial_decision'] = 'Requires additional verification before use'
            
            # Add reasoning for editorial decision support
            reasoning_parts = []
            if authority_verified:
                reasoning_parts.append('verified through authoritative sources')
            if score >= 0.75:
                reasoning_parts.append('high credibility score')
            elif score >= 0.60:
                reasoning_parts.append('moderate credibility score')
            else:
                reasoning_parts.append('limited credibility verification')
            
            person['editorial_reasoning'] = '; '.join(reasoning_parts).capitalize()
        
        return scored_data
    
    def create_enrichment_result(self, chain_result: IntelligenceChainResult) -> EnrichmentResult:
        """Convert intelligence chain result to EnrichmentResult model"""
        return EnrichmentResult(
            diarization=chain_result.diarization.data if chain_result.diarization and chain_result.diarization.success else None,
            entities=chain_result.entities.data if chain_result.entities and chain_result.entities.success else None,
            disambiguation=chain_result.disambiguation.data if chain_result.disambiguation and chain_result.disambiguation.success else None,
            proficiency_scores=chain_result.proficiency_scores.data if chain_result.proficiency_scores and chain_result.proficiency_scores.success else None
        )