"""
Enrichment Stage Processor

Uses Ollama AI to generate:
1. Executive summary (2-3 paragraphs)
2. Key takeaways (5-7 items)
3. Deep analysis (themes, implications, impact)
4. Topics/Keywords (8-10 tags)
5. Segment titles (for transcript chunks)

Falls back to basic intelligence chain if Ollama is unavailable.

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
                 ollama_enabled: bool = True):
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
                    transcript_data
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
                                   transcript_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create AI-powered enrichment using Ollama
        
        Args:
            episode: Episode object
            transcript_text: Plain text transcript
            transcript_data: Full transcript data with segments
            
        Returns:
            Enrichment data dictionary
        """
        # Run complete AI analysis
        analysis = self.ollama_client.analyze_transcript(
            transcript_text,
            episode.episode_id
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
            # Placeholder for future intelligence chain integration
            'diarization': {
                'speakers': [],
                'note': 'Diarization will be integrated in Phase 2'
            },
            'entities': {
                'people': [],
                'organizations': [],
                'topics': analysis.topics,  # Use AI-extracted topics
                'note': 'Full entity extraction will be integrated in Phase 2'
            },
            'enriched_guests': [],
            'summary': {
                'key_takeaway': analysis.key_takeaways[0] if analysis.key_takeaways else f"Episode {episode.metadata.title}",
                'description': analysis.executive_summary[:200] + '...' if len(analysis.executive_summary) > 200 else analysis.executive_summary,
                'tags': analysis.topics[:8]  # Top 8 topics as tags
            }
        }
        
        return enrichment_data
    
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
