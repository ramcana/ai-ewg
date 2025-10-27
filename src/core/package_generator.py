"""
Social Media Package Generator

Creates structured output folders for social media content based on platform policies.
Handles video transcoding, metadata file generation, and folder organization.
"""

import os
import json
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
import logging
from datetime import datetime

from .policy_engine import PlatformPolicyEngine, ValidationResult, TransformationResult
from .jsonld_generator import JSONLDGenerator

logger = logging.getLogger(__name__)


@dataclass
class PackageMetadata:
    """Metadata for a social media package"""
    platform: str
    episode_id: str
    title: str
    caption: str = ""
    hashtags: List[str] = None
    video_path: str = ""
    thumbnail_path: str = ""
    duration: float = 0.0
    created_at: datetime = None
    policy_version: str = "1.0"

    def __post_init__(self):
        if self.hashtags is None:
            self.hashtags = []
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class PackageResult:
    """Result of package generation"""
    success: bool
    package_path: str
    metadata: PackageMetadata
    files_created: List[str]
    warnings: List[str]
    errors: List[str]


class SocialMediaPackageGenerator:
    """
    Generator for social media content packages

    Creates platform-specific folder structures with transformed content,
    metadata files, and ready-to-upload assets.
    """

    def __init__(self, output_base_dir: Optional[str] = None, policy_engine: Optional[PlatformPolicyEngine] = None):
        """
        Initialize package generator

        Args:
            output_base_dir: Base directory for generated packages
            policy_engine: Policy engine instance
        """
        if output_base_dir is None:
            # Default to data/social_packages
            current_dir = Path(__file__).parent.parent.parent
            output_base_dir = current_dir / "data" / "social_packages"

        self.output_base_dir = Path(output_base_dir)
        self.output_base_dir.mkdir(parents=True, exist_ok=True)

        self.policy_engine = policy_engine or PlatformPolicyEngine()
        self.jsonld_generator = JSONLDGenerator()

        logger.info(f"Social media package generator initialized with output dir: {self.output_base_dir}")

    def generate_package(self, platform: str, episode_id: str, content: Dict[str, Any]) -> PackageResult:
        """
        Generate a complete social media package for a platform

        Args:
            platform: Target platform
            episode_id: Episode identifier
            content: Content dictionary with video, metadata, etc.

        Returns:
            PackageResult with generation results
        """
        try:
            logger.info(f"Generating {platform} package for episode {episode_id}")

            # Validate platform
            if platform not in self.policy_engine.list_platforms():
                return PackageResult(
                    success=False,
                    package_path="",
                    metadata=PackageMetadata(platform=platform, episode_id=episode_id, title=""),
                    files_created=[],
                    warnings=[],
                    errors=[f"Unknown platform: {platform}"]
                )

            # Validate content against platform policy
            validation = self.policy_engine.validate_content(platform, content)
            if not validation.is_valid:
                return PackageResult(
                    success=False,
                    package_path="",
                    metadata=PackageMetadata(platform=platform, episode_id=episode_id, title=""),
                    files_created=[],
                    warnings=validation.warnings,
                    errors=validation.errors
                )

            # Apply platform transformations
            transformation = self.policy_engine.apply_transformations(platform, content)

            # Create package directory structure
            show_name = content.get('enrichment', {}).get('show_name')
            date = content.get('created_at')
            package_dir = self._create_package_directory(episode_id, platform, show_name, date)

            # Generate package files
            files_created = []
            warnings = validation.warnings + transformation.warnings

            # Generate video file (placeholder for now)
            video_path = self._generate_video_file(package_dir, platform, content)
            if video_path:
                files_created.append(video_path)

            # Generate metadata files
            metadata_files = self._generate_metadata_files(package_dir, platform, transformation.content)
            files_created.extend(metadata_files)

            # Generate thumbnail (placeholder)
            thumbnail_path = self._generate_thumbnail(package_dir, platform, content)
            if thumbnail_path:
                files_created.append(thumbnail_path)
            
            # Generate JSON-LD structured data
            jsonld_path = self._generate_jsonld(package_dir, platform, episode_id, transformation.content)
            if jsonld_path:
                files_created.append(jsonld_path)

            # Create package metadata
            package_metadata = self._create_package_metadata(platform, episode_id, transformation.content)

            # Update metadata with file paths
            package_metadata.video_path = str(video_path) if video_path else ""
            package_metadata.thumbnail_path = str(thumbnail_path) if thumbnail_path else ""

            logger.info(f"Successfully generated {platform} package for {episode_id}")

            return PackageResult(
                success=True,
                package_path=str(package_dir),
                metadata=package_metadata,
                files_created=files_created,
                warnings=warnings,
                errors=[]
            )

        except Exception as e:
            logger.error(f"Failed to generate {platform} package for {episode_id}: {e}")
            return PackageResult(
                success=False,
                package_path="",
                metadata=PackageMetadata(platform=platform, episode_id=episode_id, title=""),
                files_created=[],
                warnings=[],
                errors=[str(e)]
            )

    def _create_package_directory(self, episode_id: str, platform: str, 
                                  show_name: Optional[str] = None,
                                  date: Optional[datetime] = None) -> Path:
        """
        Create directory structure for a social media package

        Args:
            episode_id: Episode identifier
            platform: Target platform
            show_name: Show name for organized folder structure
            date: Episode date for year-based organization

        Returns:
            Path to the package directory
        """
        # Use naming service for organized structure if show name available
        if show_name:
            from .naming_service import get_naming_service
            naming_service = get_naming_service()
            
            episode_folder = naming_service.get_episode_folder_path(
                episode_id=episode_id,
                show_name=show_name,
                date=date or datetime.now(),
                base_path=str(self.output_base_dir)
            )
            package_dir = episode_folder / platform
        else:
            # Fallback to flat structure
            package_dir = self.output_base_dir / episode_id / platform
        
        package_dir.mkdir(parents=True, exist_ok=True)

        logger.debug(f"Created package directory: {package_dir}")
        return package_dir

    def _generate_video_file(self, package_dir: Path, platform: str, content: Dict[str, Any]) -> Optional[Path]:
        """
        Generate video file for package (placeholder for transcoding logic)

        Args:
            package_dir: Package directory
            platform: Target platform
            content: Content dictionary

        Returns:
            Path to generated video file or None
        """
        # For now, just copy the source video if available
        video_info = content.get('video', {})
        source_path = video_info.get('source_path')

        if not source_path or not Path(source_path).exists():
            logger.warning(f"No source video available for {platform} package")
            return None

        # Determine output filename based on platform
        policy = self.policy_engine.get_policy(platform)
        video_policy = policy.get('video', {})

        if platform == 'youtube':
            filename = "video_16x9.mp4"
        elif platform == 'instagram':
            filename = "reel_9x16.mp4"
        elif platform == 'x':
            filename = "clip_720p.mp4"
        elif platform == 'tiktok':
            filename = "video_vertical.mp4"
        elif platform == 'facebook':
            filename = "post_video.mp4"
        else:
            filename = "video.mp4"

        output_path = package_dir / filename

        try:
            # For now, just copy the file (real transcoding would go here)
            shutil.copy2(source_path, output_path)
            logger.info(f"Copied video to {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Failed to copy video for {platform}: {e}")
            return None

    def _generate_metadata_files(self, package_dir: Path, platform: str, content: Dict[str, Any]) -> List[str]:
        """
        Generate metadata files for the package

        Args:
            package_dir: Package directory
            platform: Target platform
            content: Content dictionary

        Returns:
            List of created file paths
        """
        files_created = []
        metadata = content.get('metadata', {})

        try:
            # Generate title.txt (for platforms that use separate title)
            if metadata.get('title'):
                title_file = package_dir / "title.txt"
                with open(title_file, 'w', encoding='utf-8') as f:
                    f.write(metadata['title'])
                files_created.append(str(title_file))

            # Generate description.txt (for YouTube)
            if metadata.get('description'):
                desc_file = package_dir / "description.txt"
                with open(desc_file, 'w', encoding='utf-8') as f:
                    f.write(metadata['description'])
                files_created.append(str(desc_file))

            # Generate caption.txt (for Instagram, TikTok)
            if metadata.get('caption'):
                caption_file = package_dir / "caption.txt"
                with open(caption_file, 'w', encoding='utf-8') as f:
                    f.write(metadata['caption'])
                files_created.append(str(caption_file))

            # Generate hashtags.txt
            hashtags = metadata.get('hashtags', [])
            if hashtags:
                hashtag_file = package_dir / "hashtags.txt"
                with open(hashtag_file, 'w', encoding='utf-8') as f:
                    if platform == 'x':
                        # Twitter: space separated
                        f.write(' '.join(hashtags))
                    else:
                        # Others: newline separated
                        f.write('\n'.join(hashtags))
                files_created.append(str(hashtag_file))

            # Generate tags.txt (comma-separated for YouTube)
            if hashtags and platform == 'youtube':
                tags_file = package_dir / "tags.txt"
                with open(tags_file, 'w', encoding='utf-8') as f:
                    f.write(', '.join(h.strip('#') for h in hashtags))
                files_created.append(str(tags_file))

            # Generate metadata.json (comprehensive metadata)
            metadata_file = package_dir / "metadata.json"
            metadata_dict = {
                'platform': platform,
                'episode_id': content.get('episode_id', ''),
                'generated_at': datetime.now().isoformat(),
                'content': content,
                'policy_applied': True
            }

            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata_dict, f, indent=2, ensure_ascii=False)
            files_created.append(str(metadata_file))

        except Exception as e:
            logger.error(f"Failed to generate metadata files for {platform}: {e}")

        return files_created

    def _generate_thumbnail(self, package_dir: Path, platform: str, content: Dict[str, Any]) -> Optional[Path]:
        """
        Generate thumbnail for the package (placeholder)

        Args:
            package_dir: Package directory
            platform: Target platform
            content: Content dictionary

        Returns:
            Path to generated thumbnail or None
        """
        # For now, just create a placeholder thumbnail file
        # Real implementation would extract frame from video
        thumbnail_info = content.get('thumbnail', {})

        if platform == 'instagram':
            filename = "thumbnail_square.jpg"
        elif platform in ['youtube', 'facebook', 'x']:
            filename = "thumbnail.jpg"
        else:
            filename = "thumbnail.jpg"

        thumbnail_path = package_dir / filename

        try:
            # Create a placeholder thumbnail file
            # Real implementation would use ffmpeg or PIL to extract/generate thumbnail
            with open(thumbnail_path, 'w') as f:
                f.write("# Placeholder thumbnail file\n")
                f.write(f"# Generated for {platform} package\n")
                f.write(f"# Would contain actual image data\n")
            return thumbnail_path
        except Exception as e:
            logger.error(f"Failed to generate thumbnail for {platform}: {e}")
            return None

    def _generate_jsonld(self, package_dir: Path, platform: str, episode_id: str, content: Dict[str, Any]) -> Optional[Path]:
        """
        Generate JSON-LD structured data for the package
        
        Args:
            package_dir: Package directory
            platform: Target platform
            episode_id: Episode identifier
            content: Content dictionary
        
        Returns:
            Path to generated JSON-LD file or None
        """
        try:
            # Prepare data for JSON-LD generation
            metadata = content.get('metadata', {})
            video = content.get('video', {})
            enrichment = content.get('enrichment', {})
            
            package_data = {
                'title': metadata.get('title', ''),
                'caption': metadata.get('caption', ''),
                'hashtags': metadata.get('hashtags', []),
                'video_path': video.get('source_path', ''),
                'thumbnail_path': ''
            }
            
            episode_data = {
                'episode_id': episode_id,
                'title': metadata.get('title', ''),
                'show_name': metadata.get('show_name', ''),
                'description': metadata.get('description', ''),
                'duration': video.get('duration_seconds', 0),
                'enrichment': enrichment,
                'created_at': datetime.now().isoformat()
            }
            
            # Generate JSON-LD
            jsonld = self.jsonld_generator.generate_social_package_jsonld(
                package_data,
                episode_data,
                platform
            )
            
            # Save to file
            jsonld_path = package_dir / "structured_data.jsonld"
            if self.jsonld_generator.save_jsonld(jsonld, jsonld_path):
                logger.info(f"Generated JSON-LD for {platform} package")
                return jsonld_path
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to generate JSON-LD for {platform}: {e}")
            return None
    
    def _create_package_metadata(self, platform: str, episode_id: str, content: Dict[str, Any]) -> PackageMetadata:
        """
        Create PackageMetadata object from content

        Args:
            platform: Target platform
            episode_id: Episode identifier
            content: Content dictionary

        Returns:
            PackageMetadata object
        """
        metadata = content.get('metadata', {})
        video = content.get('video', {})

        return PackageMetadata(
            platform=platform,
            episode_id=episode_id,
            title=metadata.get('title', ''),
            caption=metadata.get('caption', ''),
            hashtags=metadata.get('hashtags', []),
            duration=video.get('duration_seconds', 0.0)
        )

    def list_packages(self, episode_id: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        List all generated packages

        Args:
            episode_id: Optional episode ID to filter by

        Returns:
            Dictionary mapping episode IDs to lists of packages
        """
        packages = {}

        try:
            if episode_id:
                episode_dirs = [self.output_base_dir / episode_id]
            else:
                episode_dirs = list(self.output_base_dir.iterdir()) if self.output_base_dir.exists() else []

            for episode_dir in episode_dirs:
                if not episode_dir.is_dir():
                    continue

                episode_packages = []
                for platform_dir in episode_dir.iterdir():
                    if not platform_dir.is_dir():
                        continue

                    # Check if metadata.json exists
                    metadata_file = platform_dir / "metadata.json"
                    if metadata_file.exists():
                        try:
                            with open(metadata_file, 'r', encoding='utf-8') as f:
                                package_info = json.load(f)

                            episode_packages.append({
                                'platform': platform_dir.name,
                                'path': str(platform_dir),
                                'metadata': package_info,
                                'created_at': package_info.get('generated_at'),
                                'files': [f.name for f in platform_dir.iterdir() if f.is_file()]
                            })
                        except Exception as e:
                            logger.warning(f"Failed to read package metadata for {platform_dir}: {e}")

                if episode_packages:
                    packages[episode_dir.name] = episode_packages

        except Exception as e:
            logger.error(f"Failed to list packages: {e}")

        return packages

    def delete_package(self, episode_id: str, platform: str) -> bool:
        """
        Delete a generated package

        Args:
            episode_id: Episode identifier
            platform: Platform name

        Returns:
            True if deleted successfully
        """
        try:
            package_dir = self.output_base_dir / episode_id / platform
            if package_dir.exists():
                shutil.rmtree(package_dir)
                logger.info(f"Deleted package: {package_dir}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete package {episode_id}/{platform}: {e}")
            return False


# Convenience function
def create_package_generator(output_dir: Optional[str] = None) -> SocialMediaPackageGenerator:
    """
    Create and return a configured package generator

    Args:
        output_dir: Output directory for packages

    Returns:
        SocialMediaPackageGenerator: Configured generator instance
    """
    return SocialMediaPackageGenerator(output_dir)
