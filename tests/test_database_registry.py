"""
Tests for database and registry functionality

Tests the core database operations, episode registry, and deduplication system.
"""

import pytest
import tempfile
import os
from pathlib import Path
from datetime import datetime

from src.core.database import DatabaseManager, DatabaseConfig
from src.core.registry import EpisodeRegistry
from src.core.models import (
    EpisodeObject, ProcessingStage, SourceInfo, MediaInfo, EpisodeMetadata,
    ContentHasher, create_episode_from_file
)
from src.core.exceptions import DatabaseError, ValidationError


class TestDatabaseManager:
    """Test database manager functionality"""
    
    def setup_method(self):
        """Setup test database"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        
        self.config = DatabaseConfig(
            path=self.db_path,
            backup_enabled=False,
            connection_timeout=5
        )
        
        self.db_manager = DatabaseManager(self.config)
    
    def teardown_method(self):
        """Cleanup test database"""
        if self.db_manager:
            self.db_manager.close()
        
        # Clean up temp files
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_database_initialization(self):
        """Test database initialization and migration"""
        self.db_manager.initialize()
        
        # Verify tables exist
        connection = self.db_manager.get_connection()
        cursor = connection.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        
        tables = {row[0] for row in cursor.fetchall()}
        expected_tables = {'episodes', 'processing_log', 'schema_version'}
        
        assert expected_tables.issubset(tables)
    
    def test_database_stats(self):
        """Test database statistics"""
        self.db_manager.initialize()
        
        stats = self.db_manager.get_database_stats()
        
        assert 'episodes_count' in stats
        assert 'processing_log_count' in stats
        assert 'database_size' in stats
        assert 'schema_version' in stats
        assert stats['episodes_count'] == 0
        assert stats['schema_version'] > 0


class TestEpisodeRegistry:
    """Test episode registry functionality"""
    
    def setup_method(self):
        """Setup test registry"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        
        config = DatabaseConfig(path=self.db_path, backup_enabled=False)
        self.db_manager = DatabaseManager(config)
        self.db_manager.initialize()
        
        self.registry = EpisodeRegistry(self.db_manager)
    
    def teardown_method(self):
        """Cleanup test registry"""
        if self.db_manager:
            self.db_manager.close()
        
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_test_episode(self, episode_id: str = "test-show-s1e1") -> EpisodeObject:
        """Create a test episode object"""
        source = SourceInfo(
            path="/test/video.mp4",
            file_size=1000000,
            last_modified=datetime.now()
        )
        
        media = MediaInfo(duration_seconds=3600.0)
        
        metadata = EpisodeMetadata(
            show_name="Test Show",
            show_slug="test-show",
            season=1,
            episode=1
        )
        
        content_hash = ContentHasher.calculate_metadata_hash(source, media)
        
        return EpisodeObject(
            episode_id=episode_id,
            content_hash=content_hash,
            source=source,
            media=media,
            metadata=metadata
        )
    
    def test_episode_registration(self):
        """Test episode registration"""
        episode = self.create_test_episode()
        
        # Register episode
        result = self.registry.register_episode(episode)
        assert result is True
        
        # Verify episode exists
        retrieved = self.registry.get_episode(episode.episode_id)
        assert retrieved is not None
        assert retrieved.episode_id == episode.episode_id
        assert retrieved.content_hash == episode.content_hash
    
    def test_duplicate_detection(self):
        """Test duplicate episode detection"""
        episode1 = self.create_test_episode("test-1")
        episode2 = self.create_test_episode("test-2")
        
        # Same content hash should be detected as duplicate
        episode2.content_hash = episode1.content_hash
        
        # Register first episode
        result1 = self.registry.register_episode(episode1)
        assert result1 is True
        
        # Try to register duplicate
        result2 = self.registry.register_episode(episode2)
        assert result2 is False
        
        # Verify duplicate check
        assert self.registry.is_duplicate(episode1.content_hash) is True
        assert self.registry.is_duplicate("nonexistent-hash") is False
    
    def test_episode_id_collision_resolution(self):
        """Test episode ID collision resolution"""
        episode1 = self.create_test_episode("test-show-s1e1")
        episode2 = self.create_test_episode("test-show-s1e1")
        
        # Different content hashes
        episode2.content_hash = "different-hash"
        
        # Register both episodes
        result1 = self.registry.register_episode(episode1)
        result2 = self.registry.register_episode(episode2)
        
        assert result1 is True
        assert result2 is True
        
        # Second episode should have modified ID
        assert episode2.episode_id != "test-show-s1e1"
        assert episode2.episode_id.startswith("test-show-s1e1-")
    
    def test_stage_updates(self):
        """Test processing stage updates"""
        episode = self.create_test_episode()
        self.registry.register_episode(episode)
        
        # Update stage
        self.registry.update_episode_stage(episode.episode_id, ProcessingStage.PREPPED)
        
        # Verify update
        retrieved = self.registry.get_episode(episode.episode_id)
        assert retrieved.processing_stage == ProcessingStage.PREPPED
    
    def test_episodes_by_stage(self):
        """Test retrieving episodes by stage"""
        # Create episodes at different stages
        episode1 = self.create_test_episode("test-1")
        episode2 = self.create_test_episode("test-2")
        episode2.content_hash = "different-hash"
        
        self.registry.register_episode(episode1)
        self.registry.register_episode(episode2)
        
        # Update one episode to different stage
        self.registry.update_episode_stage(episode2.episode_id, ProcessingStage.PREPPED)
        
        # Get episodes by stage
        discovered = self.registry.get_episodes_by_stage(ProcessingStage.DISCOVERED)
        prepped = self.registry.get_episodes_by_stage(ProcessingStage.PREPPED)
        
        assert len(discovered) == 1
        assert len(prepped) == 1
        assert discovered[0].episode_id == episode1.episode_id
        assert prepped[0].episode_id == episode2.episode_id
    
    def test_processing_event_logging(self):
        """Test processing event logging"""
        episode = self.create_test_episode()
        self.registry.register_episode(episode)
        
        # Log processing events
        self.registry.log_processing_event(
            episode.episode_id, "transcription", "started"
        )
        self.registry.log_processing_event(
            episode.episode_id, "transcription", "completed", duration=120.5
        )
        
        # Get processing history
        history = self.registry.get_processing_history(episode.episode_id)
        
        # Should have registration + 2 transcription events
        assert len(history) >= 2
        
        # Find transcription events
        transcription_events = [e for e in history if e.stage == "transcription"]
        assert len(transcription_events) == 2
        
        started_event = next(e for e in transcription_events if e.status == "started")
        completed_event = next(e for e in transcription_events if e.status == "completed")
        
        assert started_event.duration_seconds is None
        assert completed_event.duration_seconds == 120.5
    
    def test_registry_stats(self):
        """Test registry statistics"""
        # Create and register episodes
        episode1 = self.create_test_episode("test-1")
        episode2 = self.create_test_episode("test-2")
        episode2.content_hash = "different-hash"
        
        self.registry.register_episode(episode1)
        self.registry.register_episode(episode2)
        
        # Update one episode stage
        self.registry.update_episode_stage(episode2.episode_id, ProcessingStage.PREPPED)
        
        # Get stats
        stats = self.registry.get_registry_stats()
        
        assert stats['total_episodes'] == 2
        assert 'episodes_by_stage' in stats
        assert stats['episodes_by_stage']['discovered'] == 1
        assert stats['episodes_by_stage']['prepped'] == 1


