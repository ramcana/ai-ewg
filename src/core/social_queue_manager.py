"""
Social Queue Manager for Content Publishing Platform

Implements queue file generation with build-based organization,
suggested publish timestamps, scheduling, and queue processing status tracking.
"""

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum

from .publishing_models import (
    SocialPackage, PackageStatus, ValidationResult, ValidationError, 
    ValidationWarning, ErrorType, Severity
)


class QueueItemStatus(Enum):
    """Status of items in the social posting queue"""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    POSTED = "posted"
    FAILED = "failed"
    SKIPPED = "skipped"


class SchedulingStrategy(Enum):
    """Strategies for scheduling social posts"""
    IMMEDIATE = "immediate"
    STAGGERED = "staggered"
    OPTIMAL_TIMES = "optimal_times"
    CUSTOM = "custom"


@dataclass
class QueueItem:
    """Individual item in the social posting queue"""
    item_id: str
    episode_id: str
    platform: str
    package_path: str
    suggested_publish_at: datetime
    priority: int = 0
    status: QueueItemStatus = QueueItemStatus.PENDING
    created_at: Optional[datetime] = None
    scheduled_at: Optional[datetime] = None
    posted_at: Optional[datetime] = None
    external_id: Optional[str] = None  # Platform-specific post ID
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if not self.item_id:
            self.item_id = f"{self.episode_id}_{self.platform}_{uuid.uuid4().hex[:8]}"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'item_id': self.item_id,
            'episode_id': self.episode_id,
            'platform': self.platform,
            'package_path': self.package_path,
            'suggested_publish_at': self.suggested_publish_at.isoformat(),
            'priority': self.priority,
            'status': self.status.value,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'scheduled_at': self.scheduled_at.isoformat() if self.scheduled_at else None,
            'posted_at': self.posted_at.isoformat() if self.posted_at else None,
            'external_id': self.external_id,
            'error_message': self.error_message,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QueueItem':
        return cls(
            item_id=data['item_id'],
            episode_id=data['episode_id'],
            platform=data['platform'],
            package_path=data['package_path'],
            suggested_publish_at=datetime.fromisoformat(data['suggested_publish_at']),
            priority=data.get('priority', 0),
            status=QueueItemStatus(data.get('status', 'pending')),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None,
            scheduled_at=datetime.fromisoformat(data['scheduled_at']) if data.get('scheduled_at') else None,
            posted_at=datetime.fromisoformat(data['posted_at']) if data.get('posted_at') else None,
            external_id=data.get('external_id'),
            error_message=data.get('error_message'),
            retry_count=data.get('retry_count', 0),
            max_retries=data.get('max_retries', 3)
        )


@dataclass
class SocialQueue:
    """Social posting queue for a build"""
    build_id: str
    queue_items: List[QueueItem] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    total_items: int = 0
    pending_items: int = 0
    posted_items: int = 0
    failed_items: int = 0
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self._update_counts()
    
    def _update_counts(self):
        """Update item counts based on current queue state"""
        self.total_items = len(self.queue_items)
        self.pending_items = sum(1 for item in self.queue_items 
                               if item.status in [QueueItemStatus.PENDING, QueueItemStatus.SCHEDULED])
        self.posted_items = sum(1 for item in self.queue_items 
                              if item.status == QueueItemStatus.POSTED)
        self.failed_items = sum(1 for item in self.queue_items 
                              if item.status == QueueItemStatus.FAILED)
    
    def add_item(self, item: QueueItem) -> None:
        """Add item to queue"""
        self.queue_items.append(item)
        self.updated_at = datetime.now()
        self._update_counts()
    
    def update_item_status(self, item_id: str, status: QueueItemStatus, 
                          external_id: Optional[str] = None,
                          error_message: Optional[str] = None) -> bool:
        """Update status of queue item"""
        for item in self.queue_items:
            if item.item_id == item_id:
                item.status = status
                if external_id:
                    item.external_id = external_id
                if error_message:
                    item.error_message = error_message
                if status == QueueItemStatus.POSTED:
                    item.posted_at = datetime.now()
                elif status == QueueItemStatus.SCHEDULED:
                    item.scheduled_at = datetime.now()
                
                self.updated_at = datetime.now()
                self._update_counts()
                return True
        return False
    
    def get_pending_items(self) -> List[QueueItem]:
        """Get all pending items"""
        return [item for item in self.queue_items 
                if item.status in [QueueItemStatus.PENDING, QueueItemStatus.SCHEDULED]]
    
    def get_failed_items(self) -> List[QueueItem]:
        """Get all failed items"""
        return [item for item in self.queue_items if item.status == QueueItemStatus.FAILED]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'build_id': self.build_id,
            'queue_items': [item.to_dict() for item in self.queue_items],
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'total_items': self.total_items,
            'pending_items': self.pending_items,
            'posted_items': self.posted_items,
            'failed_items': self.failed_items
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SocialQueue':
        queue = cls(
            build_id=data['build_id'],
            queue_items=[QueueItem.from_dict(item_data) for item_data in data.get('queue_items', [])],
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None,
            updated_at=datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else None
        )
        return queue


