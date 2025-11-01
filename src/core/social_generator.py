"""
Social Generator for Platform-Ready Content Packages

Implements SocialPackage creation with upload manifests, platform-specific
metadata formatting, and package validation and status tracking.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
import uuid
import shutil

from .platform_profiles import PlatformProfile, PlatformProfileLoader, MediaSpecValidator
from .media_normalizer import MediaNormalizationPipeline, NormalizationResult
from .publishing_models import (
    Episode, SocialPackage, UploadManifest, MediaAsset, RightsMetadata,
    PackageStatus, PrivacyLevel, AssetType, ValidationResult, ValidationError,
    ErrorType, Severity
)


@dataclass
class SocialGenerationJob:
    """Job specification for social package generation"""
    episode: Episode
    platform_id: str
    output_dir: Union[str, Path]
    source_video_path: Optional[Union[str, Path]] = None
    source_caption_path: Optional[Union[str, Path]] = None
    custom_specs: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'episode': self.episode.to_dict(),
            'platform_id': self.platform_id,
            'output_dir': str(self.output_dir),
            'source_video_path': str(self.source_video_path) if self.source_video_path else None,
            'source_caption_path': str(self.source_caption_path) if self.source_caption_path else None,
            'custom_specs': self.custom_specs
        }


@dataclass
class SocialGenerationResult:
    """Result of social package generation"""
    success: bool
    social_package: Optional[SocialPackage] = None
    validation_result: Optional[ValidationResult] = None
    error_message: Optional[str] = None
    processing_log: List[str] = field(default_factory=list)
    generated_files: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'social_package': self.social_package.to_dict() if self.social_package else None,
            'validation_result': self.validation_result.to_dict() if self.validation_result else None,
            'error_message': self.error_message,
            'processing_log': self.processing_log,
            'generated_files': self.generated_files
        }


class PlatformMetadataFormatter:
    """Formats episode metadata for specific social media platforms"""
    
    def __init__(self, platform_profile: PlatformProfile):
        """
        Initialize metadata formatter
        
        Args:
            platform_profile: Platform profile with metadata specifications
        """
        self.platform_profile = platform_profile
    
    def format_title(self, episode: Episode) -> str:
        """
        Format episode title for platform
        
        Args:
            episode: Episode object
            
        Returns:
            Formatted title string
        """
        title = episode.title
        
        # Truncate if necessary
        if self.platform_profile.metadata.title_max_length:
            max_len = self.platform_profile.metadata.title_max_length
            if len(title) > max_len:
                # Truncate and add ellipsis
                title = title[:max_len-3] + "..."
        
        return title
    
    def format_description(self, episode: Episode) -> str:
        """
        Format episode description for platform
        
        Args:
            episode: Episode object
            
        Returns:
            Formatted description string
        """
        description_parts = []
        
        # Start with episode description
        if episode.description:
            description_parts.append(episode.description)
        
        # Add series information
        if episode.series:
            description_parts.append(f"\nFrom: {episode.series.title}")
        
        # Add host information
        if episode.hosts:
            host_names = [host.name for host in episode.hosts]
            description_parts.append(f"Host(s): {', '.join(host_names)}")
        
        # Add episode metadata
        if episode.episode_number:
            description_parts.append(f"Episode #{episode.episode_number}")
        
        # Join all parts
        description = "\n".join(description_parts)
        
        # Truncate if necessary
        if self.platform_profile.metadata.description_max_length:
            max_len = self.platform_profile.metadata.description_max_length
            if len(description) > max_len:
                # Truncate and add ellipsis
                description = description[:max_len-3] + "..."
        
        return description
    
    def format_tags(self, episode: Episode) -> List[str]:
        """
        Format episode tags for platform
        
        Args:
            episode: Episode object
            
        Returns:
            List of formatted tags
        """
        tags = []
        
        # Add episode tags
        if episode.tags:
            tags.extend(episode.tags)
        
        # Add series-based tags
        if episode.series:
            tags.append(episode.series.slug)
            if episode.series.topics:
                tags.extend(episode.series.topics)
        
        # Add host-based tags
        if episode.hosts:
            for host in episode.hosts:
                tags.append(host.slug)
        
        # Clean and validate tags
        formatted_tags = []
        for tag in tags:
            # Remove special characters and spaces
            clean_tag = ''.join(c for c in tag if c.isalnum() or c in '-_')
            
            # Check tag length
            if self.platform_profile.metadata.tag_max_length:
                max_len = self.platform_profile.metadata.tag_max_length
                if len(clean_tag) > max_len:
                    clean_tag = clean_tag[:max_len]
            
            if clean_tag and clean_tag not in formatted_tags:
                formatted_tags.append(clean_tag)
        
        # Limit number of tags
        if self.platform_profile.metadata.tags_max_count:
            max_count = self.platform_profile.metadata.tags_max_count
            formatted_tags = formatted_tags[:max_count]
        
        return formatted_tags
    
    def determine_privacy_level(self, episode: Episode) -> PrivacyLevel:
        """
        Determine appropriate privacy level for episode
        
        Args:
            episode: Episode object
            
        Returns:
            PrivacyLevel enum value
        """
        # Default to public for most content
        # Could be enhanced with episode-specific privacy settings
        return PrivacyLevel.PUBLIC
    
    def determine_age_restriction(self, episode: Episode) -> bool:
        """
        Determine if content should be age-restricted
        
        Args:
            episode: Episode object
            
        Returns:
            True if age-restricted content
        """
        # Check episode tags for mature content indicators
        mature_keywords = ['mature', 'adult', 'explicit', '18+', 'nsfw']
        
        if episode.tags:
            for tag in episode.tags:
                if any(keyword in tag.lower() for keyword in mature_keywords):
                    return True
        
        return False
    
    def determine_made_for_kids(self, episode: Episode) -> bool:
        """
        Determine if content is made for kids
        
        Args:
            episode: Episode object
            
        Returns:
            True if made for kids
        """
        # Check episode tags for kids content indicators
        kids_keywords = ['kids', 'children', 'family', 'educational']
        
        if episode.tags:
            for tag in episode.tags:
                if any(keyword in tag.lower() for keyword in kids_keywords):
                    return True
        
        return False


class SocialPackageValidator:
    """Validates social packages against platform requirements and compliance"""
    
    def __init__(self, platform_profile: PlatformProfile):
        """
        Initialize package validator
        
        Args:
            platform_profile: Platform profile for validation
        """
        self.platform_profile = platform_profile
        self.media_validator = MediaSpecValidator(platform_profile)
    
    def validate_package(self, social_package: SocialPackage) -> ValidationResult:
        """
        Validate complete social package
        
        Args:
            social_package: SocialPackage to validate
            
        Returns:
            ValidationResult with errors and warnings
        """
        errors = []
        warnings = []
        
        # Validate upload manifest
        manifest_result = self.validate_upload_manifest(social_package.upload_manifest)
        errors.extend(manifest_result.errors)
        warnings.extend(manifest_result.warnings)
        
        # Validate media assets
        for asset in social_package.media_assets:
            asset_result = self.validate_media_asset(asset)
            errors.extend(asset_result.errors)
            warnings.extend(asset_result.warnings)
        
        # Validate rights compliance
        rights_result = self.validate_rights_compliance(social_package.rights)
        errors.extend(rights_result.errors)
        warnings.extend(rights_result.warnings)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            metadata={
                'platform': self.platform_profile.platform_id,
                'package_id': social_package.episode_id
            }
        )
    
    def validate_upload_manifest(self, manifest: UploadManifest) -> ValidationResult:
        """Validate upload manifest metadata"""
        errors = []
        warnings = []
        
        # Validate title
        if manifest.title:
            title_result = self.media_validator.validate_metadata_specs(title=manifest.title)
            errors.extend(title_result.errors)
            warnings.extend(title_result.warnings)
        else:
            errors.append(ValidationError(
                error_type=ErrorType.MEDIA_VALIDATION,
                message="Title is required",
                location="upload_manifest.title",
                severity=Severity.ERROR
            ))
        
        # Validate description
        if manifest.description:
            desc_result = self.media_validator.validate_metadata_specs(description=manifest.description)
            errors.extend(desc_result.errors)
            warnings.extend(desc_result.warnings)
        
        # Validate tags
        if manifest.tags:
            tags_result = self.media_validator.validate_metadata_specs(tags=manifest.tags)
            errors.extend(tags_result.errors)
            warnings.extend(tags_result.warnings)
        
        # Validate media paths exist
        for media_path in manifest.media_paths:
            if not Path(media_path).exists():
                errors.append(ValidationError(
                    error_type=ErrorType.MEDIA_VALIDATION,
                    message=f"Media file not found: {media_path}",
                    location="upload_manifest.media_paths",
                    severity=Severity.ERROR
                ))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def validate_media_asset(self, asset: MediaAsset) -> ValidationResult:
        """Validate individual media asset"""
        errors = []
        warnings = []
        
        # Check if file exists
        if not Path(asset.asset_path).exists():
            errors.append(ValidationError(
                error_type=ErrorType.MEDIA_VALIDATION,
                message=f"Asset file not found: {asset.asset_path}",
                location="media_asset.asset_path",
                severity=Severity.ERROR
            ))
            return ValidationResult(is_valid=False, errors=errors)
        
        # Validate based on asset type
        if asset.asset_type == AssetType.VIDEO:
            # Validate video specifications
            video_result = self.media_validator.validate_video_specs(
                duration_seconds=asset.duration.total_seconds() if asset.duration else None,
                resolution=asset.format_specs.resolution,
                codec=asset.format_specs.codec,
                bitrate=asset.format_specs.bitrate,
                file_size_bytes=asset.file_size
            )
            errors.extend(video_result.errors)
            warnings.extend(video_result.warnings)
        
        elif asset.asset_type == AssetType.AUDIO:
            # Validate audio specifications
            audio_result = self.media_validator.validate_audio_specs(
                codec=asset.format_specs.codec,
                loudness=asset.format_specs.loudness_target
            )
            errors.extend(audio_result.errors)
            warnings.extend(audio_result.warnings)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def validate_rights_compliance(self, rights: RightsMetadata) -> ValidationResult:
        """Validate rights and compliance requirements"""
        errors = []
        warnings = []
        
        # Check music clearance for platforms that require it
        if not rights.music_clearance and self.platform_profile.platform_id in ['youtube', 'instagram']:
            warnings.append(ValidationError(
                error_type=ErrorType.RIGHTS_VALIDATION,
                message="Music clearance not confirmed - may result in content claims",
                location="rights.music_clearance",
                severity=Severity.WARNING
            ))
        
        # Check for third-party assets
        if rights.third_party_assets:
            warnings.append(ValidationError(
                error_type=ErrorType.RIGHTS_VALIDATION,
                message=f"Third-party assets present: {', '.join(rights.third_party_assets)}",
                location="rights.third_party_assets",
                severity=Severity.WARNING
            ))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )


class SocialGenerator:
    """Main social media package generator"""
    
    def __init__(self, 
                 profile_loader: PlatformProfileLoader,
                 temp_dir: Optional[Union[str, Path]] = None):
        """
        Initialize social generator
        
        Args:
            profile_loader: Loaded platform profiles
            temp_dir: Directory for temporary files
        """
        self.profile_loader = profile_loader
        self.temp_dir = Path(temp_dir) if temp_dir else Path.cwd() / "temp"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize media normalization pipeline
        self.media_pipeline = MediaNormalizationPipeline(self.temp_dir)
    
    def generate_social_package(self, job: SocialGenerationJob) -> SocialGenerationResult:
        """
        Generate complete social media package for episode
        
        Args:
            job: Social generation job specification
            
        Returns:
            SocialGenerationResult with package and validation details
        """
        processing_log = []
        generated_files = []
        
        try:
            # Get platform profile
            platform_profile = self.profile_loader.get_profile(job.platform_id)
            if not platform_profile:
                return SocialGenerationResult(
                    success=False,
                    error_message=f"Platform profile not found: {job.platform_id}",
                    processing_log=processing_log
                )
            
            if not platform_profile.enabled:
                return SocialGenerationResult(
                    success=False,
                    error_message=f"Platform {job.platform_id} is disabled",
                    processing_log=processing_log
                )
            
            processing_log.append(f"Generating social package for {job.platform_id}")
            processing_log.append(f"Episode: {job.episode.episode_id}")
            
            # Create output directory
            output_dir = Path(job.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Initialize metadata formatter
            formatter = PlatformMetadataFormatter(platform_profile)
            
            # Create upload manifest
            processing_log.append("Creating upload manifest...")
            upload_manifest = self._create_upload_manifest(job.episode, formatter)
            
            # Normalize media assets
            processing_log.append("Normalizing media assets...")
            media_assets = []
            
            if job.source_video_path:
                # Normalize video for platform
                normalization_results = self.media_pipeline.normalize_for_platform(
                    job.source_video_path,
                    output_dir,
                    platform_profile,
                    job.episode.episode_id,
                    job.source_caption_path
                )
                
                # Collect successful media assets
                for result in normalization_results:
                    if result.success and result.media_asset:
                        media_assets.append(result.media_asset)
                        generated_files.append(result.output_path)
                        processing_log.extend(result.processing_log)
                    else:
                        processing_log.append(f"Media normalization failed: {result.error_message}")
            
            # Update upload manifest with media paths
            upload_manifest.media_paths = [asset.asset_path for asset in media_assets if asset.asset_type == AssetType.VIDEO]
            
            # Set thumbnail URL from generated thumbnails
            thumbnail_assets = [asset for asset in media_assets if asset.asset_type == AssetType.THUMBNAIL]
            if thumbnail_assets:
                upload_manifest.thumbnail_url = thumbnail_assets[0].asset_path
            
            # Set captions URL from generated captions
            caption_assets = [asset for asset in media_assets if asset.asset_type == AssetType.CAPTIONS]
            if caption_assets:
                upload_manifest.captions_url = caption_assets[0].asset_path
            
            # Create rights metadata
            rights = job.episode.rights or RightsMetadata()
            
            # Create social package
            social_package = SocialPackage(
                episode_id=job.episode.episode_id,
                platform=job.platform_id,
                status=PackageStatus.PENDING,
                media_assets=media_assets,
                upload_manifest=upload_manifest,
                rights=rights
            )
            
            # Save upload manifest to file
            manifest_path = output_dir / "upload.json"
            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump(upload_manifest.to_dict(), f, indent=2, default=str)
            generated_files.append(str(manifest_path))
            processing_log.append(f"Saved upload manifest: {manifest_path}")
            
            # Validate package
            processing_log.append("Validating social package...")
            validator = SocialPackageValidator(platform_profile)
            validation_result = validator.validate_package(social_package)
            
            # Update package status based on validation
            if validation_result.is_valid:
                social_package.status = PackageStatus.VALID
                processing_log.append("Package validation successful")
            else:
                social_package.status = PackageStatus.INVALID
                processing_log.append(f"Package validation failed: {len(validation_result.errors)} errors")
                for error in validation_result.errors:
                    processing_log.append(f"  - {error.message}")
            
            # Save package metadata
            package_path = output_dir / "package.json"
            with open(package_path, 'w', encoding='utf-8') as f:
                json.dump(social_package.to_dict(), f, indent=2, default=str)
            generated_files.append(str(package_path))
            processing_log.append(f"Saved package metadata: {package_path}")
            
            return SocialGenerationResult(
                success=True,
                social_package=social_package,
                validation_result=validation_result,
                processing_log=processing_log,
                generated_files=generated_files
            )
            
        except Exception as e:
            error_msg = f"Social package generation failed: {str(e)}"
            processing_log.append(error_msg)
            return SocialGenerationResult(
                success=False,
                error_message=error_msg,
                processing_log=processing_log,
                generated_files=generated_files
            )
    
    def _create_upload_manifest(self, 
                               episode: Episode, 
                               formatter: PlatformMetadataFormatter) -> UploadManifest:
        """Create upload manifest from episode data"""
        return UploadManifest(
            title=formatter.format_title(episode),
            description=formatter.format_description(episode),
            tags=formatter.format_tags(episode),
            publish_at=episode.upload_date + timedelta(hours=1),  # Schedule 1 hour after upload
            privacy=formatter.determine_privacy_level(episode),
            age_restriction=formatter.determine_age_restriction(episode),
            made_for_kids=formatter.determine_made_for_kids(episode)
        )
    
    def generate_packages_for_episode(self, 
                                    episode: Episode,
                                    output_base_dir: Union[str, Path],
                                    source_video_path: Optional[Union[str, Path]] = None,
                                    source_caption_path: Optional[Union[str, Path]] = None,
                                    platforms: Optional[List[str]] = None) -> Dict[str, SocialGenerationResult]:
        """
        Generate social packages for multiple platforms
        
        Args:
            episode: Episode to generate packages for
            output_base_dir: Base directory for all platform packages
            source_video_path: Source video file
            source_caption_path: Source caption file
            platforms: List of platform IDs (default: all enabled platforms)
            
        Returns:
            Dictionary of platform_id -> SocialGenerationResult
        """
        output_base_dir = Path(output_base_dir)
        results = {}
        
        # Get platforms to generate for
        if platforms is None:
            enabled_profiles = self.profile_loader.get_enabled_profiles()
            platforms = list(enabled_profiles.keys())
        
        # Generate package for each platform
        for platform_id in platforms:
            platform_output_dir = output_base_dir / platform_id / episode.episode_id
            
            job = SocialGenerationJob(
                episode=episode,
                platform_id=platform_id,
                output_dir=platform_output_dir,
                source_video_path=source_video_path,
                source_caption_path=source_caption_path
            )
            
            result = self.generate_social_package(job)
            results[platform_id] = result
        
        return results
    
    def get_package_status(self, package_dir: Union[str, Path]) -> Optional[PackageStatus]:
        """
        Get status of existing social package
        
        Args:
            package_dir: Directory containing package files
            
        Returns:
            PackageStatus if package exists, None otherwise
        """
        package_dir = Path(package_dir)
        package_file = package_dir / "package.json"
        
        if not package_file.exists():
            return None
        
        try:
            with open(package_file, 'r', encoding='utf-8') as f:
                package_data = json.load(f)
            
            return PackageStatus(package_data.get('status', 'pending'))
        except (json.JSONDecodeError, KeyError, ValueError):
            return None
    
    def update_package_status(self, 
                             package_dir: Union[str, Path], 
                             status: PackageStatus,
                             external_id: Optional[str] = None,
                             posted_at: Optional[datetime] = None) -> bool:
        """
        Update status of existing social package
        
        Args:
            package_dir: Directory containing package files
            status: New package status
            external_id: Platform-specific ID (for posted packages)
            posted_at: Timestamp when posted (for posted packages)
            
        Returns:
            True if update successful, False otherwise
        """
        package_dir = Path(package_dir)
        package_file = package_dir / "package.json"
        
        if not package_file.exists():
            return False
        
        try:
            # Load existing package data
            with open(package_file, 'r', encoding='utf-8') as f:
                package_data = json.load(f)
            
            # Update status fields
            package_data['status'] = status.value
            if external_id:
                package_data['external_id'] = external_id
            if posted_at:
                package_data['posted_at'] = posted_at.isoformat()
            
            # Save updated package data
            with open(package_file, 'w', encoding='utf-8') as f:
                json.dump(package_data, f, indent=2, default=str)
            
            return True
            
        except (json.JSONDecodeError, IOError):
            return False


def create_social_generator(profile_config_path: Union[str, Path],
                          temp_dir: Optional[Union[str, Path]] = None) -> SocialGenerator:
    """
    Factory function to create social generator with loaded profiles
    
    Args:
        profile_config_path: Path to platform profiles configuration
        temp_dir: Optional temporary directory
        
    Returns:
        SocialGenerator instance
    """
    # Load platform profiles
    profile_loader = PlatformProfileLoader(profile_config_path)
    profile_loader.load_profiles()
    
    return SocialGenerator(profile_loader, temp_dir)