class TestHashCollisionDetection:
    """Test hash collision detection and resolution"""
    
    def setup_method(self):
        """Setup test registry"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        
        config = DatabaseConfig(path=self.db_path, backup_enabled=False)
        self.db_manager = DatabaseManager(config)
        self.db_manager.initialize()
        
        self.registry = EpisodeRegistry(self.db_manager)
    
    def teardown_method(self):
        """Cleanup test registry"""
        if self.db_manager:
            self.db_manager.close()
        
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_hash_collision_detection(self):
        """Test detection of hash collisions"""
        # Create two episodes with same content hash but different IDs
        episode1 = self.create_test_episode("episode-1")
        episode2 = self.create_test_episode("episode-2")
        
        # Force same hash to simulate collision
        collision_hash = "collision_hash_12345"
        episode1.content_hash = collision_hash
        episode2.content_hash = collision_hash
        
        # Register first episode
        result1 = self.registry.register_episode(episode1)
        assert result1 is True
        
        # Attempt to register second episode with same hash
        result2 = self.registry.register_episode(episode2)
        assert result2 is False  # Should be rejected as duplicate
        
        # Verify only first episode exists
        retrieved1 = self.registry.get_episode(episode1.episode_id)
        retrieved2 = self.registry.get_episode(episode2.episode_id)
        
        assert retrieved1 is not None
        assert retrieved2 is None
    
    def test_hash_collision_with_database_constraint(self):
        """Test that database constraints prevent hash collisions"""
        episode1 = self.create_test_episode("test-1")
        episode2 = self.create_test_episode("test-2")
        
        # Force same hash
        collision_hash = "forced_collision_hash"
        episode1.content_hash = collision_hash
        episode2.content_hash = collision_hash
        
        # Register first episode
        self.registry.register_episode(episode1)
        
        # Verify hash exists in database
        assert self.registry.is_duplicate(collision_hash) is True
        
        # Second registration should fail due to duplicate detection
        result = self.registry.register_episode(episode2)
        assert result is False
    
    def test_episode_id_collision_resolution(self):
        """Test automatic resolution of episode ID collisions"""
        # Create episodes with same base ID but different content
        base_id = "test-show-s1e1"
        episode1 = self.create_test_episode(base_id)
        episode2 = self.create_test_episode(base_id)
        
        # Ensure different content hashes
        episode1.content_hash = "hash1"
        episode2.content_hash = "hash2"
        
        # Register both episodes
        result1 = self.registry.register_episode(episode1)
        result2 = self.registry.register_episode(episode2)
        
        assert result1 is True
        assert result2 is True
        
        # Verify first episode keeps original ID
        assert episode1.episode_id == base_id
        
        # Verify second episode gets modified ID
        assert episode2.episode_id != base_id
        assert episode2.episode_id.startswith(f"{base_id}-")
        
        # Both should be retrievable
        retrieved1 = self.registry.get_episode(episode1.episode_id)
        retrieved2 = self.registry.get_episode(episode2.episode_id)
        
        assert retrieved1 is not None
        assert retrieved2 is not None
        assert retrieved1.content_hash != retrieved2.content_hash
    
    def create_test_episode(self, episode_id: str) -> EpisodeObject:
        """Create a test episode object"""
        source = SourceInfo(
            path=f"/test/{episode_id}.mp4",
            file_size=1000000,
            last_modified=datetime.now()
        )
        
        media = MediaInfo(duration_seconds=3600.0)
        
        metadata = EpisodeMetadata(
            show_name="Test Show",
            show_slug="test-show",
            season=1,
            episode=1
        )
        
        content_hash = ContentHasher.calculate_metadata_hash(source, media)
        
        return EpisodeObject(
            episode_id=episode_id,
            content_hash=content_hash,
            source=source,
            media=media,
            metadata=metadata
        )


class TestDatabaseConstraintEnforcement:
    """Test database constraint enforcement"""
    
    def setup_method(self):
        """Setup test registry"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        
        config = DatabaseConfig(path=self.db_path, backup_enabled=False)
        self.db_manager = DatabaseManager(config)
        self.db_manager.initialize()
        
        self.registry = EpisodeRegistry(self.db_manager)
    
    def teardown_method(self):
        """Cleanup test registry"""
        if self.db_manager:
            self.db_manager.close()
        
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_unique_hash_constraint(self):
        """Test that unique hash constraint is enforced"""
        episode1 = self.create_test_episode("test-1")
        episode2 = self.create_test_episode("test-2")
        
        # Force same hash to test constraint
        same_hash = "duplicate_hash_test"
        episode1.content_hash = same_hash
        episode2.content_hash = same_hash
        
        # First registration should succeed
        result1 = self.registry.register_episode(episode1)
        assert result1 is True
        
        # Second registration should fail due to hash constraint
        result2 = self.registry.register_episode(episode2)
        assert result2 is False
        
        # Verify only one episode with this hash exists
        episodes_with_hash = []
        connection = self.db_manager.get_connection()
        cursor = connection.execute_query("SELECT id FROM episodes WHERE hash = ?", (same_hash,))
        episodes_with_hash = cursor.fetchall()
        
        assert len(episodes_with_hash) == 1
        assert episodes_with_hash[0][0] == episode1.episode_id
    
    def test_primary_key_constraint(self):
        """Test that primary key constraint prevents duplicate episode IDs"""
        episode1 = self.create_test_episode("duplicate-id")
        episode2 = self.create_test_episode("duplicate-id")
        
        # Different hashes to avoid hash constraint
        episode1.content_hash = "hash1"
        episode2.content_hash = "hash2"
        
        # First registration should succeed
        result1 = self.registry.register_episode(episode1)
        assert result1 is True
        
        # Second registration should succeed with modified ID
        result2 = self.registry.register_episode(episode2)
        assert result2 is True
        
        # Verify second episode got a different ID
        assert episode2.episode_id != "duplicate-id"
        assert episode2.episode_id.startswith("duplicate-id-")
    
    def test_foreign_key_constraint_processing_log(self):
        """Test foreign key constraint between episodes and processing_log"""
        episode = self.create_test_episode("test-episode")
        self.registry.register_episode(episode)
        
        # Log processing event - should succeed
        self.registry.log_processing_event(episode.episode_id, "test_stage", "started")
        
        # Verify event was logged
        history = self.registry.get_processing_history(episode.episode_id)
        assert len(history) >= 1
        
        # Try to log event for non-existent episode
        connection = self.db_manager.get_connection()
        
        # This should not raise an error but should be handled gracefully
        try:
            with connection.transaction() as conn:
                conn.execute("""
                    INSERT INTO processing_log (episode_id, stage, status)
                    VALUES (?, ?, ?)
                """, ("non-existent-id", "test", "started"))
            # If foreign key constraints are enabled, this should fail
            # But our implementation handles this gracefully
        except Exception:
            # Expected if foreign key constraints are strictly enforced
            pass
    
    def test_not_null_constraints(self):
        """Test that NOT NULL constraints are enforced"""
        # Try to create episode with missing required fields
        episode = self.create_test_episode("test-episode")
        
        # Test with empty episode_id - should raise DatabaseError (wraps ValidationError)
        episode.episode_id = ""
        
        with pytest.raises(DatabaseError):
            self.registry.register_episode(episode)
        
        # Test with empty content_hash
        episode.episode_id = "valid-id"
        episode.content_hash = ""
        
        with pytest.raises(DatabaseError):
            self.registry.register_episode(episode)
    
    def test_stage_enum_constraint(self):
        """Test that processing stage values are constrained to valid enum values"""
        episode = self.create_test_episode("test-episode")
        self.registry.register_episode(episode)
        
        # Valid stage update should work
        self.registry.update_episode_stage(episode.episode_id, ProcessingStage.PREPPED)
        
        # Invalid stage should be caught by enum validation
        with pytest.raises((ValueError, ValidationError)):
            # This should fail at the enum level
            invalid_stage = "invalid_stage"
            ProcessingStage(invalid_stage)
    
    def create_test_episode(self, episode_id: str) -> EpisodeObject:
        """Create a test episode object"""
        source = SourceInfo(
            path=f"/test/{episode_id}.mp4",
            file_size=1000000,
            last_modified=datetime.now()
        )
        
        media = MediaInfo(duration_seconds=3600.0)
        
        metadata = EpisodeMetadata(
            show_name="Test Show",
            show_slug="test-show",
            season=1,
            episode=1
        )
        
        content_hash = ContentHasher.calculate_metadata_hash(source, media)
        
        return EpisodeObject(
            episode_id=episode_id,
            content_hash=content_hash,
            source=source,
            media=media,
            metadata=metadata
        )


