"""
Content-addressed caching for intelligence chain steps

Provides deterministic caching with video_hash + config_hash keys
to enable idempotent reruns and partial completion.
"""

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Callable, TypeVar
from pydantic import BaseModel

from .logging import get_logger

logger = get_logger('pipeline.intelligence_cache')

T = TypeVar('T', bound=BaseModel)


class CacheKey(BaseModel):
    """Cache key components"""
    step_name: str
    video_hash: str
    config_hash: str
    step_version: str = "1.0.0"
    
    def to_string(self) -> str:
        """Generate cache key string"""
        return f"{self.step_name}-{self.video_hash[:16]}-{self.config_hash[:16]}-{self.step_version}"
    
    def to_hash(self) -> str:
        """Generate deterministic hash of cache key"""
        key_str = f"{self.step_name}:{self.video_hash}:{self.config_hash}:{self.step_version}"
        return hashlib.sha256(key_str.encode()).hexdigest()


class CacheProvenance(BaseModel):
    """Provenance metadata for cached artifacts"""
    cache_key: str
    cache_hash: str
    created_at: datetime
    step_name: str
    video_hash: str
    config_hash: str
    step_version: str
    input_hash: Optional[str] = None
    output_hash: Optional[str] = None
    duration_ms: Optional[float] = None


