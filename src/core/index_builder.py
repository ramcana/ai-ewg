"""
Index Builder for the Video Processing Pipeline

Generates navigation and search indices for TV/journalistic content with
engaging episode listings, professional biographical context, and cross-references
between shows and hosts.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

from .config import PipelineConfig
from .logging import get_logger
from .models import EpisodeObject, ProcessingStage
from .exceptions import ProcessingError

logger = get_logger('pipeline.index_builder')


@dataclass
class ShowIndex:
    """Index data for a show"""
    show_slug: str
    show_name: str
    total_episodes: int
    seasons: Dict[int, int]  # season -> episode count
    episodes: List[Dict[str, Any]]
    hosts: List[Dict[str, Any]]
    topics: List[str]
    last_updated: datetime
    description: Optional[str] = None


@dataclass
class HostIndex:
    """Index data for a host/guest"""
    host_slug: str
    name: str
    total_appearances: int
    shows: List[Dict[str, Any]]
    episodes: List[Dict[str, Any]]
    topics: List[str]
    credentials: Dict[str, Any]
    last_updated: datetime
    biography: Optional[str] = None


@dataclass
class GlobalIndex:
    """Master index for all content"""
    total_episodes: int
    total_shows: int
    total_hosts: int
    shows: List[Dict[str, Any]]
    featured_hosts: List[Dict[str, Any]]
    recent_episodes: List[Dict[str, Any]]
    popular_topics: List[Dict[str, Any]]
    last_updated: datetime


@dataclass
class IndexBuildResult:
    """Result of index building operation"""
    show_indices_updated: List[str]
    host_indices_updated: List[str]
    global_index_updated: bool
    total_episodes_processed: int
    build_time: float
    validation_results: Dict[str, Any]


class IndexBuilder:
    """
    Index builder for navigation and search functionality
    
    Creates per-show and per-host indices with engaging episode listings,
    professional biographical context, and cross-reference generation
    between shows and hosts.
    """
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.logger = logger
        
        # Output configuration
        self.output_base = Path(self._get_config_value('output', {}).get('indices', 'output/indices'))
        self.web_base = Path(self._get_config_value('output', {}).get('web_artifacts', 'output/web'))
        
        # Index configuration
        self.max_recent_episodes = 10
        self.max_featured_hosts = 20
        self.max_popular_topics = 15
        self.min_host_appearances = 2
        
        # Ensure output directories exist
        self.output_base.mkdir(parents=True, exist_ok=True)
        (self.output_base / 'shows').mkdir(exist_ok=True)
        (self.output_base / 'hosts').mkdir(exist_ok=True)
    
    def _get_config_value(self, key: str, default: Any = None) -> Any:
        """Get configuration value, handling both dict and dataclass config"""
        if hasattr(self.config, 'get'):
            return self.config.get(key, default)
        elif hasattr(self.config, key):
            return getattr(self.config, key)
        else:
            return default
    
    def build_all_indices(self, episodes: List[EpisodeObject]) -> IndexBuildResult:
        """
        Build all indices from episode list
        
        Args:
            episodes: List of processed episodes
            
        Returns:
            IndexBuildResult: Results of index building operation
            
        Raises:
            ProcessingError: If index building fails
        """
        start_time = datetime.now()
        
        self.logger.info(
            "Building all indices",
            total_episodes=len(episodes)
        )
        
        try:
            # Filter to rendered episodes only
            rendered_episodes = [
                ep for ep in episodes 
                if ep.processing_stage == ProcessingStage.RENDERED
            ]
            
            self.logger.info(
                "Processing rendered episodes for indices",
                rendered_episodes=len(rendered_episodes),
                total_episodes=len(episodes)
            )
            
            # Build show indices
            show_indices = self._build_show_indices(rendered_episodes)
            
            # Build host indices
            host_indices = self._build_host_indices(rendered_episodes)
            
            # Build global index
            global_index = self._build_global_index(rendered_episodes, show_indices, host_indices)
            
            # Write indices to files
            show_files = self._write_show_indices(show_indices)
            host_files = self._write_host_indices(host_indices)
            global_file = self._write_global_index(global_index)
            
            # Validate indices
            validation_results = self._validate_indices(show_indices, host_indices, global_index)
            
            # Calculate build time
            build_time = (datetime.now() - start_time).total_seconds()
            
            result = IndexBuildResult(
                show_indices_updated=list(show_files.keys()),
                host_indices_updated=list(host_files.keys()),
                global_index_updated=bool(global_file),
                total_episodes_processed=len(rendered_episodes),
                build_time=build_time,
                validation_results=validation_results
            )
            
            self.logger.info(
                "All indices built successfully",
                shows_updated=len(show_files),
                hosts_updated=len(host_files),
                episodes_processed=len(rendered_episodes),
                build_time=build_time
            )
            
            return result
        
        except Exception as e:
            error_msg = f"Failed to build indices: {str(e)}"
            self.logger.error(error_msg, exception=e)
            raise ProcessingError(error_msg, stage="index_building")
    
    def update_indices_for_episode(self, episode: EpisodeObject, 
                                 all_episodes: List[EpisodeObject]) -> IndexBuildResult:
        """
        Update indices for a single new episode
        
        Args:
            episode: New episode to add to indices
            all_episodes: Complete list of all episodes
            
        Returns:
            IndexBuildResult: Results of index update operation
        """
        self.logger.info(
            "Updating indices for new episode",
            episode_id=episode.episode_id
        )
        
        try:
            # Rebuild all indices (for simplicity and consistency)
            # In a production system, this could be optimized for incremental updates
            return self.build_all_indices(all_episodes)
        
        except Exception as e:
            error_msg = f"Failed to update indices for episode {episode.episode_id}: {str(e)}"
            self.logger.error(error_msg, episode_id=episode.episode_id, exception=e)
            raise ProcessingError(error_msg, stage="index_update")
    
    def build_show_index(self, show_slug: str, episodes: List[EpisodeObject]) -> ShowIndex:
        """
        Build index for a specific show with engaging episode listings
        
        Args:
            show_slug: Show identifier
            episodes: Episodes for this show
            
        Returns:
            ShowIndex: Generated show index
        """
        try:
            if not episodes:
                raise ProcessingError(f"No episodes found for show: {show_slug}")
            
            # Get show metadata from first episode
            first_episode = episodes[0]
            show_name = first_episode.metadata.show_name or show_slug.replace('-', ' ').title()
            
            # Organize episodes by season
            seasons = defaultdict(int)
            episode_list = []
            
            for episode in episodes:
                # Count episodes per season
                season = episode.metadata.season or 1
                seasons[season] += 1
                
                # Create episode entry
                episode_entry = self._create_episode_entry(episode)
                episode_list.append(episode_entry)
            
            # Sort episodes by date (newest first) and season/episode
            episode_list.sort(key=lambda x: (
                x.get('date', ''),
                x.get('season', 0),
                x.get('episode', 0)
            ), reverse=True)
            
            # Extract hosts from episodes
            hosts = self._extract_show_hosts(episodes)
            
            # Extract topics from episodes
            topics = self._extract_show_topics(episodes)
            
            # Generate show description
            description = self._generate_show_description(show_name, episodes, hosts, topics)
            
            show_index = ShowIndex(
                show_slug=show_slug,
                show_name=show_name,
                total_episodes=len(episodes),
                seasons=dict(seasons),
                episodes=episode_list,
                hosts=hosts,
                topics=topics,
                last_updated=datetime.now(),
                description=description
            )
            
            self.logger.debug(
                "Show index built",
                show_slug=show_slug,
                total_episodes=len(episodes),
                seasons=len(seasons),
                hosts=len(hosts)
            )
            
            return show_index
        
        except Exception as e:
            error_msg = f"Failed to build show index for {show_slug}: {str(e)}"
            self.logger.error(error_msg, show_slug=show_slug, exception=e)
            raise ProcessingError(error_msg, stage="show_index_building")
    
    def build_host_index(self, host_slug: str, appearances: List[Tuple[EpisodeObject, Dict[str, Any]]]) -> HostIndex:
        """
        Build index for a host with professional biographical context
        
        Args:
            host_slug: Host identifier
            appearances: List of (episode, guest_data) tuples
            
        Returns:
            HostIndex: Generated host index
        """
        try:
            if not appearances:
                raise ProcessingError(f"No appearances found for host: {host_slug}")
            
            # Get host metadata from first appearance
            first_episode, first_guest_data = appearances[0]
            host_name = first_guest_data.get('name', host_slug.replace('-', ' ').title())
            
            # Organize appearances by show
            shows = defaultdict(list)
            episode_list = []
            
            for episode, guest_data in appearances:
                show_slug = episode.metadata.show_slug
                shows[show_slug].append({
                    'episode_id': episode.episode_id,
                    'title': self._get_episode_title(episode),
                    'date': episode.metadata.date,
                    'role': guest_data.get('job_title', 'Guest')
                })
                
                # Create episode entry for host
                episode_entry = self._create_host_episode_entry(episode, guest_data)
                episode_list.append(episode_entry)
            
            # Sort episodes by date (newest first)
            episode_list.sort(key=lambda x: x.get('date', ''), reverse=True)
            
            # Create show summary list
            show_list = []
            for show_slug, show_episodes in shows.items():
                show_name = show_episodes[0].get('show_name', show_slug.replace('-', ' ').title())
                show_list.append({
                    'show_slug': show_slug,
                    'show_name': show_name,
                    'appearances': len(show_episodes),
                    'latest_date': max(ep.get('date', '') for ep in show_episodes if ep.get('date'))
                })
            
            # Sort shows by latest appearance
            show_list.sort(key=lambda x: x.get('latest_date', ''), reverse=True)
            
            # Extract topics from appearances
            topics = self._extract_host_topics(appearances)
            
            # Aggregate credentials from all appearances
            credentials = self._aggregate_host_credentials(appearances)
            
            # Generate biography
            biography = self._generate_host_biography(host_name, credentials, show_list, topics)
            
            host_index = HostIndex(
                host_slug=host_slug,
                name=host_name,
                total_appearances=len(appearances),
                shows=show_list,
                episodes=episode_list,
                topics=topics,
                credentials=credentials,
                last_updated=datetime.now(),
                biography=biography
            )
            
            self.logger.debug(
                "Host index built",
                host_slug=host_slug,
                total_appearances=len(appearances),
                shows=len(show_list)
            )
            
            return host_index
        
        except Exception as e:
            error_msg = f"Failed to build host index for {host_slug}: {str(e)}"
            self.logger.error(error_msg, host_slug=host_slug, exception=e)
            raise ProcessingError(error_msg, stage="host_index_building")
    
    # Private helper methods
    
    def _build_show_indices(self, episodes: List[EpisodeObject]) -> Dict[str, ShowIndex]:
        """Build indices for all shows"""
        show_episodes = defaultdict(list)
        
        # Group episodes by show
        for episode in episodes:
            show_slug = episode.metadata.show_slug
            show_episodes[show_slug].append(episode)
        
        # Build index for each show
        show_indices = {}
        for show_slug, episodes_list in show_episodes.items():
            show_index = self.build_show_index(show_slug, episodes_list)
            show_indices[show_slug] = show_index
        
        return show_indices
    
    def _build_host_indices(self, episodes: List[EpisodeObject]) -> Dict[str, HostIndex]:
        """Build indices for all hosts"""
        host_appearances = defaultdict(list)
        
        # Extract host appearances from episodes
        for episode in episodes:
            if episode.enrichment and episode.enrichment.proficiency_scores:
                scores_data = episode.enrichment.proficiency_scores
                if 'scored_people' in scores_data:
                    for person in scores_data['scored_people']:
                        name = person.get('name', '')
                        if name:
                            host_slug = self._create_host_slug(name)
                            host_appearances[host_slug].append((episode, person))
        
        # Build index for hosts with minimum appearances
        host_indices = {}
        for host_slug, appearances in host_appearances.items():
            if len(appearances) >= self.min_host_appearances:
                host_index = self.build_host_index(host_slug, appearances)
                host_indices[host_slug] = host_index
        
        return host_indices
    
    def _build_global_index(self, episodes: List[EpisodeObject], 
                          show_indices: Dict[str, ShowIndex],
                          host_indices: Dict[str, HostIndex]) -> GlobalIndex:
        """Build master global index"""
        # Recent episodes (last 10)
        recent_episodes = sorted(
            episodes, 
            key=lambda x: x.metadata.date or '', 
            reverse=True
        )[:self.max_recent_episodes]
        
        recent_episode_list = [
            self._create_episode_entry(episode) 
            for episode in recent_episodes
        ]
        
        # Show summary list
        show_list = []
        for show_slug, show_index in show_indices.items():
            show_list.append({
                'show_slug': show_slug,
                'show_name': show_index.show_name,
                'total_episodes': show_index.total_episodes,
                'latest_episode': show_index.episodes[0] if show_index.episodes else None,
                'description': show_index.description
            })
        
        # Sort shows by latest episode date
        show_list.sort(key=lambda x: x.get('latest_episode', {}).get('date', ''), reverse=True)
        
        # Featured hosts (top by appearances)
        featured_hosts = []
        for host_slug, host_index in host_indices.items():
            featured_hosts.append({
                'host_slug': host_slug,
                'name': host_index.name,
                'total_appearances': host_index.total_appearances,
                'credentials': host_index.credentials,
                'biography': host_index.biography
            })
        
        # Sort by appearances and limit
        featured_hosts.sort(key=lambda x: x['total_appearances'], reverse=True)
        featured_hosts = featured_hosts[:self.max_featured_hosts]
        
        # Popular topics (aggregated from all episodes)
        topic_counts = defaultdict(int)
        for episode in episodes:
            if episode.editorial and episode.editorial.topic_tags:
                for topic in episode.editorial.topic_tags:
                    topic_counts[topic] += 1
        
        popular_topics = [
            {'topic': topic, 'count': count}
            for topic, count in sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)
        ][:self.max_popular_topics]
        
        return GlobalIndex(
            total_episodes=len(episodes),
            total_shows=len(show_indices),
            total_hosts=len(host_indices),
            shows=show_list,
            featured_hosts=featured_hosts,
            recent_episodes=recent_episode_list,
            popular_topics=popular_topics,
            last_updated=datetime.now()
        )
    
    def _create_episode_entry(self, episode: EpisodeObject) -> Dict[str, Any]:
        """Create episode entry for indices"""
        entry = {
            'episode_id': episode.episode_id,
            'title': self._get_episode_title(episode),
            'date': episode.metadata.date,
            'season': episode.metadata.season,
            'episode': episode.metadata.episode,
            'show_name': episode.metadata.show_name,
            'show_slug': episode.metadata.show_slug
        }
        
        # Add editorial content if available
        if episode.editorial:
            if episode.editorial.key_takeaway:
                entry['key_takeaway'] = episode.editorial.key_takeaway
            if episode.editorial.summary:
                entry['summary'] = episode.editorial.summary
            if episode.editorial.topic_tags:
                entry['topics'] = episode.editorial.topic_tags
        
        # Add guest information
        if episode.enrichment and episode.enrichment.proficiency_scores:
            scores_data = episode.enrichment.proficiency_scores
            if 'scored_people' in scores_data:
                guests = []
                for person in scores_data['scored_people'][:3]:  # Top 3 guests
                    guest = {
                        'name': person.get('name', ''),
                        'title': person.get('job_title', ''),
                        'badge': person.get('credibilityBadge', 'Guest')
                    }
                    if guest['name']:
                        guests.append(guest)
                entry['guests'] = guests
        
        # Add media info
        if episode.media.duration_seconds:
            entry['duration'] = int(episode.media.duration_seconds)
        
        return entry
    
    def _create_host_episode_entry(self, episode: EpisodeObject, guest_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create episode entry for host index"""
        entry = self._create_episode_entry(episode)
        
        # Add host-specific information
        entry['role'] = guest_data.get('job_title', 'Guest')
        entry['affiliation'] = guest_data.get('affiliation', '')
        entry['badge'] = guest_data.get('credibilityBadge', 'Guest')
        entry['score'] = guest_data.get('proficiencyScore', 0)
        
        return entry
    
    def _extract_show_hosts(self, episodes: List[EpisodeObject]) -> List[Dict[str, Any]]:
        """Extract host information for show index"""
        host_data = defaultdict(lambda: {
            'appearances': 0,
            'roles': set(),
            'affiliations': set(),
            'badges': set()
        })
        
        for episode in episodes:
            if episode.enrichment and episode.enrichment.proficiency_scores:
                scores_data = episode.enrichment.proficiency_scores
                if 'scored_people' in scores_data:
                    for person in scores_data['scored_people']:
                        name = person.get('name', '')
                        if name:
                            host_data[name]['appearances'] += 1
                            if person.get('job_title'):
                                host_data[name]['roles'].add(person.get('job_title'))
                            if person.get('affiliation'):
                                host_data[name]['affiliations'].add(person.get('affiliation'))
                            if person.get('credibilityBadge'):
                                host_data[name]['badges'].add(person.get('credibilityBadge'))
        
        # Convert to list and sort by appearances
        hosts = []
        for name, data in host_data.items():
            if data['appearances'] >= 2:  # Only include frequent guests
                host_entry = {
                    'name': name,
                    'host_slug': self._create_host_slug(name),
                    'appearances': data['appearances'],
                    'primary_role': list(data['roles'])[0] if data['roles'] else 'Guest',
                    'primary_affiliation': list(data['affiliations'])[0] if data['affiliations'] else '',
                    'highest_badge': self._get_highest_badge(data['badges'])
                }
                hosts.append(host_entry)
        
        # Sort by appearances (descending)
        hosts.sort(key=lambda x: x['appearances'], reverse=True)
        return hosts[:10]  # Top 10 hosts
    
    def _extract_show_topics(self, episodes: List[EpisodeObject]) -> List[str]:
        """Extract topic tags for show index"""
        topic_counts = defaultdict(int)
        
        for episode in episodes:
            if episode.editorial and episode.editorial.topic_tags:
                for topic in episode.editorial.topic_tags:
                    topic_counts[topic] += 1
        
        # Sort by frequency and return top topics
        sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)
        return [topic for topic, _ in sorted_topics[:10]]
    
    def _extract_host_topics(self, appearances: List[Tuple[EpisodeObject, Dict[str, Any]]]) -> List[str]:
        """Extract topics for host index"""
        topic_counts = defaultdict(int)
        
        for episode, _ in appearances:
            if episode.editorial and episode.editorial.topic_tags:
                for topic in episode.editorial.topic_tags:
                    topic_counts[topic] += 1
        
        # Sort by frequency and return top topics
        sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)
        return [topic for topic, _ in sorted_topics[:8]]
    
    def _aggregate_host_credentials(self, appearances: List[Tuple[EpisodeObject, Dict[str, Any]]]) -> Dict[str, Any]:
        """Aggregate credentials from all appearances"""
        credentials = {
            'titles': set(),
            'affiliations': set(),
            'badges': set(),
            'scores': [],
            'reasoning': []
        }
        
        for _, guest_data in appearances:
            if guest_data.get('job_title'):
                credentials['titles'].add(guest_data.get('job_title'))
            if guest_data.get('affiliation'):
                credentials['affiliations'].add(guest_data.get('affiliation'))
            if guest_data.get('credibilityBadge'):
                credentials['badges'].add(guest_data.get('credibilityBadge'))
            if guest_data.get('proficiencyScore'):
                credentials['scores'].append(guest_data.get('proficiencyScore'))
            if guest_data.get('reasoning'):
                credentials['reasoning'].append(guest_data.get('reasoning'))
        
        # Convert sets to lists and calculate averages
        return {
            'primary_title': list(credentials['titles'])[0] if credentials['titles'] else '',
            'all_titles': list(credentials['titles']),
            'primary_affiliation': list(credentials['affiliations'])[0] if credentials['affiliations'] else '',
            'all_affiliations': list(credentials['affiliations']),
            'highest_badge': self._get_highest_badge(credentials['badges']),
            'all_badges': list(credentials['badges']),
            'average_score': sum(credentials['scores']) / len(credentials['scores']) if credentials['scores'] else 0,
            'score_range': [min(credentials['scores']), max(credentials['scores'])] if credentials['scores'] else [0, 0],
            'sample_reasoning': credentials['reasoning'][0] if credentials['reasoning'] else ''
        }
    
    def _generate_show_description(self, show_name: str, episodes: List[EpisodeObject], 
                                 hosts: List[Dict[str, Any]], topics: List[str]) -> str:
        """Generate engaging show description"""
        try:
            # Base description
            description = f"{show_name} features in-depth conversations with industry experts and thought leaders"
            
            # Add topic focus if available
            if topics:
                if len(topics) == 1:
                    description += f", focusing on {topics[0].lower()}"
                elif len(topics) <= 3:
                    description += f", covering {', '.join(topics[:2]).lower()} and {topics[2].lower()}"
                else:
                    description += f", exploring topics including {', '.join(topics[:3]).lower()} and more"
            
            # Add host information if available
            if hosts:
                verified_hosts = [h for h in hosts if h.get('highest_badge') == 'Verified Expert']
                if verified_hosts:
                    description += f". The show regularly features verified experts"
                    if len(verified_hosts) <= 2:
                        names = [h['name'] for h in verified_hosts[:2]]
                        description += f" including {' and '.join(names)}"
            
            # Add episode count
            description += f". With {len(episodes)} episodes available, the show provides comprehensive coverage of current issues and expert insights."
            
            return description
        
        except Exception:
            return f"{show_name} provides expert insights and in-depth discussions on current topics."
    
    def _generate_host_biography(self, host_name: str, credentials: Dict[str, Any],
                               shows: List[Dict[str, Any]], topics: List[str]) -> str:
        """Generate professional biographical context"""
        try:
            bio_parts = []
            
            # Name and primary title
            primary_title = credentials.get('primary_title', '')
            if primary_title:
                bio_parts.append(f"{host_name} is a {primary_title}")
            else:
                bio_parts.append(f"{host_name} is a recognized expert")
            
            # Primary affiliation
            primary_affiliation = credentials.get('primary_affiliation', '')
            if primary_affiliation:
                bio_parts.append(f"at {primary_affiliation}")
            
            # Expertise areas
            if topics:
                if len(topics) <= 2:
                    bio_parts.append(f"specializing in {' and '.join(topics).lower()}")
                else:
                    bio_parts.append(f"with expertise in {', '.join(topics[:2]).lower()}, and {topics[2].lower()}")
            
            # Appearance summary
            total_appearances = sum(show['appearances'] for show in shows)
            if len(shows) == 1:
                bio_parts.append(f"Having appeared {total_appearances} times on {shows[0]['show_name']}")
            else:
                bio_parts.append(f"With {total_appearances} appearances across {len(shows)} shows")
            
            # Credibility badge
            highest_badge = credentials.get('highest_badge', '')
            if highest_badge == 'Verified Expert':
                bio_parts.append(f"{host_name} brings verified expertise and authoritative insights to discussions")
            elif highest_badge == 'Identified Contributor':
                bio_parts.append(f"{host_name} provides valuable perspectives as an identified industry contributor")
            
            # Combine parts
            biography = ". ".join(bio_parts) + "."
            
            # Clean up grammar
            biography = re.sub(r'\s+', ' ', biography)
            biography = biography.replace('. .', '.')
            
            return biography
        
        except Exception:
            return f"{host_name} is a featured guest and expert contributor."
    
    def _get_episode_title(self, episode: EpisodeObject) -> str:
        """Get episode title from metadata or editorial content"""
        if episode.metadata.title:
            return episode.metadata.title
        elif episode.editorial and episode.editorial.key_takeaway:
            return episode.editorial.key_takeaway
        elif episode.metadata.topic:
            return episode.metadata.topic
        else:
            return f"{episode.metadata.show_name or 'Episode'} - {episode.episode_id}"
    
    def _create_host_slug(self, name: str) -> str:
        """Create URL-friendly slug from host name"""
        # Convert to lowercase and replace spaces/special chars with hyphens
        slug = re.sub(r'[^\w\s-]', '', name.lower())
        slug = re.sub(r'[-\s]+', '-', slug)
        return slug.strip('-')
    
    def _get_highest_badge(self, badges: Set[str]) -> str:
        """Get the highest credibility badge from a set"""
        badge_hierarchy = ['Verified Expert', 'Identified Contributor', 'Guest']
        
        for badge in badge_hierarchy:
            if badge in badges:
                return badge
        
        return 'Guest'
    
    def _write_show_indices(self, show_indices: Dict[str, ShowIndex]) -> Dict[str, Path]:
        """Write show indices to files"""
        written_files = {}
        
        for show_slug, show_index in show_indices.items():
            try:
                # Convert to dictionary
                index_data = {
                    'show_slug': show_index.show_slug,
                    'show_name': show_index.show_name,
                    'total_episodes': show_index.total_episodes,
                    'seasons': show_index.seasons,
                    'episodes': show_index.episodes,
                    'hosts': show_index.hosts,
                    'topics': show_index.topics,
                    'description': show_index.description,
                    'last_updated': show_index.last_updated.isoformat()
                }
                
                # Write to file
                output_path = self.output_base / 'shows' / f'{show_slug}.json'
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(index_data, f, indent=2, ensure_ascii=False)
                
                written_files[show_slug] = output_path
                
                self.logger.debug(
                    "Show index written",
                    show_slug=show_slug,
                    output_path=str(output_path)
                )
            
            except Exception as e:
                self.logger.error(
                    "Failed to write show index",
                    show_slug=show_slug,
                    exception=e
                )
        
        return written_files
    
    def _write_host_indices(self, host_indices: Dict[str, HostIndex]) -> Dict[str, Path]:
        """Write host indices to files"""
        written_files = {}
        
        for host_slug, host_index in host_indices.items():
            try:
                # Convert to dictionary
                index_data = {
                    'host_slug': host_index.host_slug,
                    'name': host_index.name,
                    'total_appearances': host_index.total_appearances,
                    'shows': host_index.shows,
                    'episodes': host_index.episodes,
                    'topics': host_index.topics,
                    'credentials': host_index.credentials,
                    'biography': host_index.biography,
                    'last_updated': host_index.last_updated.isoformat()
                }
                
                # Write to file
                output_path = self.output_base / 'hosts' / f'{host_slug}.json'
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(index_data, f, indent=2, ensure_ascii=False)
                
                written_files[host_slug] = output_path
                
                self.logger.debug(
                    "Host index written",
                    host_slug=host_slug,
                    output_path=str(output_path)
                )
            
            except Exception as e:
                self.logger.error(
                    "Failed to write host index",
                    host_slug=host_slug,
                    exception=e
                )
        
        return written_files
    
    def _write_global_index(self, global_index: GlobalIndex) -> Optional[Path]:
        """Write global index to file"""
        try:
            # Convert to dictionary
            index_data = {
                'total_episodes': global_index.total_episodes,
                'total_shows': global_index.total_shows,
                'total_hosts': global_index.total_hosts,
                'shows': global_index.shows,
                'featured_hosts': global_index.featured_hosts,
                'recent_episodes': global_index.recent_episodes,
                'popular_topics': global_index.popular_topics,
                'last_updated': global_index.last_updated.isoformat()
            }
            
            # Write to file
            output_path = self.output_base / 'global.json'
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(index_data, f, indent=2, ensure_ascii=False)
            
            self.logger.debug(
                "Global index written",
                output_path=str(output_path)
            )
            
            return output_path
        
        except Exception as e:
            self.logger.error(
                "Failed to write global index",
                exception=e
            )
            return None
    
    def _validate_indices(self, show_indices: Dict[str, ShowIndex],
                        host_indices: Dict[str, HostIndex],
                        global_index: GlobalIndex) -> Dict[str, Any]:
        """Validate generated indices for consistency"""
        validation_results = {
            'valid': True,
            'issues': [],
            'warnings': [],
            'statistics': {}
        }
        
        try:
            # Validate show indices
            for show_slug, show_index in show_indices.items():
                if not show_index.episodes:
                    validation_results['issues'].append(f"Show {show_slug} has no episodes")
                    validation_results['valid'] = False
                
                if show_index.total_episodes != len(show_index.episodes):
                    validation_results['warnings'].append(
                        f"Show {show_slug} episode count mismatch: {show_index.total_episodes} vs {len(show_index.episodes)}"
                    )
            
            # Validate host indices
            for host_slug, host_index in host_indices.items():
                if not host_index.episodes:
                    validation_results['issues'].append(f"Host {host_slug} has no episodes")
                    validation_results['valid'] = False
                
                if host_index.total_appearances != len(host_index.episodes):
                    validation_results['warnings'].append(
                        f"Host {host_slug} appearance count mismatch: {host_index.total_appearances} vs {len(host_index.episodes)}"
                    )
            
            # Validate global index consistency
            if global_index.total_shows != len(show_indices):
                validation_results['warnings'].append(
                    f"Global index show count mismatch: {global_index.total_shows} vs {len(show_indices)}"
                )
            
            if global_index.total_hosts != len(host_indices):
                validation_results['warnings'].append(
                    f"Global index host count mismatch: {global_index.total_hosts} vs {len(host_indices)}"
                )
            
            # Generate statistics
            validation_results['statistics'] = {
                'total_shows': len(show_indices),
                'total_hosts': len(host_indices),
                'total_episodes': global_index.total_episodes,
                'avg_episodes_per_show': global_index.total_episodes / len(show_indices) if show_indices else 0,
                'avg_appearances_per_host': sum(h.total_appearances for h in host_indices.values()) / len(host_indices) if host_indices else 0
            }
        
        except Exception as e:
            validation_results['valid'] = False
            validation_results['issues'].append(f"Validation failed: {str(e)}")
        
        return validation_results


