"""Registry database operations."""

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from sqlmodel import Session, SQLModel, create_engine, select
from .models import (
    Episode, EpisodeState, Artifact, ArtifactKind,
    Person, EntityMention, ProcessingRun, EntityCache
)


class Registry:
    """Central registry for pipeline state."""
    
    def __init__(self, db_path: Path):
        """Initialize registry with database path."""
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # SQLite with WAL mode for better concurrency
        self.engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
            echo=False
        )
        
    def init_db(self):
        """Create all tables."""
        SQLModel.metadata.create_all(self.engine)
        
        # Enable WAL mode for better concurrency
        with Session(self.engine) as session:
            session.exec("PRAGMA journal_mode=WAL")
            session.exec("PRAGMA synchronous=NORMAL")
            session.exec("PRAGMA cache_size=-64000")  # 64MB cache
            session.commit()
    
    def get_session(self) -> Session:
        """Get a new database session."""
        return Session(self.engine)
    
    # Episode operations
    def register_episode(
        self,
        abs_path: Path,
        show: str,
        show_slug: str,
        episode_id: str,
        episode_title: Optional[str] = None,
        episode_date: Optional[datetime] = None,
    ) -> Episode:
        """Register or update an episode."""
        with self.get_session() as session:
            # Check if exists
            statement = select(Episode).where(Episode.episode_id == episode_id)
            episode = session.exec(statement).first()
            
            # Compute file hash and stats
            sha256 = self._compute_sha256(abs_path)
            stat = abs_path.stat()
            
            if episode:
                # Update if changed
                if episode.sha256 != sha256 or episode.mtime != datetime.fromtimestamp(stat.st_mtime):
                    episode.sha256 = sha256
                    episode.size_bytes = stat.st_size
                    episode.mtime = datetime.fromtimestamp(stat.st_mtime)
                    episode.updated_at = datetime.utcnow()
                    episode.state = EpisodeState.NEW  # Reset state on change
                    session.add(episode)
                    session.commit()
                    session.refresh(episode)
            else:
                # Create new
                episode = Episode(
                    episode_id=episode_id,
                    abs_path=str(abs_path),
                    sha256=sha256,
                    size_bytes=stat.st_size,
                    mtime=datetime.fromtimestamp(stat.st_mtime),
                    show=show,
                    show_slug=show_slug,
                    episode_title=episode_title,
                    episode_date=episode_date,
                    state=EpisodeState.NEW,
                )
                session.add(episode)
                session.commit()
                session.refresh(episode)
            
            return episode
    
    def get_episode(self, episode_id: str) -> Optional[Episode]:
        """Get episode by ID."""
        with self.get_session() as session:
            statement = select(Episode).where(Episode.episode_id == episode_id)
            return session.exec(statement).first()
    
    def get_episodes_by_state(self, state: EpisodeState, limit: Optional[int] = None) -> list[Episode]:
        """Get episodes in a specific state."""
        with self.get_session() as session:
            statement = select(Episode).where(Episode.state == state)
            if limit:
                statement = statement.limit(limit)
            return list(session.exec(statement).all())
    
    def update_episode_state(
        self,
        episode_id: str,
        state: EpisodeState,
        error: Optional[str] = None
    ):
        """Update episode processing state."""
        with self.get_session() as session:
            statement = select(Episode).where(Episode.episode_id == episode_id)
            episode = session.exec(statement).first()
            
            if episode:
                episode.state = state
                episode.updated_at = datetime.utcnow()
                
                if state == EpisodeState.ERROR:
                    episode.last_error = error
                    episode.retry_count += 1
                elif state == EpisodeState.RENDERED:
                    episode.processed_at = datetime.utcnow()
                    episode.last_error = None
                
                session.add(episode)
                session.commit()
    
    # Artifact operations
    def register_artifact(
        self,
        episode_id: str,
        kind: ArtifactKind,
        rel_path: Path,
        duration_ms: Optional[int] = None,
        model_version: Optional[str] = None,
    ) -> Artifact:
        """Register a generated artifact."""
        with self.get_session() as session:
            # Get episode
            statement = select(Episode).where(Episode.episode_id == episode_id)
            episode = session.exec(statement).first()
            
            if not episode:
                raise ValueError(f"Episode {episode_id} not found")
            
            # Compute artifact hash
            full_path = Path(rel_path)
            sha256 = self._compute_sha256(full_path) if full_path.exists() else None
            size_bytes = full_path.stat().st_size if full_path.exists() else None
            
            artifact = Artifact(
                episode_id=episode.id,
                kind=kind,
                rel_path=str(rel_path),
                sha256=sha256,
                size_bytes=size_bytes,
                duration_ms=duration_ms,
                model_version=model_version,
            )
            
            session.add(artifact)
            session.commit()
            session.refresh(artifact)
            
            return artifact
    
    # Person operations
    def get_or_create_person(
        self,
        name: str,
        norm_name: str,
        wikidata_id: Optional[str] = None,
        confidence: float = 0.0,
    ) -> Person:
        """Get or create a person entity."""
        with self.get_session() as session:
            # Try by wikidata_id first
            if wikidata_id:
                statement = select(Person).where(Person.wikidata_id == wikidata_id)
                person = session.exec(statement).first()
                if person:
                    person.last_seen_at = datetime.utcnow()
                    person.mention_count += 1
                    session.add(person)
                    session.commit()
                    session.refresh(person)
                    return person
            
            # Try by normalized name
            statement = select(Person).where(Person.norm_name == norm_name)
            person = session.exec(statement).first()
            
            if person:
                person.last_seen_at = datetime.utcnow()
                person.mention_count += 1
                session.add(person)
                session.commit()
                session.refresh(person)
            else:
                person = Person(
                    name=name,
                    norm_name=norm_name,
                    wikidata_id=wikidata_id,
                    confidence=confidence,
                    mention_count=1,
                )
                session.add(person)
                session.commit()
                session.refresh(person)
            
            return person
    
    # Cache operations
    def get_cached_entity(self, norm_name: str) -> Optional[EntityCache]:
        """Get cached entity lookup."""
        with self.get_session() as session:
            statement = select(EntityCache).where(EntityCache.norm_name == norm_name)
            cache = session.exec(statement).first()
            
            if cache:
                cache.hit_count += 1
                cache.last_used_at = datetime.utcnow()
                session.add(cache)
                session.commit()
                session.refresh(cache)
            
            return cache
    
    def cache_entity(
        self,
        norm_name: str,
        wikidata_id: Optional[str],
        wikipedia_url: Optional[str],
        metadata_json: Optional[str],
        confidence: float,
    ) -> EntityCache:
        """Cache an entity lookup result."""
        with self.get_session() as session:
            cache = EntityCache(
                norm_name=norm_name,
                wikidata_id=wikidata_id,
                wikipedia_url=wikipedia_url,
                metadata_json=metadata_json,
                confidence=confidence,
            )
            session.add(cache)
            session.commit()
            session.refresh(cache)
            return cache
    
    # Stats operations
    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        with self.get_session() as session:
            stats = {
                "episodes": session.exec(select(Episode)).all().__len__(),
                "artifacts": session.exec(select(Artifact)).all().__len__(),
                "people": session.exec(select(Person)).all().__len__(),
                "runs": session.exec(select(ProcessingRun)).all().__len__(),
            }
            
            # State breakdown
            for state in EpisodeState:
                count = session.exec(
                    select(Episode).where(Episode.state == state)
                ).all().__len__()
                stats[f"state_{state.value.lower()}"] = count
            
            return stats
    
    @staticmethod
    def _compute_sha256(path: Path, chunk_size: int = 8192) -> str:
        """Compute SHA256 hash of a file."""
        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(chunk_size):
                sha256.update(chunk)
        return sha256.hexdigest()


# Convenience functions
def init_database(settings):
    """Initialize the database."""
    registry = Registry(settings.registry_db_path)
    registry.init_db()


def get_registry_stats(settings) -> Dict[str, Any]:
    """Get registry statistics."""
    registry = Registry(settings.registry_db_path)
    return registry.get_stats()


def run_migrations(settings) -> Dict[str, Any]:
    """Run database migrations (placeholder for future)."""
    # For now, just ensure tables exist
    registry = Registry(settings.registry_db_path)
    registry.init_db()
    return {"count": 0, "message": "No migrations to apply"}