class IntelligenceCache:
    """
    Content-addressed cache for intelligence chain artifacts
    
    Cache structure:
    data/cache/{step_name}/{video_hash}-{config_hash}.json
    data/cache/{step_name}/{video_hash}-{config_hash}.provenance.json
    """
    
    def __init__(self, cache_dir: Path):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger
    
    def get_step_dir(self, step_name: str) -> Path:
        """Get cache directory for a specific step"""
        step_dir = self.cache_dir / step_name
        step_dir.mkdir(parents=True, exist_ok=True)
        return step_dir
    
    def compute_video_hash(self, video_path: str) -> str:
        """
        Compute content hash of video file
        
        For large files, we hash the first 10MB + last 10MB + file size
        to balance speed and uniqueness.
        """
        try:
            path = Path(video_path)
            if not path.exists():
                raise FileNotFoundError(f"Video file not found: {video_path}")
            
            hasher = hashlib.sha256()
            file_size = path.stat().st_size
            
            # Add file size to hash
            hasher.update(str(file_size).encode())
            
            # Read first 10MB
            chunk_size = 10 * 1024 * 1024  # 10MB
            with open(path, 'rb') as f:
                chunk = f.read(chunk_size)
                hasher.update(chunk)
                
                # If file is large enough, also hash last 10MB
                if file_size > chunk_size * 2:
                    f.seek(-chunk_size, 2)  # Seek from end
                    chunk = f.read(chunk_size)
                    hasher.update(chunk)
            
            return hasher.hexdigest()
        
        except Exception as e:
            self.logger.error(f"Failed to compute video hash: {e}")
            # Fallback to file path + size + mtime
            fallback = f"{video_path}:{path.stat().st_size}:{path.stat().st_mtime}"
            return hashlib.sha256(fallback.encode()).hexdigest()
    
    def compute_config_hash(self, config: Dict[str, Any]) -> str:
        """Compute hash of configuration affecting this step"""
        # Sort keys for deterministic hashing
        config_str = json.dumps(config, sort_keys=True)
        return hashlib.sha256(config_str.encode()).hexdigest()
    
    def compute_data_hash(self, data: Any) -> str:
        """Compute hash of data (for input/output tracking)"""
        if isinstance(data, BaseModel):
            # Pydantic v2: use model_dump() instead of dict() and json.dumps with sort_keys
            data_dict = data.model_dump(mode='json')
            data_str = json.dumps(data_dict, sort_keys=True, default=str)
        else:
            data_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(data_str.encode()).hexdigest()
    
    def get_cache_path(self, cache_key: CacheKey) -> Path:
        """Get cache file path for a cache key"""
        step_dir = self.get_step_dir(cache_key.step_name)
        filename = f"{cache_key.to_string()}.json"
        return step_dir / filename
    
    def get_provenance_path(self, cache_key: CacheKey) -> Path:
        """Get provenance file path for a cache key"""
        step_dir = self.get_step_dir(cache_key.step_name)
        filename = f"{cache_key.to_string()}.provenance.json"
        return step_dir / filename
    
    def has_cache(self, cache_key: CacheKey) -> bool:
        """Check if cache exists for key"""
        cache_path = self.get_cache_path(cache_key)
        return cache_path.exists()
    
    def get_cache(self, cache_key: CacheKey, result_type: type[T]) -> Optional[T]:
        """
        Retrieve cached result
        
        Args:
            cache_key: Cache key
            result_type: Pydantic model type to deserialize to
            
        Returns:
            Cached result or None if not found
        """
        cache_path = self.get_cache_path(cache_key)
        
        if not cache_path.exists():
            self.logger.debug(f"Cache miss: {cache_key.to_string()}")
            return None
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            result = result_type(**data)
            
            self.logger.info(
                f"Cache hit: {cache_key.step_name}",
                cache_key=cache_key.to_string()
            )
            
            return result
        
        except Exception as e:
            self.logger.warning(
                f"Failed to load cache: {e}",
                cache_key=cache_key.to_string()
            )
            return None
    
    def set_cache(
        self,
        cache_key: CacheKey,
        result: BaseModel,
        duration_ms: Optional[float] = None,
        input_hash: Optional[str] = None
    ) -> None:
        """
        Store result in cache with provenance
        
        Args:
            cache_key: Cache key
            result: Result to cache (pydantic model)
            duration_ms: Execution duration in milliseconds
            input_hash: Hash of input data
        """
        cache_path = self.get_cache_path(cache_key)
        provenance_path = self.get_provenance_path(cache_key)
        
        try:
            # Write result
            with open(cache_path, 'w', encoding='utf-8') as f:
                f.write(result.model_dump_json(indent=2))
            
            # Compute output hash
            output_hash = self.compute_data_hash(result)
            
            # Write provenance
            provenance = CacheProvenance(
                cache_key=cache_key.to_string(),
                cache_hash=cache_key.to_hash(),
                created_at=datetime.now(),
                step_name=cache_key.step_name,
                video_hash=cache_key.video_hash,
                config_hash=cache_key.config_hash,
                step_version=cache_key.step_version,
                input_hash=input_hash,
                output_hash=output_hash,
                duration_ms=duration_ms
            )
            
            with open(provenance_path, 'w', encoding='utf-8') as f:
                f.write(provenance.model_dump_json(indent=2))
            
            self.logger.info(
                f"Cached result: {cache_key.step_name}",
                cache_key=cache_key.to_string(),
                output_hash=output_hash[:16]
            )
        
        except Exception as e:
            self.logger.error(
                f"Failed to write cache: {e}",
                cache_key=cache_key.to_string()
            )
    
    def invalidate_cache(self, cache_key: CacheKey) -> None:
        """Remove cached result and provenance"""
        cache_path = self.get_cache_path(cache_key)
        provenance_path = self.get_provenance_path(cache_key)
        
        try:
            if cache_path.exists():
                cache_path.unlink()
            if provenance_path.exists():
                provenance_path.unlink()
            
            self.logger.info(
                f"Invalidated cache: {cache_key.step_name}",
                cache_key=cache_key.to_string()
            )
        
        except Exception as e:
            self.logger.warning(
                f"Failed to invalidate cache: {e}",
                cache_key=cache_key.to_string()
            )
    
    def clear_step_cache(self, step_name: str) -> int:
        """Clear all cache for a specific step"""
        step_dir = self.get_step_dir(step_name)
        count = 0
        
        try:
            for cache_file in step_dir.glob("*.json"):
                cache_file.unlink()
                count += 1
            
            self.logger.info(f"Cleared {count} cache files for step: {step_name}")
            return count
        
        except Exception as e:
            self.logger.error(f"Failed to clear step cache: {e}")
            return count
    
    def clear_all_cache(self) -> int:
        """Clear entire cache directory"""
        count = 0
        
        try:
            for step_dir in self.cache_dir.iterdir():
                if step_dir.is_dir():
                    for cache_file in step_dir.glob("*.json"):
                        cache_file.unlink()
                        count += 1
            
            self.logger.info(f"Cleared {count} total cache files")
            return count
        
        except Exception as e:
            self.logger.error(f"Failed to clear cache: {e}")
            return count
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        stats = {
            'total_files': 0,
            'total_size_bytes': 0,
            'steps': {}
        }
        
        try:
            for step_dir in self.cache_dir.iterdir():
                if step_dir.is_dir():
                    step_name = step_dir.name
                    step_files = list(step_dir.glob("*.json"))
                    step_size = sum(f.stat().st_size for f in step_files)
                    
                    stats['steps'][step_name] = {
                        'files': len(step_files),
                        'size_bytes': step_size
                    }
                    
                    stats['total_files'] += len(step_files)
                    stats['total_size_bytes'] += step_size
            
            return stats
        
        except Exception as e:
            self.logger.error(f"Failed to get cache stats: {e}")
            return stats