class IndexValidator:
    """Validator for index consistency and quality"""
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.logger = get_logger('pipeline.index_validator')
    
    def validate_index_consistency(self, show_indices: Dict[str, ShowIndex],
                                 host_indices: Dict[str, HostIndex],
                                 episodes: List[EpisodeObject]) -> Dict[str, Any]:
        """
        Validate consistency between indices and source episodes
        
        Args:
            show_indices: Generated show indices
            host_indices: Generated host indices
            episodes: Source episodes
            
        Returns:
            Dict[str, Any]: Validation results
        """
        try:
            validation_result = {
                'consistent': True,
                'cross_reference_issues': [],
                'data_integrity_issues': [],
                'completeness_issues': [],
                'recommendations': []
            }
            
            # Check cross-references between shows and hosts
            self._validate_cross_references(show_indices, host_indices, validation_result)
            
            # Check data integrity
            self._validate_data_integrity(show_indices, host_indices, episodes, validation_result)
            
            # Check completeness
            self._validate_completeness(show_indices, host_indices, episodes, validation_result)
            
            # Generate recommendations
            self._generate_validation_recommendations(validation_result)
            
            # Set overall consistency flag
            validation_result['consistent'] = (
                not validation_result['cross_reference_issues'] and
                not validation_result['data_integrity_issues'] and
                not validation_result['completeness_issues']
            )
            
            return validation_result
        
        except Exception as e:
            self.logger.error(
                "Index validation failed",
                exception=e
            )
            return {
                'consistent': False,
                'cross_reference_issues': ['Validation process failed'],
                'data_integrity_issues': [],
                'completeness_issues': [],
                'recommendations': ['Manual validation required']
            }
    
    def _validate_cross_references(self, show_indices: Dict[str, ShowIndex],
                                 host_indices: Dict[str, HostIndex],
                                 validation_result: Dict[str, Any]) -> None:
        """Validate cross-references between shows and hosts"""
        # Check that hosts mentioned in shows exist in host indices
        for show_slug, show_index in show_indices.items():
            for host in show_index.hosts:
                host_slug = host.get('host_slug')
                if host_slug and host_slug not in host_indices:
                    validation_result['cross_reference_issues'].append(
                        f"Show {show_slug} references non-existent host {host_slug}"
                    )
        
        # Check that shows mentioned in hosts exist in show indices
        for host_slug, host_index in host_indices.items():
            for show in host_index.shows:
                show_slug = show.get('show_slug')
                if show_slug and show_slug not in show_indices:
                    validation_result['cross_reference_issues'].append(
                        f"Host {host_slug} references non-existent show {show_slug}"
                    )
    
    def _validate_data_integrity(self, show_indices: Dict[str, ShowIndex],
                               host_indices: Dict[str, HostIndex],
                               episodes: List[EpisodeObject],
                               validation_result: Dict[str, Any]) -> None:
        """Validate data integrity between indices and episodes"""
        episode_ids = {ep.episode_id for ep in episodes}
        
        # Check that all episodes in indices exist in source data
        for show_slug, show_index in show_indices.items():
            for episode in show_index.episodes:
                episode_id = episode.get('episode_id')
                if episode_id and episode_id not in episode_ids:
                    validation_result['data_integrity_issues'].append(
                        f"Show {show_slug} references non-existent episode {episode_id}"
                    )
        
        for host_slug, host_index in host_indices.items():
            for episode in host_index.episodes:
                episode_id = episode.get('episode_id')
                if episode_id and episode_id not in episode_ids:
                    validation_result['data_integrity_issues'].append(
                        f"Host {host_slug} references non-existent episode {episode_id}"
                    )
    
    def _validate_completeness(self, show_indices: Dict[str, ShowIndex],
                             host_indices: Dict[str, HostIndex],
                             episodes: List[EpisodeObject],
                             validation_result: Dict[str, Any]) -> None:
        """Validate completeness of indices"""
        # Check that all shows have indices
        show_slugs_in_episodes = {ep.metadata.show_slug for ep in episodes}
        show_slugs_in_indices = set(show_indices.keys())
        
        missing_shows = show_slugs_in_episodes - show_slugs_in_indices
        for show_slug in missing_shows:
            validation_result['completeness_issues'].append(
                f"Missing show index for {show_slug}"
            )
        
        # Check for minimum content requirements
        for show_slug, show_index in show_indices.items():
            if not show_index.description:
                validation_result['completeness_issues'].append(
                    f"Show {show_slug} missing description"
                )
            
            if not show_index.topics:
                validation_result['completeness_issues'].append(
                    f"Show {show_slug} missing topics"
                )
        
        for host_slug, host_index in host_indices.items():
            if not host_index.biography:
                validation_result['completeness_issues'].append(
                    f"Host {host_slug} missing biography"
                )
    
    def _generate_validation_recommendations(self, validation_result: Dict[str, Any]) -> None:
        """Generate recommendations based on validation results"""
        if validation_result['cross_reference_issues']:
            validation_result['recommendations'].append(
                "Review and fix cross-reference inconsistencies between shows and hosts"
            )
        
        if validation_result['data_integrity_issues']:
            validation_result['recommendations'].append(
                "Verify episode data integrity and rebuild indices if necessary"
            )
        
        if validation_result['completeness_issues']:
            validation_result['recommendations'].append(
                "Complete missing index content (descriptions, biographies, topics)"
            )
        
        if not any([
            validation_result['cross_reference_issues'],
            validation_result['data_integrity_issues'],
            validation_result['completeness_issues']
        ]):
            validation_result['recommendations'].append(
                "All indices are consistent and complete"
            )


