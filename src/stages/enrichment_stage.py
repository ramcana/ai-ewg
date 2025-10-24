"""
Enrichment Stage Processor

Phase 1 - AI Analysis (Ollama):
1. Executive summary (2-3 paragraphs)
2. Key takeaways (5-7 items)
3. Deep analysis (themes, implications, impact)
4. Topics/Keywords (8-10 tags)
5. Segment titles (for transcript chunks)
6. Show name and host extraction

Phase 2 - Intelligence Chain V2:
1. Entity extraction (people, organizations)
2. Disambiguation (Wikidata matching)
3. Proficiency scoring (credibility badges)
4. Authority verification
5. Guest credentials generation

Creates: data/enriched/{episode_id}.json
"""

from pathlib import Path
from typing import Dict, Any, Optional
import json
import time

from ..core.logging import get_logger
from ..core.exceptions import ProcessingError
from ..core.models import EpisodeObject
from ..core.ollama_client import OllamaClient
from ..utils.transcript_cleaner import clean_transcript
from ..core.intelligence_chain_v2 import IntelligenceChainOrchestratorV2
from ..core.config import PipelineConfig

# Import diarization utility
import sys
from pathlib import Path
utils_path = Path(__file__).parent.parent.parent / "utils"
sys.path.insert(0, str(utils_path))
try:
    from diarize import diarize_audio, validate_diarization, check_speaker_consistency
    DIARIZATION_AVAILABLE = True
except ImportError:
    DIARIZATION_AVAILABLE = False
    logger.warning("Diarization not available - pyannote.audio not installed")

logger = get_logger('pipeline.enrichment_stage')


