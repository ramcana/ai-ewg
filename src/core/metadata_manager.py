"""
Metadata Manager for JSON File Management

Manages JSON metadata files with SQLite index for fast retrieval
and search across 100+ episodes.
"""

import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from .database import DatabaseConnection
from .models import EpisodeObject
from .exceptions import DatabaseError, ValidationError
from .logging import get_logger

logger = get_logger('pipeline.metadata_manager')


class MetadataManager:
    """
    Manage JSON metadata files with SQLite index
    
    Provides fast search and retrieval of episode metadata by maintaining
    a searchable index in SQLite while keeping human-readable JSON files.
    """
    
    def __init__(self, db_connection: DatabaseConnection, json_dir: Path):
        """
        Initialize metadata manager
        
        Args:
            db_connection: Database connection instance
            json_dir: Directory where JSON files are stored
        """
        self.db = db_connection
        self.json_dir = Path(json_dir)
        self.json_dir.mkdir(parents=True, exist_ok=True)
    
    def save_episode_json(self, episode: EpisodeObject) -> Path:
        """
        Save episode as JSON file and update search index
        
        Args:
            episode: Episode object to save
            
        Returns:
            Path to saved JSON file
            
        Raises:
            DatabaseError: If index update fails
        """
        try:
            # Save JSON file
            json_path = self.json_dir / f"{episode.episode_id}.json"
            episode_dict = episode.to_dict()
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(episode_dict, f, indent=2, ensure_ascii=False)
            
            file_size = json_path.stat().st_size
            
            # Extract searchable fields
            guest_names = []
            topics = []
            summary = None
            transcript_text = None
            
            # Extract guests
            if episode.enrichment and episode.enrichment.proficiency_scores:
                scored_people = episode.enrichment.proficiency_scores.get('scored_people', [])
                guest_names = [p.get('name', '') for p in scored_people if p.get('name')]
            
            # Extract topics
            if episode.editorial and episode.editorial.topic_tags:
                topics = episode.editorial.topic_tags
            
            # Extract summary
            if episode.editorial and episode.editorial.summary:
                summary = episode.editorial.summary
            
            # Extract transcript
            if episode.transcription and episode.transcription.text:
                transcript_text = episode.transcription.text
            
            # Update index
            with self.db.transaction() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO json_metadata_index 
                    (episode_id, file_path, file_size, last_updated,
                     show_name, title, date, duration_seconds,
                     guest_names, topics, has_transcript, has_enrichment, has_editorial)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    episode.episode_id,
                    str(json_path),
                    file_size,
                    datetime.now().isoformat(),
                    episode.metadata.show_name,
                    episode.metadata.title or episode.metadata.topic,
                    episode.metadata.date,
                    episode.media.duration_seconds,
                    json.dumps(guest_names),
                    json.dumps(topics),
                    episode.transcription is not None,
                    episode.enrichment is not None,
                    episode.editorial is not None
                ))
                
                # Update FTS index
                conn.execute("""
                    INSERT OR REPLACE INTO episodes_search
                    (episode_id, title, summary, transcript_text, topics, guest_names)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    episode.episode_id,
                    episode.metadata.title or episode.metadata.topic or '',
                    summary or '',
                    transcript_text or '',
                    ' '.join(topics) if topics else '',
                    ' '.join(guest_names) if guest_names else ''
                ))
            
            logger.info("Episode JSON saved and indexed",
                       episode_id=episode.episode_id,
                       file_path=str(json_path),
                       file_size=file_size)
            
            return json_path
            
        except Exception as e:
            logger.error("Failed to save episode JSON",
                        episode_id=episode.episode_id,
                        error=str(e))
            raise DatabaseError(f"Failed to save episode JSON: {e}")
    
    def load_episode_json(self, episode_id: str) -> Dict[str, Any]:
        """
        Load full JSON data for an episode
        
        Args:
            episode_id: Episode identifier
            
        Returns:
            Episode data as dictionary
            
        Raises:
            FileNotFoundError: If episode not found
            DatabaseError: If loading fails
        """
        try:
            cursor = self.db.execute_query(
                "SELECT file_path FROM json_metadata_index WHERE episode_id = ?",
                (episode_id,)
            )
            
            row = cursor.fetchone()
            if not row:
                raise FileNotFoundError(f"Episode not found in index: {episode_id}")
            
            file_path = Path(row[0])
            if not file_path.exists():
                raise FileNotFoundError(f"JSON file not found: {file_path}")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
                
        except FileNotFoundError:
            raise
        except Exception as e:
            logger.error("Failed to load episode JSON",
                        episode_id=episode_id,
                        error=str(e))
            raise DatabaseError(f"Failed to load episode JSON: {e}")
    
    def search_episodes(self, 
                       show_name: Optional[str] = None,
                       date_from: Optional[str] = None,
                       date_to: Optional[str] = None,
                       guest_name: Optional[str] = None,
                       topic: Optional[str] = None,
                       has_transcript: Optional[bool] = None,
                       has_enrichment: Optional[bool] = None,
                       min_duration: Optional[float] = None,
                       max_duration: Optional[float] = None,
                       limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Search episodes with various filters
        
        Args:
            show_name: Filter by show name
            date_from: Filter episodes from this date (inclusive)
            date_to: Filter episodes to this date (inclusive)
            guest_name: Filter by guest name (partial match)
            topic: Filter by topic (partial match)
            has_transcript: Filter by transcript availability
            has_enrichment: Filter by enrichment availability
            min_duration: Minimum duration in seconds
            max_duration: Maximum duration in seconds
            limit: Maximum number of results
            
        Returns:
            List of episode metadata dictionaries
        """
        try:
            query = """
                SELECT episode_id, file_path, show_name, title, date, 
                       duration_seconds, guest_names, topics,
                       has_transcript, has_enrichment, has_editorial
                FROM json_metadata_index 
                WHERE 1=1
            """
            params = []
            
            if show_name:
                query += " AND show_name = ?"
                params.append(show_name)
            
            if date_from:
                query += " AND date >= ?"
                params.append(date_from)
            
            if date_to:
                query += " AND date <= ?"
                params.append(date_to)
            
            if guest_name:
                query += " AND guest_names LIKE ?"
                params.append(f'%{guest_name}%')
            
            if topic:
                query += " AND topics LIKE ?"
                params.append(f'%{topic}%')
            
            if has_transcript is not None:
                query += " AND has_transcript = ?"
                params.append(1 if has_transcript else 0)
            
            if has_enrichment is not None:
                query += " AND has_enrichment = ?"
                params.append(1 if has_enrichment else 0)
            
            if min_duration is not None:
                query += " AND duration_seconds >= ?"
                params.append(min_duration)
            
            if max_duration is not None:
                query += " AND duration_seconds <= ?"
                params.append(max_duration)
            
            query += " ORDER BY date DESC"
            
            if limit:
                query += f" LIMIT {int(limit)}"
            
            cursor = self.db.execute_query(query, tuple(params))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'episode_id': row[0],
                    'file_path': row[1],
                    'show_name': row[2],
                    'title': row[3],
                    'date': row[4],
                    'duration_seconds': row[5],
                    'guest_names': json.loads(row[6]) if row[6] else [],
                    'topics': json.loads(row[7]) if row[7] else [],
                    'has_transcript': bool(row[8]),
                    'has_enrichment': bool(row[9]),
                    'has_editorial': bool(row[10])
                })
            
            logger.debug("Episode search completed",
                        filters={
                            'show_name': show_name,
                            'date_from': date_from,
                            'guest_name': guest_name,
                            'topic': topic
                        },
                        results_count=len(results))
            
            return results
            
        except Exception as e:
            logger.error("Episode search failed", error=str(e))
            raise DatabaseError(f"Episode search failed: {e}")
    
    def full_text_search(self, query: str, limit: Optional[int] = 20) -> List[Dict[str, Any]]:
        """
        Full-text search across titles, summaries, transcripts, topics, and guests
        
        Args:
            query: Search query string
            limit: Maximum number of results
            
        Returns:
            List of matching episodes with metadata
        """
        try:
            cursor = self.db.execute_query("""
                SELECT 
                    es.episode_id,
                    jmi.file_path,
                    jmi.show_name,
                    jmi.title,
                    jmi.date,
                    jmi.duration_seconds,
                    jmi.guest_names,
                    jmi.topics
                FROM episodes_search es
                JOIN json_metadata_index jmi ON es.episode_id = jmi.episode_id
                WHERE episodes_search MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (query, limit or 20))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'episode_id': row[0],
                    'file_path': row[1],
                    'show_name': row[2],
                    'title': row[3],
                    'date': row[4],
                    'duration_seconds': row[5],
                    'guest_names': json.loads(row[6]) if row[6] else [],
                    'topics': json.loads(row[7]) if row[7] else []
                })
            
            logger.info("Full-text search completed",
                       query=query,
                       results_count=len(results))
            
            return results
            
        except Exception as e:
            logger.error("Full-text search failed",
                        query=query,
                        error=str(e))
            raise DatabaseError(f"Full-text search failed: {e}")
    
    def get_shows(self) -> List[Dict[str, Any]]:
        """
        Get list of all shows with episode counts
        
        Returns:
            List of shows with metadata
        """
        try:
            cursor = self.db.execute_query("""
                SELECT 
                    show_name,
                    COUNT(*) as episode_count,
                    MIN(date) as first_episode,
                    MAX(date) as latest_episode,
                    SUM(duration_seconds) as total_duration
                FROM json_metadata_index
                WHERE show_name IS NOT NULL
                GROUP BY show_name
                ORDER BY show_name
            """)
            
            shows = []
            for row in cursor.fetchall():
                shows.append({
                    'show_name': row[0],
                    'episode_count': row[1],
                    'first_episode': row[2],
                    'latest_episode': row[3],
                    'total_duration_seconds': row[4]
                })
            
            return shows
            
        except Exception as e:
            logger.error("Failed to get shows list", error=str(e))
            raise DatabaseError(f"Failed to get shows list: {e}")
    
    def get_guests(self, min_appearances: int = 2) -> List[Dict[str, Any]]:
        """
        Get list of all guests with appearance counts
        
        Args:
            min_appearances: Minimum number of appearances to include
            
        Returns:
            List of guests with metadata
        """
        try:
            cursor = self.db.execute_query("""
                SELECT episode_id, guest_names 
                FROM json_metadata_index 
                WHERE guest_names IS NOT NULL AND guest_names != '[]'
            """)
            
            guest_counts = {}
            guest_episodes = {}
            
            for row in cursor.fetchall():
                episode_id = row[0]
                guests = json.loads(row[1])
                
                for guest in guests:
                    if guest not in guest_counts:
                        guest_counts[guest] = 0
                        guest_episodes[guest] = []
                    guest_counts[guest] += 1
                    guest_episodes[guest].append(episode_id)
            
            # Filter and format results
            guests = []
            for guest_name, count in guest_counts.items():
                if count >= min_appearances:
                    guests.append({
                        'name': guest_name,
                        'appearances': count,
                        'episodes': guest_episodes[guest_name]
                    })
            
            # Sort by appearances (descending)
            guests.sort(key=lambda x: x['appearances'], reverse=True)
            
            return guests
            
        except Exception as e:
            logger.error("Failed to get guests list", error=str(e))
            raise DatabaseError(f"Failed to get guests list: {e}")
    
    def get_topics(self, min_occurrences: int = 2) -> List[Dict[str, Any]]:
        """
        Get list of all topics with occurrence counts
        
        Args:
            min_occurrences: Minimum number of occurrences to include
            
        Returns:
            List of topics with metadata
        """
        try:
            cursor = self.db.execute_query("""
                SELECT episode_id, topics 
                FROM json_metadata_index 
                WHERE topics IS NOT NULL AND topics != '[]'
            """)
            
            topic_counts = {}
            topic_episodes = {}
            
            for row in cursor.fetchall():
                episode_id = row[0]
                topics = json.loads(row[1])
                
                for topic in topics:
                    if topic not in topic_counts:
                        topic_counts[topic] = 0
                        topic_episodes[topic] = []
                    topic_counts[topic] += 1
                    topic_episodes[topic].append(episode_id)
            
            # Filter and format results
            topics = []
            for topic_name, count in topic_counts.items():
                if count >= min_occurrences:
                    topics.append({
                        'topic': topic_name,
                        'occurrences': count,
                        'episodes': topic_episodes[topic_name]
                    })
            
            # Sort by occurrences (descending)
            topics.sort(key=lambda x: x['occurrences'], reverse=True)
            
            return topics
            
        except Exception as e:
            logger.error("Failed to get topics list", error=str(e))
            raise DatabaseError(f"Failed to get topics list: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get overall statistics about the metadata collection
        
        Returns:
            Dictionary with statistics
        """
        try:
            cursor = self.db.execute_query("""
                SELECT 
                    COUNT(*) as total_episodes,
                    COUNT(DISTINCT show_name) as total_shows,
                    SUM(duration_seconds) as total_duration,
                    AVG(duration_seconds) as avg_duration,
                    SUM(has_transcript) as episodes_with_transcript,
                    SUM(has_enrichment) as episodes_with_enrichment,
                    SUM(has_editorial) as episodes_with_editorial,
                    MIN(date) as earliest_date,
                    MAX(date) as latest_date
                FROM json_metadata_index
            """)
            
            row = cursor.fetchone()
            
            return {
                'total_episodes': row[0] or 0,
                'total_shows': row[1] or 0,
                'total_duration_seconds': row[2] or 0,
                'average_duration_seconds': row[3] or 0,
                'episodes_with_transcript': row[4] or 0,
                'episodes_with_enrichment': row[5] or 0,
                'episodes_with_editorial': row[6] or 0,
                'earliest_date': row[7],
                'latest_date': row[8]
            }
            
        except Exception as e:
            logger.error("Failed to get statistics", error=str(e))
            raise DatabaseError(f"Failed to get statistics: {e}")
    
    def rebuild_index(self) -> int:
        """
        Rebuild the metadata index from existing JSON files
        
        Returns:
            Number of files indexed
            
        Raises:
            DatabaseError: If rebuild fails
        """
        try:
            logger.info("Starting metadata index rebuild",
                       json_dir=str(self.json_dir))
            
            indexed_count = 0
            
            # Find all JSON files
            json_files = list(self.json_dir.glob("*.json"))
            
            for json_path in json_files:
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        episode_dict = json.load(f)
                    
                    # Reconstruct EpisodeObject
                    episode = EpisodeObject.from_dict(episode_dict)
                    
                    # Save to index
                    self.save_episode_json(episode)
                    indexed_count += 1
                    
                except Exception as e:
                    logger.warning("Failed to index file",
                                 file_path=str(json_path),
                                 error=str(e))
            
            logger.info("Metadata index rebuild completed",
                       indexed_count=indexed_count,
                       total_files=len(json_files))
            
            return indexed_count
            
        except Exception as e:
            logger.error("Metadata index rebuild failed", error=str(e))
            raise DatabaseError(f"Metadata index rebuild failed: {e}")


# Utility functions
def create_metadata_manager(db_connection: DatabaseConnection, 
                           json_dir: Path) -> MetadataManager:
    """Factory function to create metadata manager"""
    return MetadataManager(db_connection, json_dir)