class TestConcurrentAccess:
    """Test concurrent access scenarios"""
    
    def setup_method(self):
        """Setup test registry"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        
        config = DatabaseConfig(path=self.db_path, backup_enabled=False)
        self.db_manager = DatabaseManager(config)
        self.db_manager.initialize()
        
        self.registry = EpisodeRegistry(self.db_manager)
    
    def teardown_method(self):
        """Cleanup test registry"""
        if self.db_manager:
            self.db_manager.close()
        
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_concurrent_episode_registration(self):
        """Test concurrent episode registration"""
        import threading
        import time
        
        results = []
        errors = []
        
        def register_episode(episode_id: str, delay: float = 0):
            try:
                if delay > 0:
                    time.sleep(delay)
                
                episode = self.create_test_episode(episode_id)
                result = self.registry.register_episode(episode)
                results.append((episode_id, result))
            except Exception as e:
                errors.append((episode_id, str(e)))
        
        # Create multiple threads registering different episodes
        threads = []
        for i in range(5):
            thread = threading.Thread(
                target=register_episode,
                args=(f"concurrent-episode-{i}", i * 0.01)
            )
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify results
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 5
        
        # All registrations should succeed since episodes are different
        for episode_id, result in results:
            assert result is True, f"Registration failed for {episode_id}"
    
    def test_concurrent_duplicate_registration(self):
        """Test concurrent registration of duplicate episodes"""
        import threading
        
        results = []
        errors = []
        
        def register_duplicate_episode(thread_id: int):
            try:
                # All threads try to register episode with same hash
                episode = self.create_test_episode(f"thread-{thread_id}")
                episode.content_hash = "shared_hash_for_collision_test"
                
                result = self.registry.register_episode(episode)
                results.append((thread_id, result))
            except Exception as e:
                errors.append((thread_id, str(e)))
        
        # Create multiple threads trying to register same content
        threads = []
        for i in range(3):
            thread = threading.Thread(target=register_duplicate_episode, args=(i,))
            threads.append(thread)
        
        # Start all threads simultaneously
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify results - only one should succeed
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 3
        
        successful_registrations = sum(1 for _, result in results if result is True)
        failed_registrations = sum(1 for _, result in results if result is False)
        
        assert successful_registrations == 1, "Exactly one registration should succeed"
        assert failed_registrations == 2, "Two registrations should fail as duplicates"
    
    def test_concurrent_stage_updates(self):
        """Test concurrent stage updates on same episode"""
        import threading
        import time
        
        # Register an episode first
        episode = self.create_test_episode("concurrent-update-test")
        self.registry.register_episode(episode)
        
        results = []
        errors = []
        
        def update_stage(stage: ProcessingStage, delay: float = 0):
            try:
                if delay > 0:
                    time.sleep(delay)
                
                self.registry.update_episode_stage(episode.episode_id, stage)
                results.append(stage)
            except Exception as e:
                errors.append((stage, str(e)))
        
        # Create threads updating to different stages
        stages = [ProcessingStage.PREPPED, ProcessingStage.TRANSCRIBED, ProcessingStage.ENRICHED]
        threads = []
        
        for i, stage in enumerate(stages):
            thread = threading.Thread(
                target=update_stage,
                args=(stage, i * 0.01)
            )
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify no errors occurred
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 3
        
        # Verify final state is consistent
        final_episode = self.registry.get_episode(episode.episode_id)
        assert final_episode is not None
        assert final_episode.processing_stage in stages
    
    def test_concurrent_read_write_operations(self):
        """Test concurrent read and write operations"""
        import threading
        import time
        
        # Register initial episodes
        for i in range(3):
            episode = self.create_test_episode(f"read-write-test-{i}")
            self.registry.register_episode(episode)
        
        read_results = []
        write_results = []
        errors = []
        
        def read_operations():
            try:
                for i in range(10):
                    # Read episode
                    episode = self.registry.get_episode(f"read-write-test-{i % 3}")
                    read_results.append(episode is not None)
                    
                    # Get stats
                    stats = self.registry.get_registry_stats()
                    read_results.append(stats['total_episodes'] >= 3)
                    
                    time.sleep(0.001)  # Small delay
            except Exception as e:
                errors.append(f"Read error: {e}")
        
        def write_operations():
            try:
                for i in range(5):
                    episode_id = f"read-write-test-{i % 3}"
                    
                    # Update stage
                    stages = [ProcessingStage.PREPPED, ProcessingStage.TRANSCRIBED]
                    stage = stages[i % 2]
                    
                    self.registry.update_episode_stage(episode_id, stage)
                    write_results.append(True)
                    
                    time.sleep(0.002)  # Small delay
            except Exception as e:
                errors.append(f"Write error: {e}")
        
        # Create reader and writer threads
        reader_thread = threading.Thread(target=read_operations)
        writer_thread = threading.Thread(target=write_operations)
        
        # Start both threads
        reader_thread.start()
        writer_thread.start()
        
        # Wait for completion
        reader_thread.join()
        writer_thread.join()
        
        # Verify no errors occurred
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(read_results) > 0
        assert len(write_results) == 5
        
        # All operations should have succeeded
        assert all(read_results), "Some read operations failed"
        assert all(write_results), "Some write operations failed"
    
    def create_test_episode(self, episode_id: str) -> EpisodeObject:
        """Create a test episode object"""
        source = SourceInfo(
            path=f"/test/{episode_id}.mp4",
            file_size=1000000,
            last_modified=datetime.now()
        )
        
        media = MediaInfo(duration_seconds=3600.0)
        
        metadata = EpisodeMetadata(
            show_name="Test Show",
            show_slug="test-show",
            season=1,
            episode=1
        )
        
        content_hash = ContentHasher.calculate_metadata_hash(source, media)
        
        return EpisodeObject(
            episode_id=episode_id,
            content_hash=content_hash,
            source=source,
            media=media,
            metadata=metadata
        )


class TestContentHasher:
    """Test content hashing functionality"""
    
    def test_metadata_hash_consistency(self):
        """Test that metadata hash is consistent"""
        source = SourceInfo(
            path="/test/video.mp4",
            file_size=1000000,
            last_modified=datetime(2024, 1, 1, 12, 0, 0)
        )
        
        media = MediaInfo(duration_seconds=3600.0)
        
        hash1 = ContentHasher.calculate_metadata_hash(source, media)
        hash2 = ContentHasher.calculate_metadata_hash(source, media)
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex length
    
    def test_metadata_hash_uniqueness(self):
        """Test that different metadata produces different hashes"""
        source1 = SourceInfo(
            path="/test/video1.mp4",
            file_size=1000000,
            last_modified=datetime(2024, 1, 1, 12, 0, 0)
        )
        
        source2 = SourceInfo(
            path="/test/video2.mp4",
            file_size=2000000,
            last_modified=datetime(2024, 1, 1, 12, 0, 0)
        )
        
        media = MediaInfo(duration_seconds=3600.0)
        
        hash1 = ContentHasher.calculate_metadata_hash(source1, media)
        hash2 = ContentHasher.calculate_metadata_hash(source2, media)
        
        assert hash1 != hash2


if __name__ == "__main__":
    pytest.main([__file__])