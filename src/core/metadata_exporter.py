"""
Metadata Exporter for Web Publishing Workflows

Generates complete episode metadata exports with all enrichment data,
guest profile exports with proficiency scores and reasoning, diarized
transcript exports with speaker attribution, and organized folder
structures for web publishing workflows.
"""

import json
import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, TextIO
from dataclasses import dataclass, asdict

from .config import PipelineConfig
from .logging import get_logger
from .models import EpisodeObject, EditorialContent, EnrichmentResult, TranscriptionResult


@dataclass
class ExportConfig:
    """Configuration for metadata export"""
    output_dir: Path
    include_transcripts: bool = True
    include_enrichment: bool = True
    include_editorial: bool = True
    format_json: bool = True
    format_csv: bool = False
    create_folders: bool = True
    pretty_print: bool = True


class MetadataExporter:
    """
    Exports episode metadata in various formats for web publishing workflows.
    
    Generates complete episode metadata exports with all enrichment data,
    guest profile exports with proficiency scores and reasoning, and
    diarized transcript exports with speaker attribution.
    """
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.logger = get_logger(__name__)
    
    def export_episode_metadata(self, episode: EpisodeObject, 
                              export_config: ExportConfig) -> Dict[str, Path]:
        """
        Export complete episode metadata with all enrichment data.
        
        Args:
            episode: The episode object to export
            export_config: Export configuration settings
            
        Returns:
            Dictionary mapping export type to file path
        """
        self.logger.info(f"Exporting metadata for episode: {episode.episode_id}")
        
        # Create folder structure if requested
        episode_dir = None
        if export_config.create_folders:
            episode_dir = self._create_episode_folder(episode, export_config.output_dir)
        else:
            episode_dir = export_config.output_dir
        
        exported_files = {}
        
        # Generate complete metadata
        metadata = self._generate_complete_metadata(episode, export_config)
        
        # Export in requested formats
        if export_config.format_json:
            json_path = self._export_json_metadata(metadata, episode_dir, 
                                                 episode.episode_id, export_config.pretty_print)
            exported_files['metadata_json'] = json_path
        
        if export_config.format_csv:
            csv_path = self._export_csv_metadata(metadata, episode_dir, episode.episode_id)
            exported_files['metadata_csv'] = csv_path
        
        # Export guest profiles if enrichment data exists
        if episode.enrichment and export_config.include_enrichment:
            guest_profiles_path = self._export_guest_profiles(episode, episode_dir, export_config)
            if guest_profiles_path:
                exported_files['guest_profiles'] = guest_profiles_path
        
        # Export diarized transcript if available
        if (episode.transcription and episode.enrichment and 
            export_config.include_transcripts):
            transcript_path = self._export_diarized_transcript(episode, episode_dir, export_config)
            if transcript_path:
                exported_files['diarized_transcript'] = transcript_path
        
        self.logger.info(f"Exported {len(exported_files)} files for episode: {episode.episode_id}")
        return exported_files
    
    def export_batch_metadata(self, episodes: List[EpisodeObject], 
                            export_config: ExportConfig) -> Dict[str, Any]:
        """
        Export metadata for multiple episodes in batch.
        
        Args:
            episodes: List of episode objects to export
            export_config: Export configuration settings
            
        Returns:
            Summary of batch export results
        """
        self.logger.info(f"Starting batch export for {len(episodes)} episodes")
        
        results = {
            'total_episodes': len(episodes),
            'successful_exports': 0,
            'failed_exports': 0,
            'exported_files': {},
            'errors': []
        }
        
        for episode in episodes:
            try:
                exported_files = self.export_episode_metadata(episode, export_config)
                results['exported_files'][episode.episode_id] = exported_files
                results['successful_exports'] += 1
            except Exception as e:
                self.logger.error(f"Failed to export episode {episode.episode_id}: {str(e)}")
                results['errors'].append({
                    'episode_id': episode.episode_id,
                    'error': str(e)
                })
                results['failed_exports'] += 1
        
        # Generate batch summary
        if export_config.format_json:
            summary_path = self._export_batch_summary(results, export_config.output_dir)
            results['summary_file'] = summary_path
        
        self.logger.info(f"Batch export completed: {results['successful_exports']} successful, "
                        f"{results['failed_exports']} failed")
        
        return results
    
    def _create_episode_folder(self, episode: EpisodeObject, base_dir: Path) -> Path:
        """Create organized folder structure for episode files"""
        # Create folder structure: show/season/episode_id/
        show_slug = episode.metadata.show_slug
        season = episode.metadata.season or "unknown"
        
        episode_dir = base_dir / show_slug / f"season_{season}" / episode.episode_id
        episode_dir.mkdir(parents=True, exist_ok=True)
        
        return episode_dir
    
    def _generate_complete_metadata(self, episode: EpisodeObject, 
                                  export_config: ExportConfig) -> Dict[str, Any]:
        """Generate complete metadata dictionary for export"""
        metadata = {
            'episode_id': episode.episode_id,
            'content_hash': episode.content_hash,
            'processing_stage': episode.processing_stage.value,
            'created_at': episode.created_at.isoformat() if episode.created_at else None,
            'updated_at': episode.updated_at.isoformat() if episode.updated_at else None,
            'source': episode.source.to_dict(),
            'media': episode.media.to_dict(),
            'metadata': episode.metadata.to_dict()
        }
        
        # Add transcription data if requested and available
        if export_config.include_transcripts and episode.transcription:
            metadata['transcription'] = episode.transcription.to_dict()
        
        # Add enrichment data if requested and available
        if export_config.include_enrichment and episode.enrichment:
            metadata['enrichment'] = episode.enrichment.to_dict()
        
        # Add editorial content if requested and available
        if export_config.include_editorial and episode.editorial:
            metadata['editorial'] = episode.editorial.to_dict()
        
        # Add errors if present
        if episode.errors:
            metadata['errors'] = episode.errors
        
        return metadata
    
    def _export_json_metadata(self, metadata: Dict[str, Any], output_dir: Path, 
                            episode_id: str, pretty_print: bool = True) -> Path:
        """Export metadata as JSON file"""
        filename = f"{episode_id}_metadata.json"
        file_path = output_dir / filename
        
        with open(file_path, 'w', encoding='utf-8') as f:
            if pretty_print:
                json.dump(metadata, f, indent=2, ensure_ascii=False, default=str)
            else:
                json.dump(metadata, f, ensure_ascii=False, default=str)
        
        return file_path
    
    def _export_csv_metadata(self, metadata: Dict[str, Any], output_dir: Path, 
                           episode_id: str) -> Path:
        """Export flattened metadata as CSV file"""
        filename = f"{episode_id}_metadata.csv"
        file_path = output_dir / filename
        
        # Flatten nested metadata for CSV export
        flattened = self._flatten_dict(metadata)
        
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            if flattened:
                writer = csv.DictWriter(f, fieldnames=flattened.keys())
                writer.writeheader()
                writer.writerow(flattened)
        
        return file_path
    
    def _export_guest_profiles(self, episode: EpisodeObject, output_dir: Path, 
                             export_config: ExportConfig) -> Optional[Path]:
        """Export guest profile data with proficiency scores and reasoning"""
        if not episode.enrichment or not episode.enrichment.proficiency_scores:
            return None
        
        filename = f"{episode.episode_id}_guest_profiles.json"
        file_path = output_dir / filename
        
        # Extract guest profile data
        guest_profiles = []
        
        # Get proficiency scores data
        proficiency_data = episode.enrichment.proficiency_scores
        if isinstance(proficiency_data, dict) and 'people' in proficiency_data:
            for person_data in proficiency_data['people']:
                profile = {
                    'name': person_data.get('name', ''),
                    'job_title': person_data.get('job_title', ''),
                    'affiliation': person_data.get('affiliation', {}),
                    'proficiency_score': person_data.get('proficiency_score', 0.0),
                    'credibility_badge': person_data.get('credibility_badge', ''),
                    'confidence': person_data.get('confidence', 0.0),
                    'reasoning': person_data.get('reasoning', ''),
                    'same_as': person_data.get('same_as', []),
                    'biographical_data': person_data.get('biographical_data', {}),
                    'verification_sources': person_data.get('verification_sources', [])
                }
                guest_profiles.append(profile)
        
        # Add disambiguation data if available
        if episode.enrichment.disambiguation:
            disambiguation_data = episode.enrichment.disambiguation
            if isinstance(disambiguation_data, dict) and 'people' in disambiguation_data:
                # Merge disambiguation data with profiles
                for i, person in enumerate(disambiguation_data['people']):
                    if i < len(guest_profiles):
                        guest_profiles[i].update({
                            'wikidata_id': person.get('wikidata_id', ''),
                            'wikipedia_url': person.get('wikipedia_url', ''),
                            'official_sources': person.get('official_sources', [])
                        })
        
        export_data = {
            'episode_id': episode.episode_id,
            'export_timestamp': datetime.now().isoformat(),
            'guest_count': len(guest_profiles),
            'guests': guest_profiles
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            if export_config.pretty_print:
                json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)
            else:
                json.dump(export_data, f, ensure_ascii=False, default=str)
        
        return file_path
    
    def _export_diarized_transcript(self, episode: EpisodeObject, output_dir: Path, 
                                  export_config: ExportConfig) -> Optional[Path]:
        """Export diarized transcript with speaker attribution"""
        if not episode.transcription or not episode.enrichment:
            return None
        
        filename = f"{episode.episode_id}_diarized_transcript.json"
        file_path = output_dir / filename
        
        # Combine transcription and diarization data
        transcript_data = {
            'episode_id': episode.episode_id,
            'export_timestamp': datetime.now().isoformat(),
            'transcription_model': episode.transcription.model_used,
            'language': episode.transcription.language,
            'confidence': episode.transcription.confidence,
            'segments': []
        }
        
        # Get diarization data
        diarization_data = episode.enrichment.diarization if episode.enrichment.diarization else {}
        speaker_segments = diarization_data.get('segments', []) if isinstance(diarization_data, dict) else []
        
        # Get transcription segments
        transcription_segments = episode.transcription.segments or []
        
        # Merge transcription and diarization data
        for i, segment in enumerate(transcription_segments):
            segment_data = {
                'id': i,
                'start': segment.get('start', 0.0),
                'end': segment.get('end', 0.0),
                'text': segment.get('text', ''),
                'confidence': segment.get('confidence', 0.0),
                'speaker': 'Unknown'
            }
            
            # Find matching speaker from diarization
            segment_start = segment.get('start', 0.0)
            for speaker_seg in speaker_segments:
                if (speaker_seg.get('start', 0.0) <= segment_start <= 
                    speaker_seg.get('end', float('inf'))):
                    segment_data['speaker'] = speaker_seg.get('speaker', 'Unknown')
                    break
            
            transcript_data['segments'].append(segment_data)
        
        # Add speaker summary
        speakers = set(seg['speaker'] for seg in transcript_data['segments'])
        transcript_data['speaker_count'] = len(speakers)
        transcript_data['speakers'] = list(speakers)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            if export_config.pretty_print:
                json.dump(transcript_data, f, indent=2, ensure_ascii=False, default=str)
            else:
                json.dump(transcript_data, f, ensure_ascii=False, default=str)
        
        return file_path
    
    def _export_batch_summary(self, results: Dict[str, Any], output_dir: Path) -> Path:
        """Export batch processing summary"""
        filename = f"batch_export_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        file_path = output_dir / filename
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        
        return file_path
    
    def _flatten_dict(self, d: Dict[str, Any], parent_key: str = '', sep: str = '.') -> Dict[str, Any]:
        """Flatten nested dictionary for CSV export"""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            elif isinstance(v, list):
                # Convert lists to comma-separated strings
                items.append((new_key, ', '.join(str(item) for item in v)))
            else:
                items.append((new_key, v))
        return dict(items)
    
    def create_web_publishing_structure(self, episodes: List[EpisodeObject], 
                                      base_output_dir: Path) -> Dict[str, Path]:
        """
        Create organized folder structure optimized for web publishing workflows.
        
        Creates a hierarchical structure:
        - shows/
          - {show_slug}/
            - seasons/
              - season_{n}/
                - episodes/
                  - {episode_id}/
                    - metadata.json
                    - guest_profiles.json
                    - diarized_transcript.json
            - index.json (show metadata)
        - hosts/
          - {host_slug}/
            - appearances.json
        - global_index.json
        
        Args:
            episodes: List of episodes to organize
            base_output_dir: Base directory for web publishing structure
            
        Returns:
            Dictionary mapping structure type to created paths
        """
        self.logger.info(f"Creating web publishing structure for {len(episodes)} episodes")
        
        created_paths = {}
        
        # Create base directories
        shows_dir = base_output_dir / "shows"
        hosts_dir = base_output_dir / "hosts"
        shows_dir.mkdir(parents=True, exist_ok=True)
        hosts_dir.mkdir(parents=True, exist_ok=True)
        
        # Group episodes by show
        shows_data = {}
        hosts_data = {}
        
        for episode in episodes:
            show_slug = episode.metadata.show_slug
            season = episode.metadata.season or 0
            
            # Initialize show data
            if show_slug not in shows_data:
                shows_data[show_slug] = {
                    'show_name': episode.metadata.show_name,
                    'show_slug': show_slug,
                    'seasons': {},
                    'total_episodes': 0
                }
            
            # Initialize season data
            if season not in shows_data[show_slug]['seasons']:
                shows_data[show_slug]['seasons'][season] = {
                    'season_number': season,
                    'episodes': [],
                    'episode_count': 0
                }
            
            # Add episode to season
            episode_summary = {
                'episode_id': episode.episode_id,
                'title': episode.metadata.title or episode.metadata.topic,
                'date': episode.metadata.date,
                'description': episode.editorial.summary if episode.editorial else None,
                'topic_tags': episode.editorial.topic_tags if episode.editorial else [],
                'processing_stage': episode.processing_stage.value,
                'has_transcription': episode.transcription is not None,
                'has_enrichment': episode.enrichment is not None
            }
            
            shows_data[show_slug]['seasons'][season]['episodes'].append(episode_summary)
            shows_data[show_slug]['seasons'][season]['episode_count'] += 1
            shows_data[show_slug]['total_episodes'] += 1
            
            # Extract host information from enrichment data
            if episode.enrichment and episode.enrichment.proficiency_scores:
                proficiency_data = episode.enrichment.proficiency_scores
                if isinstance(proficiency_data, dict) and 'people' in proficiency_data:
                    for person in proficiency_data['people']:
                        host_name = person.get('name', '')
                        if host_name:
                            host_slug = self._create_slug(host_name)
                            
                            if host_slug not in hosts_data:
                                hosts_data[host_slug] = {
                                    'name': host_name,
                                    'slug': host_slug,
                                    'appearances': [],
                                    'total_appearances': 0,
                                    'shows': set()
                                }
                            
                            appearance = {
                                'episode_id': episode.episode_id,
                                'show_name': episode.metadata.show_name,
                                'show_slug': show_slug,
                                'date': episode.metadata.date,
                                'title': episode.metadata.title or episode.metadata.topic,
                                'role': person.get('job_title', ''),
                                'credibility_badge': person.get('credibility_badge', ''),
                                'proficiency_score': person.get('proficiency_score', 0.0)
                            }
                            
                            hosts_data[host_slug]['appearances'].append(appearance)
                            hosts_data[host_slug]['total_appearances'] += 1
                            hosts_data[host_slug]['shows'].add(show_slug)
        
        # Create show directories and index files
        for show_slug, show_data in shows_data.items():
            show_dir = shows_dir / show_slug
            show_dir.mkdir(exist_ok=True)
            
            # Create seasons directory
            seasons_dir = show_dir / "seasons"
            seasons_dir.mkdir(exist_ok=True)
            
            # Create season directories and episode files
            for season_num, season_data in show_data['seasons'].items():
                season_dir = seasons_dir / f"season_{season_num}"
                episodes_dir = season_dir / "episodes"
                episodes_dir.mkdir(parents=True, exist_ok=True)
                
                # Create season index
                season_index_path = season_dir / "index.json"
                with open(season_index_path, 'w', encoding='utf-8') as f:
                    json.dump(season_data, f, indent=2, ensure_ascii=False, default=str)
            
            # Create show index
            # Convert sets to lists for JSON serialization
            show_index_data = {
                'show_name': show_data['show_name'],
                'show_slug': show_data['show_slug'],
                'total_episodes': show_data['total_episodes'],
                'seasons': {str(k): v for k, v in show_data['seasons'].items()}
            }
            
            show_index_path = show_dir / "index.json"
            with open(show_index_path, 'w', encoding='utf-8') as f:
                json.dump(show_index_data, f, indent=2, ensure_ascii=False, default=str)
            
            created_paths[f"show_{show_slug}"] = show_dir
        
        # Create host directories and files
        for host_slug, host_data in hosts_data.items():
            host_dir = hosts_dir / host_slug
            host_dir.mkdir(exist_ok=True)
            
            # Convert sets to lists for JSON serialization
            host_index_data = {
                'name': host_data['name'],
                'slug': host_data['slug'],
                'total_appearances': host_data['total_appearances'],
                'shows': list(host_data['shows']),
                'appearances': host_data['appearances']
            }
            
            host_index_path = host_dir / "appearances.json"
            with open(host_index_path, 'w', encoding='utf-8') as f:
                json.dump(host_index_data, f, indent=2, ensure_ascii=False, default=str)
            
            created_paths[f"host_{host_slug}"] = host_dir
        
        # Create global index
        global_index = {
            'created_at': datetime.now().isoformat(),
            'total_episodes': len(episodes),
            'total_shows': len(shows_data),
            'total_hosts': len(hosts_data),
            'shows': list(shows_data.keys()),
            'hosts': list(hosts_data.keys())
        }
        
        global_index_path = base_output_dir / "global_index.json"
        with open(global_index_path, 'w', encoding='utf-8') as f:
            json.dump(global_index, f, indent=2, ensure_ascii=False, default=str)
        
        created_paths['global_index'] = global_index_path
        created_paths['shows_dir'] = shows_dir
        created_paths['hosts_dir'] = hosts_dir
        
        self.logger.info(f"Created web publishing structure with {len(created_paths)} components")
        return created_paths
    
    def _create_slug(self, text: str) -> str:
        """Create URL-friendly slug from text"""
        import re
        
        # Convert to lowercase and replace spaces/special chars with hyphens
        slug = re.sub(r'[^\w\s-]', '', text.lower())
        slug = re.sub(r'[-\s]+', '-', slug)
        slug = slug.strip('-')
        
        return slug or 'unknown'