@dataclass
class SchedulingConfig:
    """Configuration for social post scheduling"""
    strategy: SchedulingStrategy = SchedulingStrategy.STAGGERED
    stagger_interval_minutes: int = 15
    optimal_times: Dict[str, List[str]] = field(default_factory=dict)  # platform -> list of "HH:MM" times
    timezone: str = "UTC"
    max_posts_per_hour: int = 10
    respect_platform_limits: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'strategy': self.strategy.value,
            'stagger_interval_minutes': self.stagger_interval_minutes,
            'optimal_times': self.optimal_times,
            'timezone': self.timezone,
            'max_posts_per_hour': self.max_posts_per_hour,
            'respect_platform_limits': self.respect_platform_limits
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SchedulingConfig':
        return cls(
            strategy=SchedulingStrategy(data.get('strategy', 'staggered')),
            stagger_interval_minutes=data.get('stagger_interval_minutes', 15),
            optimal_times=data.get('optimal_times', {}),
            timezone=data.get('timezone', 'UTC'),
            max_posts_per_hour=data.get('max_posts_per_hour', 10),
            respect_platform_limits=data.get('respect_platform_limits', True)
        )


class SocialQueueManager:
    """
    Manages social posting queues with build-based organization,
    scheduling, and status tracking
    """
    
    def __init__(self, queue_root: str = "data/social/queue"):
        """
        Initialize Social Queue Manager
        
        Args:
            queue_root: Root directory for queue files
        """
        self.queue_root = Path(queue_root)
        self.queue_root.mkdir(parents=True, exist_ok=True)
        
        # Default scheduling configuration
        self.scheduling_config = SchedulingConfig()
        
        # Platform-specific optimal posting times (example defaults)
        self.scheduling_config.optimal_times = {
            'youtube': ['09:00', '14:00', '18:00'],
            'instagram': ['11:00', '13:00', '17:00', '19:00'],
            'twitter': ['08:00', '12:00', '15:00', '18:00'],
            'facebook': ['09:00', '13:00', '15:00']
        }
    
    def generate_queue_file(self, build_id: str, social_packages: List[SocialPackage],
                          scheduling_config: Optional[SchedulingConfig] = None) -> SocialQueue:
        """
        Generate queue file for a build with social packages
        
        Args:
            build_id: Build identifier
            social_packages: List of social packages to queue
            scheduling_config: Optional scheduling configuration
            
        Returns:
            Generated SocialQueue object
        """
        if scheduling_config:
            self.scheduling_config = scheduling_config
        
        # Create queue
        queue = SocialQueue(build_id=build_id)
        
        # Filter valid packages
        valid_packages = [pkg for pkg in social_packages if pkg.status == PackageStatus.VALID]
        
        if not valid_packages:
            return queue
        
        # Generate queue items with scheduling
        base_time = datetime.now()
        
        for i, package in enumerate(valid_packages):
            # Calculate suggested publish time
            suggested_time = self._calculate_suggested_publish_time(
                package.platform, base_time, i
            )
            
            # Determine package path
            package_path = f"{package.platform}/{package.episode_id}"
            
            # Create queue item
            queue_item = QueueItem(
                item_id="",  # Will be auto-generated
                episode_id=package.episode_id,
                platform=package.platform,
                package_path=package_path,
                suggested_publish_at=suggested_time,
                priority=self._calculate_priority(package)
            )
            
            queue.add_item(queue_item)
        
        # Sort by priority and suggested publish time
        queue.queue_items.sort(key=lambda x: (x.priority, x.suggested_publish_at))
        
        return queue
    
    def _calculate_suggested_publish_time(self, platform: str, base_time: datetime, index: int) -> datetime:
        """Calculate suggested publish time based on scheduling strategy"""
        if self.scheduling_config.strategy == SchedulingStrategy.IMMEDIATE:
            return base_time
        
        elif self.scheduling_config.strategy == SchedulingStrategy.STAGGERED:
            # Stagger posts by configured interval
            offset_minutes = index * self.scheduling_config.stagger_interval_minutes
            return base_time + timedelta(minutes=offset_minutes)
        
        elif self.scheduling_config.strategy == SchedulingStrategy.OPTIMAL_TIMES:
            # Use platform-specific optimal times
            optimal_times = self.scheduling_config.optimal_times.get(platform, ['12:00'])
            
            # Find next optimal time
            current_time = base_time + timedelta(minutes=index * 5)  # Small offset for ordering
            
            for time_str in optimal_times:
                hour, minute = map(int, time_str.split(':'))
                optimal_time = current_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
                
                if optimal_time > current_time:
                    return optimal_time
            
            # If no optimal time today, use first optimal time tomorrow
            hour, minute = map(int, optimal_times[0].split(':'))
            next_day = current_time.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=1)
            return next_day
        
        else:  # CUSTOM or fallback
            return base_time + timedelta(minutes=index * 10)
    
    def _calculate_priority(self, package: SocialPackage) -> int:
        """Calculate priority for queue item (lower number = higher priority)"""
        priority = 100  # Default priority
        
        # Adjust based on platform (example logic)
        platform_priorities = {
            'youtube': 10,
            'instagram': 20,
            'twitter': 30,
            'facebook': 40
        }
        
        priority = platform_priorities.get(package.platform, priority)
        
        # Adjust based on episode metadata (if available)
        # This could be enhanced with more sophisticated priority logic
        
        return priority
    
    def save_queue_file(self, queue: SocialQueue) -> Path:
        """
        Save queue to file
        
        Args:
            queue: SocialQueue to save
            
        Returns:
            Path to saved queue file
        """
        queue_file_path = self.queue_root / f"{queue.build_id}.json"
        
        with open(queue_file_path, 'w', encoding='utf-8') as f:
            json.dump(queue.to_dict(), f, indent=2, ensure_ascii=False)
        
        return queue_file_path
    
    def load_queue_file(self, build_id: str) -> Optional[SocialQueue]:
        """
        Load queue from file
        
        Args:
            build_id: Build identifier
            
        Returns:
            Loaded SocialQueue or None if not found
        """
        queue_file_path = self.queue_root / f"{build_id}.json"
        
        if not queue_file_path.exists():
            return None
        
        try:
            with open(queue_file_path, 'r', encoding='utf-8') as f:
                queue_data = json.load(f)
            
            return SocialQueue.from_dict(queue_data)
        
        except Exception as e:
            print(f"Error loading queue file {queue_file_path}: {e}")
            return None
    
    def update_queue_item_status(self, build_id: str, item_id: str, 
                                status: QueueItemStatus,
                                external_id: Optional[str] = None,
                                error_message: Optional[str] = None) -> bool:
        """
        Update status of a queue item
        
        Args:
            build_id: Build identifier
            item_id: Queue item identifier
            status: New status
            external_id: Optional external platform ID
            error_message: Optional error message
            
        Returns:
            True if update successful, False otherwise
        """
        queue = self.load_queue_file(build_id)
        if not queue:
            return False
        
        success = queue.update_item_status(item_id, status, external_id, error_message)
        
        if success:
            self.save_queue_file(queue)
        
        return success
    
    def get_pending_items(self, build_id: Optional[str] = None) -> List[QueueItem]:
        """
        Get pending items from queue(s)
        
        Args:
            build_id: Optional specific build ID, if None returns from all queues
            
        Returns:
            List of pending queue items
        """
        pending_items = []
        
        if build_id:
            # Get from specific build
            queue = self.load_queue_file(build_id)
            if queue:
                pending_items.extend(queue.get_pending_items())
        else:
            # Get from all queue files
            for queue_file in self.queue_root.glob("*.json"):
                build_id = queue_file.stem
                queue = self.load_queue_file(build_id)
                if queue:
                    pending_items.extend(queue.get_pending_items())
        
        # Sort by suggested publish time
        pending_items.sort(key=lambda x: x.suggested_publish_at)
        
        return pending_items
    
    def get_queue_statistics(self, build_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics about queue(s)
        
        Args:
            build_id: Optional specific build ID
            
        Returns:
            Dictionary with queue statistics
        """
        if build_id:
            # Statistics for specific build
            queue = self.load_queue_file(build_id)
            if not queue:
                return {"error": f"Queue not found for build: {build_id}"}
            
            return {
                "build_id": build_id,
                "total_items": queue.total_items,
                "pending_items": queue.pending_items,
                "posted_items": queue.posted_items,
                "failed_items": queue.failed_items,
                "created_at": queue.created_at.isoformat() if queue.created_at else None,
                "updated_at": queue.updated_at.isoformat() if queue.updated_at else None
            }
        else:
            # Statistics for all queues
            all_stats = {
                "total_queues": 0,
                "total_items": 0,
                "total_pending": 0,
                "total_posted": 0,
                "total_failed": 0,
                "queue_details": []
            }
            
            for queue_file in self.queue_root.glob("*.json"):
                build_id = queue_file.stem
                queue = self.load_queue_file(build_id)
                if queue:
                    all_stats["total_queues"] += 1
                    all_stats["total_items"] += queue.total_items
                    all_stats["total_pending"] += queue.pending_items
                    all_stats["total_posted"] += queue.posted_items
                    all_stats["total_failed"] += queue.failed_items
                    
                    all_stats["queue_details"].append({
                        "build_id": build_id,
                        "total_items": queue.total_items,
                        "pending_items": queue.pending_items,
                        "posted_items": queue.posted_items,
                        "failed_items": queue.failed_items
                    })
            
            return all_stats
    
    def cleanup_old_queues(self, days_old: int = 30) -> int:
        """
        Clean up old queue files
        
        Args:
            days_old: Remove queues older than this many days
            
        Returns:
            Number of queues removed
        """
        cutoff_date = datetime.now() - timedelta(days=days_old)
        removed_count = 0
        
        for queue_file in self.queue_root.glob("*.json"):
            try:
                queue = self.load_queue_file(queue_file.stem)
                if queue and queue.created_at and queue.created_at < cutoff_date:
                    # Only remove if all items are posted or failed
                    if queue.pending_items == 0:
                        queue_file.unlink()
                        removed_count += 1
            except Exception as e:
                print(f"Error processing queue file {queue_file}: {e}")
        
        return removed_count


# Utility functions
def create_social_queue_manager(queue_root: Optional[str] = None) -> SocialQueueManager:
    """
    Create a SocialQueueManager instance
    
    Args:
        queue_root: Optional queue root directory
        
    Returns:
        Configured SocialQueueManager instance
    """
    return SocialQueueManager(queue_root or "data/social/queue")


def create_scheduling_config(strategy: str = "staggered",
                           stagger_minutes: int = 15,
                           optimal_times: Optional[Dict[str, List[str]]] = None) -> SchedulingConfig:
    """
    Create a SchedulingConfig instance
    
    Args:
        strategy: Scheduling strategy name
        stagger_minutes: Minutes between staggered posts
        optimal_times: Platform-specific optimal posting times
        
    Returns:
        Configured SchedulingConfig instance
    """
    config = SchedulingConfig(
        strategy=SchedulingStrategy(strategy),
        stagger_interval_minutes=stagger_minutes
    )
    
    if optimal_times:
        config.optimal_times = optimal_times
    
    return config