class EnrichmentStageProcessor:
    """
    Processes enrichment stage with AI-powered analysis
    
    Uses Ollama for generating professional editorial content:
    - Executive summaries
    - Key takeaways  
    - Deep analysis
    - Topic extraction
    - Segment title generation
    """
    
    def __init__(self, 
                 output_dir: str = "data/enriched",
                 ollama_host: str = "http://localhost:11434",
                 ollama_model: str = "llama3.1:latest",
                 ollama_enabled: bool = True,
                 diarization_enabled: bool = True,
                 diarization_device: str = "cuda",
                 num_speakers: int = 2,
                 hf_token: str = None,
                 intelligence_chain_enabled: bool = True,
                 config: Optional[PipelineConfig] = None):
        """
        Initialize enrichment processor
        
        Args:
            output_dir: Output directory for enrichment JSON files
            ollama_host: Ollama server URL
            ollama_model: Ollama model to use
            ollama_enabled: Whether to use Ollama (falls back to basic if False)
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.ollama_enabled = ollama_enabled
        self.ollama_client: Optional[OllamaClient] = None
        
        # Diarization settings
        self.diarization_enabled = diarization_enabled and DIARIZATION_AVAILABLE
        self.diarization_device = diarization_device
        self.num_speakers = num_speakers
        self.hf_token = hf_token
        
        # Intelligence Chain V2 settings (Phase 2)
        self.intelligence_chain_enabled = intelligence_chain_enabled
        self.intelligence_chain: Optional[IntelligenceChainOrchestratorV2] = None
        
        # Initialize intelligence chain if enabled
        if intelligence_chain_enabled:
            try:
                # Use provided config or create default
                if config is None:
                    from ..core.config import ConfigurationManager
                    config_manager = ConfigurationManager()
                    config = config_manager.load_config()
                
                self.intelligence_chain = IntelligenceChainOrchestratorV2(config)
                logger.info(
                    "Intelligence Chain V2 initialized",
                    enabled=True
                )
            except Exception as e:
                import traceback
                logger.error(
                    "Failed to initialize Intelligence Chain V2, Phase 2 features disabled",
                    error=str(e),
                    traceback=traceback.format_exc()
                )
                self.intelligence_chain = None
                self.intelligence_chain_enabled = False
        
        # Try to initialize Ollama client
        if ollama_enabled:
            try:
                self.ollama_client = OllamaClient(
                    host=ollama_host,
                    model=ollama_model,
                    timeout=300  # 5 minute timeout for AI generation
                )
                logger.info(
                    "Ollama client initialized",
                    host=ollama_host,
                    model=ollama_model
                )
            except Exception as e:
                logger.warning(
                    "Failed to initialize Ollama, will use basic enrichment",
                    error=str(e)
                )
                self.ollama_client = None
    
    async def process(self, episode: EpisodeObject, audio_path: str, transcript_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run AI enrichment on transcript
        
        Args:
            episode: Episode object
            audio_path: Path to audio file
            transcript_data: Transcript data from transcription stage
            
        Returns:
            Dict with enrichment results
        """
        start_time = time.time()
        
        try:
            logger.info("Starting enrichment", episode_id=episode.episode_id)
            
            # Get transcript text
            transcript_text = transcript_data.get('text', '')
            
            # Clean transcript (remove Whisper hallucination/repetitions)
            if transcript_text:
                logger.info("Cleaning transcript", episode_id=episode.episode_id)
                transcript_text_cleaned = clean_transcript(transcript_text)
                logger.info(
                    "Transcript cleaned",
                    original_length=len(transcript_text),
                    cleaned_length=len(transcript_text_cleaned)
                )
            else:
                transcript_text_cleaned = transcript_text
            
            if not transcript_text_cleaned:
                logger.warning(
                    "No transcript text found, using basic enrichment",
                    episode_id=episode.episode_id
                )
                enrichment_data = self._create_basic_enrichment(episode, transcript_data)
            elif self.ollama_client:
                # Use Ollama for AI-powered enrichment
                logger.info(
                    "Using Ollama for AI enrichment",
                    episode_id=episode.episode_id
                )
                enrichment_data = await self._create_ai_enrichment(
                    episode, 
                    transcript_text_cleaned,  # Use cleaned transcript
                    transcript_data,
                    audio_path  # Pass audio path for diarization
                )
            else:
                # Fallback to basic enrichment
                logger.info(
                    "Using basic enrichment (Ollama unavailable)",
                    episode_id=episode.episode_id
                )
                enrichment_data = self._create_basic_enrichment(episode, transcript_data)
            
            # Add processing metadata
            enrichment_data['processing_time'] = time.time() - start_time
            enrichment_data['ai_enhanced'] = self.ollama_client is not None
            
            # Save enrichment data
            enriched_path = self.output_dir / f"{episode.episode_id}.json"
            with open(enriched_path, 'w', encoding='utf-8') as f:
                json.dump(enrichment_data, f, indent=2, ensure_ascii=False)
            
            logger.info(
                "Enrichment completed", 
                episode_id=episode.episode_id,
                path=str(enriched_path),
                size=enriched_path.stat().st_size,
                processing_time=enrichment_data['processing_time'],
                ai_enhanced=enrichment_data['ai_enhanced']
            )
            
            return {
                'enriched_path': str(enriched_path),
                'enrichment_data': enrichment_data,
                'success': True
            }
            
        except Exception as e:
            logger.error(
                "Enrichment failed",
                episode_id=episode.episode_id,
                error=str(e)
            )
            raise ProcessingError(f"Enrichment stage failed: {e}")
    
    async def _create_ai_enrichment(self, 
                                   episode: EpisodeObject, 
                                   transcript_text: str,
                                   transcript_data: Dict[str, Any],
                                   audio_path: str = None) -> Dict[str, Any]:
        """
        Create AI-powered enrichment using Ollama
        
        Args:
            episode: Episode object
            transcript_text: Plain text transcript
            transcript_data: Full transcript data with segments
            audio_path: Path to audio file (for diarization)
            
        Returns:
            Enrichment data dictionary
        """
        # Run complete AI analysis
        analysis = self.ollama_client.analyze_transcript(
            transcript_text,
            episode.episode_id
        )
        
        # Run diarization if enabled and audio path available
        diarization_data = await self._run_diarization(episode, audio_path) if audio_path else None
        
        # Run Intelligence Chain V2 (Phase 2: Entity extraction, disambiguation, proficiency scoring)
        # Skip diarization step since we already ran it above
        intelligence_results = None
        if self.intelligence_chain_enabled and self.intelligence_chain and audio_path:
            intelligence_results = await self._run_intelligence_chain(
                episode, 
                audio_path, 
                transcript_text,
                start_from_step="extract_entities"  # Skip diarization, start from entity extraction
            )
        
        # Build enrichment data structure
        enrichment_data = {
            'episode_id': episode.episode_id,
            'show_name_extracted': analysis.show_name,  # AI-extracted show name
            'host_name_extracted': analysis.host_name,  # AI-extracted host name
            'transcript': {
                'text': transcript_text,
                'segments': transcript_data.get('segments', [])
            },
            'ai_analysis': {
                'executive_summary': analysis.executive_summary,
                'key_takeaways': analysis.key_takeaways,
                'deep_analysis': analysis.deep_analysis,
                'topics': analysis.topics,
                'segment_titles': analysis.segment_titles,
                'show_name': analysis.show_name,  # Include in ai_analysis too
                'host_name': analysis.host_name,  # Include host name
                'analysis_time': analysis.processing_time
            },
            # Diarization results
            'diarization': diarization_data if diarization_data else {
                'speakers': [],
                'segments': [],
                'note': 'Diarization not available' if not self.diarization_enabled else 'Diarization failed'
            },
            'entities': self._build_entities_data(intelligence_results, analysis.topics),
            'enriched_guests': self._build_enriched_guests(intelligence_results),
            'proficiency_scores': self._build_proficiency_scores(intelligence_results),
            'summary': {
                'key_takeaway': analysis.key_takeaways[0] if analysis.key_takeaways else f"Episode {episode.metadata.title}",
                'description': analysis.executive_summary[:200] + '...' if len(analysis.executive_summary) > 200 else analysis.executive_summary,
                'tags': analysis.topics[:8]  # Top 8 topics as tags
            }
        }
        
        return enrichment_data
    
    async def _run_diarization(self, episode: EpisodeObject, audio_path: str) -> Optional[Dict[str, Any]]:
        """
        Run speaker diarization on audio file
        
        Args:
            episode: Episode object
            audio_path: Path to audio file
            
        Returns:
            Diarization data dict or None if failed
        """
        if not self.diarization_enabled:
            logger.info("Diarization disabled or not available", episode_id=episode.episode_id)
            return None
        
        if not audio_path or not Path(audio_path).exists():
            logger.warning("Audio path not found for diarization", episode_id=episode.episode_id, audio_path=audio_path)
            return None
        
        try:
            logger.info(
                "Starting speaker diarization",
                episode_id=episode.episode_id,
                audio_path=audio_path,
                num_speakers=self.num_speakers,
                device=self.diarization_device
            )
            
            # Run diarization
            result = diarize_audio(
                audio_path=audio_path,
                output_path=None,  # Don't save to file, return dict
                hf_token=self.hf_token,
                num_speakers=self.num_speakers if self.num_speakers > 0 else None,
                device=self.diarization_device,
                merge_gap=2.0
            )
            
            # Validate results
            validation = validate_diarization(result['segments'])
            consistency = check_speaker_consistency(result['segments'])
            
            # Add validation data
            result['validation'] = validation
            result['consistency'] = consistency
            
            logger.info(
                "Diarization completed",
                episode_id=episode.episode_id,
                num_segments=len(result['segments']),
                num_speakers=result['num_speakers'],
                quality_score=validation['quality_score'],
                device_used=result['device_used']
            )
            
            # Log quality issues
            if validation['issues']:
                for issue in validation['issues']:
                    logger.warning(f"Diarization quality issue: {issue}", episode_id=episode.episode_id)
            
            if not consistency['consistent']:
                for issue in consistency['issues']:
                    logger.warning(f"Diarization consistency issue: {issue}", episode_id=episode.episode_id)
            
            return result
        
        except Exception as e:
            logger.error(
                "Diarization failed",
                episode_id=episode.episode_id,
                error=str(e)
            )
            # Return None to allow pipeline to continue without diarization
            return None
    
    async def _run_intelligence_chain(self, 
                                     episode: EpisodeObject, 
                                     audio_path: str,
                                     transcript_text: str,
                                     start_from_step: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Run Intelligence Chain V2 for entity extraction, disambiguation, and proficiency scoring
        
        Args:
            episode: Episode object
            audio_path: Path to audio file
            transcript_text: Transcript text
            
        Returns:
            Intelligence chain results or None if failed
        """
        if not self.intelligence_chain_enabled or not self.intelligence_chain:
            logger.info("Intelligence Chain V2 disabled", episode_id=episode.episode_id)
            return None
        
        try:
            logger.info(
                "Starting Intelligence Chain V2 (entity extraction, disambiguation, proficiency scoring)",
                episode_id=episode.episode_id
            )
            
            # Run intelligence chain
            result = await self.intelligence_chain.process_episode(
                episode=episode,
                audio_path=audio_path,
                transcript_text=transcript_text,
                force_rerun=False,
                start_from_step=start_from_step  # Skip diarization if specified
            )
            
            if result.success:
                logger.info(
                    "Intelligence Chain V2 completed successfully",
                    episode_id=episode.episode_id,
                    entities_found=len(result.entities.candidates) if result.entities else 0,
                    people_resolved=len(result.resolution.enriched_people) if result.resolution else 0,
                    people_scored=len(result.proficiency.scored_people) if result.proficiency else 0
                )
                return result
            else:
                import traceback
                logger.error(
                    "Intelligence Chain V2 failed",
                    episode_id=episode.episode_id,
                    error=result.error,
                    success=result.success
                )
                return None
                
        except Exception as e:
            import traceback
            logger.error(
                "Intelligence Chain V2 failed with exception",
                episode_id=episode.episode_id,
                error=str(e),
                traceback=traceback.format_exc()
            )
            # Return None to allow pipeline to continue without intelligence chain
            return None
    
    def _build_entities_data(self, intelligence_results, ai_topics: list) -> Dict[str, Any]:
        """Build entities data from intelligence chain results"""
        if not intelligence_results or not intelligence_results.entities:
            return {
                'people': [],
                'organizations': [],
                'topics': ai_topics,
                'note': 'Intelligence Chain V2 not available or failed'
            }
        
        entities = intelligence_results.entities
        return {
            'people': [
                {
                    'name': candidate.name,
                    'role_guess': candidate.role_guess,
                    'org_guess': candidate.org_guess,
                    'confidence': candidate.confidence,
                    'journalistic_relevance': candidate.journalistic_relevance
                }
                for candidate in entities.candidates
            ],
            'organizations': [],  # Can be extracted from candidates if needed
            'topics': entities.topics or ai_topics,
            'extraction_method': entities.extraction_method,
            'model_used': entities.model_used
        }
    
    def _build_enriched_guests(self, intelligence_results) -> list:
        """Build enriched guests list from intelligence chain results"""
        if not intelligence_results or not intelligence_results.resolution:
            return []
        
        resolution = intelligence_results.resolution
        return [
            {
                'original_name': person.original_name,
                'name': person.name,
                'wikidata_id': person.wikidata_id,
                'description': person.description,
                'job_title': person.job_title,
                'affiliation': person.affiliation,
                'confidence': person.confidence,
                'authority_level': person.authority_level,
                'authority_score': person.authority_score,
                'journalistic_relevance': person.journalistic_relevance,
                'source_credibility': person.source_credibility
            }
            for person in resolution.enriched_people
        ]
    
    def _build_proficiency_scores(self, intelligence_results) -> Dict[str, Any]:
        """Build proficiency scores data from intelligence chain results"""
        if not intelligence_results or not intelligence_results.proficiency:
            return {
                'scored_people': [],
                'note': 'Intelligence Chain V2 not available or failed'
            }
        
        proficiency = intelligence_results.proficiency
        return {
            'scored_people': [
                {
                    'original_name': person.original_name,
                    'name': person.name,
                    'wikidata_id': person.wikidata_id,
                    'job_title': person.criteria_scores.get('job_title', ''),
                    'affiliation': person.criteria_scores.get('affiliation', ''),
                    'proficiencyScore': person.proficiencyScore,
                    'credibilityBadge': person.credibilityBadge,
                    'verificationBadge': person.verificationBadge,
                    'scoreBreakdown': {
                        'roleMatch': person.scoreBreakdown.roleMatch,
                        'authorityDomain': person.scoreBreakdown.authorityDomain,
                        'knowledgeBase': person.scoreBreakdown.knowledgeBase,
                        'publications': person.scoreBreakdown.publications,
                        'recency': person.scoreBreakdown.recency,
                        'journalisticRelevance': person.scoreBreakdown.journalisticRelevance,
                        'authorityVerification': person.scoreBreakdown.authorityVerification,
                        'ambiguityPenalty': person.scoreBreakdown.ambiguityPenalty
                    },
                    'reasoning': person.reasoning,
                    'editorialDecision': person.editorialDecision,
                    'authorityLevel': person.authorityLevel,
                    'journalisticRelevance': person.journalisticRelevance
                }
                for person in proficiency.scored_people
            ],
            'summary': proficiency.summary
        }
    
    def _create_basic_enrichment(self, 
                                episode: EpisodeObject,
                                transcript_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create basic enrichment without AI (fallback)
        
        Args:
            episode: Episode object
            transcript_data: Transcript data
            
        Returns:
            Basic enrichment data dictionary
        """
        enrichment_data = {
            'episode_id': episode.episode_id,
            'transcript': {
                'text': transcript_data.get('text', ''),
                'segments': transcript_data.get('segments', [])
            },
            'ai_analysis': {
                'executive_summary': '',
                'key_takeaways': [],
                'deep_analysis': '',
                'topics': [],
                'segment_titles': [],
                'analysis_time': 0.0
            },
            'diarization': {
                'speakers': [],
                'note': 'Diarization not yet implemented'
            },
            'entities': {
                'people': [],
                'organizations': [],
                'topics': [],
                'note': 'Entity extraction not yet implemented'
            },
            'enriched_guests': [],
            'summary': {
                'key_takeaway': f"Episode {episode.metadata.title}",
                'description': episode.metadata.description or '',
                'tags': []
            }
        }
        
        return enrichment_data