class GlobalIndexManager:
    """
    Global index management for master indices and cross-references
    
    Manages master index updates, cross-reference generation between shows and hosts,
    search optimization metadata, and index validation and consistency checks.
    """
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.logger = get_logger('pipeline.global_index_manager')
        
        # Output configuration
        self.output_base = Path(self._get_config_value('output', {}).get('indices', 'output/indices'))
        self.search_base = Path(self._get_config_value('output', {}).get('search', 'output/search'))
        
        # Search optimization configuration
        self.enable_search_optimization = self._get_config_value('search', {}).get('enabled', True)
        self.search_index_fields = self._get_config_value('search', {}).get('fields', [
            'title', 'summary', 'topics', 'guests', 'show_name'
        ])
        
        # Ensure output directories exist
        self.output_base.mkdir(parents=True, exist_ok=True)
        self.search_base.mkdir(parents=True, exist_ok=True)
    
    def _get_config_value(self, key: str, default: Any = None) -> Any:
        """Get configuration value, handling both dict and dataclass config"""
        if hasattr(self.config, 'get'):
            return self.config.get(key, default)
        elif hasattr(self.config, key):
            return getattr(self.config, key)
        else:
            return default
    
    def update_master_indices(self, new_episode: EpisodeObject, 
                            all_episodes: List[EpisodeObject]) -> Dict[str, Any]:
        """
        Update master indices for new episodes
        
        Args:
            new_episode: Newly processed episode
            all_episodes: Complete list of all episodes
            
        Returns:
            Dict[str, Any]: Update results and statistics
        """
        self.logger.info(
            "Updating master indices",
            new_episode_id=new_episode.episode_id,
            total_episodes=len(all_episodes)
        )
        
        try:
            update_result = {
                'success': True,
                'indices_updated': [],
                'cross_references_updated': 0,
                'search_indices_updated': False,
                'validation_passed': True,
                'update_time': 0.0,
                'statistics': {}
            }
            
            start_time = datetime.now()
            
            # Build complete indices
            index_builder = IndexBuilder(self.config)
            build_result = index_builder.build_all_indices(all_episodes)
            
            # Load existing indices for comparison
            existing_show_indices = self._load_existing_show_indices()
            existing_host_indices = self._load_existing_host_indices()
            existing_global_index = self._load_existing_global_index()
            
            # Generate cross-references
            cross_references = self._generate_cross_references(
                build_result.show_indices_updated,
                build_result.host_indices_updated,
                all_episodes
            )
            update_result['cross_references_updated'] = len(cross_references)
            
            # Update search optimization metadata
            if self.enable_search_optimization:
                search_update = self._update_search_indices(all_episodes)
                update_result['search_indices_updated'] = search_update['success']
            
            # Validate indices
            validation_result = self._validate_master_indices(all_episodes)
            update_result['validation_passed'] = validation_result['consistent']
            
            # Generate update statistics
            update_result['statistics'] = self._generate_update_statistics(
                build_result, existing_show_indices, existing_host_indices
            )
            
            # Calculate update time
            update_result['update_time'] = (datetime.now() - start_time).total_seconds()
            
            # Write cross-references
            self._write_cross_references(cross_references)
            
            # Write update metadata
            self._write_update_metadata(update_result, new_episode)
            
            self.logger.info(
                "Master indices updated successfully",
                new_episode_id=new_episode.episode_id,
                shows_updated=len(build_result.show_indices_updated),
                hosts_updated=len(build_result.host_indices_updated),
                update_time=update_result['update_time']
            )
            
            return update_result
        
        except Exception as e:
            error_msg = f"Failed to update master indices: {str(e)}"
            self.logger.error(error_msg, new_episode_id=new_episode.episode_id, exception=e)
            return {
                'success': False,
                'error': error_msg,
                'indices_updated': [],
                'cross_references_updated': 0,
                'search_indices_updated': False,
                'validation_passed': False,
                'update_time': 0.0,
                'statistics': {}
            }
    
    def generate_cross_references(self, episodes: List[EpisodeObject]) -> Dict[str, Any]:
        """
        Generate cross-reference mappings between shows and hosts
        
        Args:
            episodes: List of all episodes
            
        Returns:
            Dict[str, Any]: Cross-reference data structure
        """
        try:
            cross_references = {
                'show_to_hosts': defaultdict(list),
                'host_to_shows': defaultdict(list),
                'topic_to_episodes': defaultdict(list),
                'episode_to_related': defaultdict(list),
                'guest_networks': defaultdict(set),
                'topic_networks': defaultdict(set),
                'generation_time': datetime.now().isoformat()
            }
            
            # Build show-to-hosts mapping
            for episode in episodes:
                show_slug = episode.metadata.show_slug
                
                if episode.enrichment and episode.enrichment.proficiency_scores:
                    scores_data = episode.enrichment.proficiency_scores
                    if 'scored_people' in scores_data:
                        for person in scores_data['scored_people']:
                            name = person.get('name', '')
                            if name:
                                host_slug = self._create_host_slug(name)
                                
                                # Show-to-hosts mapping
                                host_entry = {
                                    'host_slug': host_slug,
                                    'name': name,
                                    'appearances': 1,
                                    'latest_episode': episode.episode_id,
                                    'latest_date': episode.metadata.date,
                                    'role': person.get('job_title', 'Guest'),
                                    'badge': person.get('credibilityBadge', 'Guest')
                                }
                                
                                # Check if host already exists for this show
                                existing_host = None
                                for existing in cross_references['show_to_hosts'][show_slug]:
                                    if existing['host_slug'] == host_slug:
                                        existing_host = existing
                                        break
                                
                                if existing_host:
                                    existing_host['appearances'] += 1
                                    if episode.metadata.date and episode.metadata.date > existing_host.get('latest_date', ''):
                                        existing_host['latest_episode'] = episode.episode_id
                                        existing_host['latest_date'] = episode.metadata.date
                                else:
                                    cross_references['show_to_hosts'][show_slug].append(host_entry)
                                
                                # Host-to-shows mapping
                                show_entry = {
                                    'show_slug': show_slug,
                                    'show_name': episode.metadata.show_name,
                                    'appearances': 1,
                                    'latest_episode': episode.episode_id,
                                    'latest_date': episode.metadata.date
                                }
                                
                                # Check if show already exists for this host
                                existing_show = None
                                for existing in cross_references['host_to_shows'][host_slug]:
                                    if existing['show_slug'] == show_slug:
                                        existing_show = existing
                                        break
                                
                                if existing_show:
                                    existing_show['appearances'] += 1
                                    if episode.metadata.date and episode.metadata.date > existing_show.get('latest_date', ''):
                                        existing_show['latest_episode'] = episode.episode_id
                                        existing_show['latest_date'] = episode.metadata.date
                                else:
                                    cross_references['host_to_shows'][host_slug].append(show_entry)
                                
                                # Build guest networks (co-appearances)
                                for other_person in scores_data['scored_people']:
                                    other_name = other_person.get('name', '')
                                    if other_name and other_name != name:
                                        other_host_slug = self._create_host_slug(other_name)
                                        cross_references['guest_networks'][host_slug].add(other_host_slug)
                
                # Build topic-to-episodes mapping
                if episode.editorial and episode.editorial.topic_tags:
                    for topic in episode.editorial.topic_tags:
                        topic_entry = {
                            'episode_id': episode.episode_id,
                            'show_slug': show_slug,
                            'show_name': episode.metadata.show_name,
                            'title': episode.metadata.title or episode.editorial.key_takeaway,
                            'date': episode.metadata.date
                        }
                        cross_references['topic_to_episodes'][topic].append(topic_entry)
                        
                        # Build topic networks (co-occurring topics)
                        for other_topic in episode.editorial.topic_tags:
                            if other_topic != topic:
                                cross_references['topic_networks'][topic].add(other_topic)
            
            # Generate episode-to-related mappings
            cross_references['episode_to_related'] = self._generate_episode_relationships(episodes)
            
            # Convert sets to lists for JSON serialization
            cross_references['guest_networks'] = {
                k: list(v) for k, v in cross_references['guest_networks'].items()
            }
            cross_references['topic_networks'] = {
                k: list(v) for k, v in cross_references['topic_networks'].items()
            }
            
            # Convert defaultdicts to regular dicts
            cross_references = {
                k: dict(v) if isinstance(v, defaultdict) else v
                for k, v in cross_references.items()
            }
            
            self.logger.info(
                "Cross-references generated",
                shows=len(cross_references['show_to_hosts']),
                hosts=len(cross_references['host_to_shows']),
                topics=len(cross_references['topic_to_episodes'])
            )
            
            return cross_references
        
        except Exception as e:
            error_msg = f"Failed to generate cross-references: {str(e)}"
            self.logger.error(error_msg, exception=e)
            raise ProcessingError(error_msg, stage="cross_reference_generation")
    
    def update_search_optimization_metadata(self, episodes: List[EpisodeObject]) -> Dict[str, Any]:
        """
        Generate search optimization metadata for indices
        
        Args:
            episodes: List of all episodes
            
        Returns:
            Dict[str, Any]: Search optimization results
        """
        try:
            search_result = {
                'success': True,
                'search_documents': 0,
                'indexed_fields': [],
                'search_statistics': {},
                'optimization_time': 0.0
            }
            
            start_time = datetime.now()
            
            if not self.enable_search_optimization:
                search_result['success'] = False
                search_result['message'] = 'Search optimization disabled'
                return search_result
            
            # Generate search documents for episodes
            search_documents = []
            
            for episode in episodes:
                if episode.processing_stage != ProcessingStage.RENDERED:
                    continue
                
                # Create search document
                search_doc = {
                    'id': episode.episode_id,
                    'type': 'episode',
                    'title': self._get_episode_title(episode),
                    'show_name': episode.metadata.show_name,
                    'show_slug': episode.metadata.show_slug,
                    'date': episode.metadata.date,
                    'season': episode.metadata.season,
                    'episode_number': episode.metadata.episode
                }
                
                # Add editorial content
                if episode.editorial:
                    if episode.editorial.summary:
                        search_doc['summary'] = episode.editorial.summary
                    if episode.editorial.key_takeaway:
                        search_doc['key_takeaway'] = episode.editorial.key_takeaway
                    if episode.editorial.topic_tags:
                        search_doc['topics'] = episode.editorial.topic_tags
                
                # Add guest information
                if episode.enrichment and episode.enrichment.proficiency_scores:
                    scores_data = episode.enrichment.proficiency_scores
                    if 'scored_people' in scores_data:
                        guests = []
                        for person in scores_data['scored_people']:
                            guest = {
                                'name': person.get('name', ''),
                                'title': person.get('job_title', ''),
                                'affiliation': person.get('affiliation', ''),
                                'badge': person.get('credibilityBadge', 'Guest')
                            }
                            if guest['name']:
                                guests.append(guest)
                        search_doc['guests'] = guests
                
                # Add searchable text field (combination of all text content)
                searchable_parts = []
                if search_doc.get('title'):
                    searchable_parts.append(search_doc['title'])
                if search_doc.get('summary'):
                    searchable_parts.append(search_doc['summary'])
                if search_doc.get('key_takeaway'):
                    searchable_parts.append(search_doc['key_takeaway'])
                if search_doc.get('topics'):
                    searchable_parts.extend(search_doc['topics'])
                if search_doc.get('guests'):
                    for guest in search_doc['guests']:
                        if guest.get('name'):
                            searchable_parts.append(guest['name'])
                        if guest.get('title'):
                            searchable_parts.append(guest['title'])
                
                search_doc['searchable_text'] = ' '.join(searchable_parts)
                
                # Add search optimization metadata
                search_doc['search_metadata'] = {
                    'word_count': len(search_doc['searchable_text'].split()),
                    'has_summary': bool(search_doc.get('summary')),
                    'has_guests': bool(search_doc.get('guests')),
                    'topic_count': len(search_doc.get('topics', [])),
                    'guest_count': len(search_doc.get('guests', []))
                }
                
                search_documents.append(search_doc)
            
            # Write search index
            search_index_path = self.search_base / 'episodes.json'
            with open(search_index_path, 'w', encoding='utf-8') as f:
                json.dump(search_documents, f, indent=2, ensure_ascii=False)
            
            # Generate search statistics
            search_statistics = self._generate_search_statistics(search_documents)
            
            # Generate search configuration
            search_config = self._generate_search_config(search_documents)
            search_config_path = self.search_base / 'config.json'
            with open(search_config_path, 'w', encoding='utf-8') as f:
                json.dump(search_config, f, indent=2, ensure_ascii=False)
            
            # Update result
            search_result.update({
                'search_documents': len(search_documents),
                'indexed_fields': list(self.search_index_fields),
                'search_statistics': search_statistics,
                'optimization_time': (datetime.now() - start_time).total_seconds()
            })
            
            self.logger.info(
                "Search optimization metadata updated",
                documents=len(search_documents),
                optimization_time=search_result['optimization_time']
            )
            
            return search_result
        
        except Exception as e:
            error_msg = f"Failed to update search optimization metadata: {str(e)}"
            self.logger.error(error_msg, exception=e)
            return {
                'success': False,
                'error': error_msg,
                'search_documents': 0,
                'indexed_fields': [],
                'search_statistics': {},
                'optimization_time': 0.0
            }
    
    def validate_index_consistency(self, episodes: List[EpisodeObject]) -> Dict[str, Any]:
        """
        Validate index consistency and generate consistency report
        
        Args:
            episodes: List of all episodes
            
        Returns:
            Dict[str, Any]: Consistency validation results
        """
        try:
            validation_result = {
                'consistent': True,
                'validation_time': 0.0,
                'index_integrity': {},
                'cross_reference_integrity': {},
                'search_integrity': {},
                'recommendations': []
            }
            
            start_time = datetime.now()
            
            # Load all indices
            show_indices = self._load_existing_show_indices()
            host_indices = self._load_existing_host_indices()
            global_index = self._load_existing_global_index()
            cross_references = self._load_existing_cross_references()
            
            # Validate index integrity
            index_validator = IndexValidator(self.config)
            index_validation = index_validator.validate_index_consistency(
                show_indices, host_indices, episodes
            )
            validation_result['index_integrity'] = index_validation
            
            if not index_validation['consistent']:
                validation_result['consistent'] = False
            
            # Validate cross-reference integrity
            cross_ref_validation = self._validate_cross_reference_integrity(
                cross_references, show_indices, host_indices
            )
            validation_result['cross_reference_integrity'] = cross_ref_validation
            
            if not cross_ref_validation['consistent']:
                validation_result['consistent'] = False
            
            # Validate search index integrity
            if self.enable_search_optimization:
                search_validation = self._validate_search_integrity(episodes)
                validation_result['search_integrity'] = search_validation
                
                if not search_validation['consistent']:
                    validation_result['consistent'] = False
            
            # Generate recommendations
            recommendations = []
            if not validation_result['consistent']:
                recommendations.append("Rebuild indices to resolve consistency issues")
            
            if index_validation.get('completeness_issues'):
                recommendations.append("Complete missing index content")
            
            if cross_ref_validation.get('orphaned_references'):
                recommendations.append("Clean up orphaned cross-references")
            
            validation_result['recommendations'] = recommendations
            validation_result['validation_time'] = (datetime.now() - start_time).total_seconds()
            
            self.logger.info(
                "Index consistency validation completed",
                consistent=validation_result['consistent'],
                validation_time=validation_result['validation_time']
            )
            
            return validation_result
        
        except Exception as e:
            error_msg = f"Failed to validate index consistency: {str(e)}"
            self.logger.error(error_msg, exception=e)
            return {
                'consistent': False,
                'error': error_msg,
                'validation_time': 0.0,
                'index_integrity': {},
                'cross_reference_integrity': {},
                'search_integrity': {},
                'recommendations': ['Manual validation required due to validation failure']
            }
    
    # Private helper methods
    
    def _load_existing_show_indices(self) -> Dict[str, Any]:
        """Load existing show indices from files"""
        show_indices = {}
        shows_dir = self.output_base / 'shows'
        
        if shows_dir.exists():
            for show_file in shows_dir.glob('*.json'):
                try:
                    with open(show_file, 'r', encoding='utf-8') as f:
                        show_data = json.load(f)
                        show_slug = show_file.stem
                        show_indices[show_slug] = show_data
                except Exception as e:
                    self.logger.warning(
                        "Failed to load show index",
                        show_file=str(show_file),
                        exception=e
                    )
        
        return show_indices
    
    def _load_existing_host_indices(self) -> Dict[str, Any]:
        """Load existing host indices from files"""
        host_indices = {}
        hosts_dir = self.output_base / 'hosts'
        
        if hosts_dir.exists():
            for host_file in hosts_dir.glob('*.json'):
                try:
                    with open(host_file, 'r', encoding='utf-8') as f:
                        host_data = json.load(f)
                        host_slug = host_file.stem
                        host_indices[host_slug] = host_data
                except Exception as e:
                    self.logger.warning(
                        "Failed to load host index",
                        host_file=str(host_file),
                        exception=e
                    )
        
        return host_indices
    
    def _load_existing_global_index(self) -> Optional[Dict[str, Any]]:
        """Load existing global index from file"""
        global_file = self.output_base / 'global.json'
        
        if global_file.exists():
            try:
                with open(global_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(
                    "Failed to load global index",
                    global_file=str(global_file),
                    exception=e
                )
        
        return None
    
    def _load_existing_cross_references(self) -> Optional[Dict[str, Any]]:
        """Load existing cross-references from file"""
        cross_ref_file = self.output_base / 'cross_references.json'
        
        if cross_ref_file.exists():
            try:
                with open(cross_ref_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(
                    "Failed to load cross-references",
                    cross_ref_file=str(cross_ref_file),
                    exception=e
                )
        
        return None
    
    def _generate_cross_references(self, show_slugs: List[str], host_slugs: List[str],
                                 episodes: List[EpisodeObject]) -> Dict[str, Any]:
        """Generate cross-references for updated indices"""
        return self.generate_cross_references(episodes)
    
    def _update_search_indices(self, episodes: List[EpisodeObject]) -> Dict[str, Any]:
        """Update search optimization indices"""
        return self.update_search_optimization_metadata(episodes)
    
    def _validate_master_indices(self, episodes: List[EpisodeObject]) -> Dict[str, Any]:
        """Validate master indices consistency"""
        return self.validate_index_consistency(episodes)
    
    def _generate_update_statistics(self, build_result: IndexBuildResult,
                                  existing_show_indices: Dict[str, Any],
                                  existing_host_indices: Dict[str, Any]) -> Dict[str, Any]:
        """Generate statistics about the update operation"""
        return {
            'shows_added': len(set(build_result.show_indices_updated) - set(existing_show_indices.keys())),
            'shows_updated': len(set(build_result.show_indices_updated) & set(existing_show_indices.keys())),
            'hosts_added': len(set(build_result.host_indices_updated) - set(existing_host_indices.keys())),
            'hosts_updated': len(set(build_result.host_indices_updated) & set(existing_host_indices.keys())),
            'total_episodes_processed': build_result.total_episodes_processed,
            'build_time': build_result.build_time
        }
    
    def _write_cross_references(self, cross_references: Dict[str, Any]) -> None:
        """Write cross-references to file"""
        try:
            cross_ref_path = self.output_base / 'cross_references.json'
            with open(cross_ref_path, 'w', encoding='utf-8') as f:
                json.dump(cross_references, f, indent=2, ensure_ascii=False)
            
            self.logger.debug(
                "Cross-references written",
                output_path=str(cross_ref_path)
            )
        
        except Exception as e:
            self.logger.error(
                "Failed to write cross-references",
                exception=e
            )
    
    def _write_update_metadata(self, update_result: Dict[str, Any], 
                             new_episode: EpisodeObject) -> None:
        """Write update metadata for tracking"""
        try:
            update_metadata = {
                'last_update': datetime.now().isoformat(),
                'trigger_episode': new_episode.episode_id,
                'update_result': update_result
            }
            
            metadata_path = self.output_base / 'update_metadata.json'
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(update_metadata, f, indent=2, ensure_ascii=False)
            
            self.logger.debug(
                "Update metadata written",
                output_path=str(metadata_path)
            )
        
        except Exception as e:
            self.logger.error(
                "Failed to write update metadata",
                exception=e
            )
    
    def _generate_episode_relationships(self, episodes: List[EpisodeObject]) -> Dict[str, List[str]]:
        """Generate episode-to-related-episodes mappings"""
        episode_relationships = {}
        
        for episode in episodes:
            related_episodes = []
            
            # Find episodes with similar topics
            if episode.editorial and episode.editorial.topic_tags:
                episode_topics = set(episode.editorial.topic_tags)
                
                for other_episode in episodes:
                    if other_episode.episode_id == episode.episode_id:
                        continue
                    
                    if other_episode.editorial and other_episode.editorial.topic_tags:
                        other_topics = set(other_episode.editorial.topic_tags)
                        
                        # Calculate topic overlap
                        overlap = len(episode_topics & other_topics)
                        if overlap >= 2:  # At least 2 topics in common
                            related_episodes.append(other_episode.episode_id)
            
            # Find episodes with same guests
            if episode.enrichment and episode.enrichment.proficiency_scores:
                scores_data = episode.enrichment.proficiency_scores
                if 'scored_people' in scores_data:
                    episode_guests = {person.get('name', '') for person in scores_data['scored_people']}
                    
                    for other_episode in episodes:
                        if other_episode.episode_id == episode.episode_id:
                            continue
                        
                        if other_episode.enrichment and other_episode.enrichment.proficiency_scores:
                            other_scores = other_episode.enrichment.proficiency_scores
                            if 'scored_people' in other_scores:
                                other_guests = {person.get('name', '') for person in other_scores['scored_people']}
                                
                                # Check for guest overlap
                                if episode_guests & other_guests:
                                    if other_episode.episode_id not in related_episodes:
                                        related_episodes.append(other_episode.episode_id)
            
            # Limit to top 5 related episodes
            episode_relationships[episode.episode_id] = related_episodes[:5]
        
        return episode_relationships
    
    def _generate_search_statistics(self, search_documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate search optimization statistics"""
        if not search_documents:
            return {}
        
        # Calculate statistics
        total_docs = len(search_documents)
        docs_with_summary = sum(1 for doc in search_documents if doc.get('summary'))
        docs_with_guests = sum(1 for doc in search_documents if doc.get('guests'))
        
        topic_counts = []
        guest_counts = []
        word_counts = []
        
        for doc in search_documents:
            topic_counts.append(len(doc.get('topics', [])))
            guest_counts.append(len(doc.get('guests', [])))
            word_counts.append(doc.get('search_metadata', {}).get('word_count', 0))
        
        return {
            'total_documents': total_docs,
            'documents_with_summary': docs_with_summary,
            'documents_with_guests': docs_with_guests,
            'average_topics_per_document': sum(topic_counts) / total_docs if total_docs else 0,
            'average_guests_per_document': sum(guest_counts) / total_docs if total_docs else 0,
            'average_words_per_document': sum(word_counts) / total_docs if total_docs else 0,
            'summary_coverage': docs_with_summary / total_docs if total_docs else 0,
            'guest_coverage': docs_with_guests / total_docs if total_docs else 0
        }
    
    def _generate_search_config(self, search_documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate search configuration for frontend"""
        # Extract all unique values for faceted search
        all_shows = set()
        all_topics = set()
        all_guest_names = set()
        all_badges = set()
        
        for doc in search_documents:
            if doc.get('show_name'):
                all_shows.add(doc['show_name'])
            
            if doc.get('topics'):
                all_topics.update(doc['topics'])
            
            if doc.get('guests'):
                for guest in doc['guests']:
                    if guest.get('name'):
                        all_guest_names.add(guest['name'])
                    if guest.get('badge'):
                        all_badges.add(guest['badge'])
        
        return {
            'search_fields': self.search_index_fields,
            'facets': {
                'shows': sorted(list(all_shows)),
                'topics': sorted(list(all_topics)),
                'guests': sorted(list(all_guest_names)),
                'badges': sorted(list(all_badges))
            },
            'total_documents': len(search_documents),
            'last_updated': datetime.now().isoformat()
        }
    
    def _validate_cross_reference_integrity(self, cross_references: Optional[Dict[str, Any]],
                                          show_indices: Dict[str, Any],
                                          host_indices: Dict[str, Any]) -> Dict[str, Any]:
        """Validate cross-reference integrity"""
        validation_result = {
            'consistent': True,
            'orphaned_references': [],
            'missing_references': [],
            'statistics': {}
        }
        
        if not cross_references:
            validation_result['consistent'] = False
            validation_result['missing_references'].append('Cross-references file missing')
            return validation_result
        
        # Check for orphaned show references
        if 'show_to_hosts' in cross_references:
            for show_slug in cross_references['show_to_hosts']:
                if show_slug not in show_indices:
                    validation_result['orphaned_references'].append(f'Show {show_slug} in cross-references but not in indices')
                    validation_result['consistent'] = False
        
        # Check for orphaned host references
        if 'host_to_shows' in cross_references:
            for host_slug in cross_references['host_to_shows']:
                if host_slug not in host_indices:
                    validation_result['orphaned_references'].append(f'Host {host_slug} in cross-references but not in indices')
                    validation_result['consistent'] = False
        
        # Generate statistics
        validation_result['statistics'] = {
            'total_show_references': len(cross_references.get('show_to_hosts', {})),
            'total_host_references': len(cross_references.get('host_to_shows', {})),
            'total_topic_references': len(cross_references.get('topic_to_episodes', {})),
            'orphaned_count': len(validation_result['orphaned_references']),
            'missing_count': len(validation_result['missing_references'])
        }
        
        return validation_result
    
    def _validate_search_integrity(self, episodes: List[EpisodeObject]) -> Dict[str, Any]:
        """Validate search index integrity"""
        validation_result = {
            'consistent': True,
            'missing_documents': [],
            'extra_documents': [],
            'statistics': {}
        }
        
        # Load search index
        search_index_path = self.search_base / 'episodes.json'
        if not search_index_path.exists():
            validation_result['consistent'] = False
            validation_result['missing_documents'].append('Search index file missing')
            return validation_result
        
        try:
            with open(search_index_path, 'r', encoding='utf-8') as f:
                search_documents = json.load(f)
        except Exception as e:
            validation_result['consistent'] = False
            validation_result['missing_documents'].append(f'Failed to load search index: {str(e)}')
            return validation_result
        
        # Get rendered episode IDs
        rendered_episode_ids = {
            ep.episode_id for ep in episodes 
            if ep.processing_stage == ProcessingStage.RENDERED
        }
        
        # Get search document IDs
        search_document_ids = {doc.get('id') for doc in search_documents if doc.get('id')}
        
        # Find missing and extra documents
        missing_ids = rendered_episode_ids - search_document_ids
        extra_ids = search_document_ids - rendered_episode_ids
        
        validation_result['missing_documents'] = list(missing_ids)
        validation_result['extra_documents'] = list(extra_ids)
        
        if missing_ids or extra_ids:
            validation_result['consistent'] = False
        
        # Generate statistics
        validation_result['statistics'] = {
            'total_search_documents': len(search_documents),
            'total_rendered_episodes': len(rendered_episode_ids),
            'missing_count': len(missing_ids),
            'extra_count': len(extra_ids)
        }
        
        return validation_result
    
    def _get_episode_title(self, episode: EpisodeObject) -> str:
        """Get episode title from metadata or editorial content"""
        if episode.metadata.title:
            return episode.metadata.title
        elif episode.editorial and episode.editorial.key_takeaway:
            return episode.editorial.key_takeaway
        elif episode.metadata.topic:
            return episode.metadata.topic
        else:
            return f"{episode.metadata.show_name or 'Episode'} - {episode.episode_id}"
    
    def _create_host_slug(self, name: str) -> str:
        """Create URL-friendly slug from host name"""
        # Convert to lowercase and replace spaces/special chars with hyphens
        slug = re.sub(r'[^\w\s-]', '', name.lower())
        slug = re.sub(r'[-\s]+', '-', slug)
        return slug.strip('-')