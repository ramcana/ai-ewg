"""
Platform Policy Engine

Loads and applies platform-specific policies for social media content generation.
Handles validation, transformation rules, and metadata requirements per platform.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of content validation against platform policy"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    score: float  # 0-100 validation score


@dataclass
class TransformationResult:
    """Result of content transformation for platform"""
    content: Dict[str, Any]
    applied_transformations: List[str]
    warnings: List[str]


class PlatformPolicyEngine:
    """
    Engine for loading and applying platform-specific policies

    Handles validation, transformation, and metadata generation for different
    social media platforms based on YAML policy configurations.
    """

    def __init__(self, config_dir: Optional[str] = None):
        """
        Initialize policy engine

        Args:
            config_dir: Directory containing platform YAML files
        """
        if config_dir is None:
            # Default to config/platforms relative to this file
            current_dir = Path(__file__).parent
            config_dir = current_dir.parent.parent / "config" / "platforms"

        self.config_dir = Path(config_dir)
        self.policies: Dict[str, Dict[str, Any]] = {}
        self._load_all_policies()

    def _load_all_policies(self) -> None:
        """Load all platform policy YAML files"""
        if not self.config_dir.exists():
            logger.warning(f"Policy config directory not found: {self.config_dir}")
            return

        policy_files = list(self.config_dir.glob("*.yaml"))
        logger.info(f"Found {len(policy_files)} policy files")

        for policy_file in policy_files:
            try:
                with open(policy_file, 'r', encoding='utf-8') as f:
                    policy_data = yaml.safe_load(f)

                platform = policy_data.get('platform')
                if platform:
                    self.policies[platform] = policy_data
                    logger.info(f"Loaded policy for {platform}")
                else:
                    logger.warning(f"No platform specified in {policy_file}")

            except Exception as e:
                logger.error(f"Failed to load policy file {policy_file}: {e}")

        logger.info(f"Successfully loaded {len(self.policies)} platform policies")

    def get_policy(self, platform: str) -> Optional[Dict[str, Any]]:
        """
        Get policy configuration for a platform

        Args:
            platform: Platform name (youtube, instagram, x, tiktok, facebook)

        Returns:
            Platform policy configuration or None if not found
        """
        return self.policies.get(platform.lower())

    def list_platforms(self) -> List[str]:
        """
        List all available platforms

        Returns:
            List of platform names
        """
        return list(self.policies.keys())

    def validate_content(self, platform: str, content: Dict[str, Any]) -> ValidationResult:
        """
        Validate content against platform policy

        Args:
            platform: Target platform
            content: Content to validate (video metadata, captions, etc.)

        Returns:
            ValidationResult with errors, warnings, and score
        """
        policy = self.get_policy(platform)
        if not policy:
            return ValidationResult(
                is_valid=False,
                errors=[f"Unknown platform: {platform}"],
                warnings=[],
                score=0.0
            )

        errors = []
        warnings = []
        score = 100.0

        # Video validation
        video_policy = policy.get('video', {})
        content_video = content.get('video', {})

        # Duration validation
        max_duration = video_policy.get('max_duration')
        min_duration = video_policy.get('min_duration')
        content_duration = content_video.get('duration_seconds', 0)

        if max_duration and content_duration > max_duration:
            errors.append(f"Video duration {content_duration}s exceeds platform limit of {max_duration}s")
            score -= 30

        if min_duration and content_duration < min_duration:
            errors.append(f"Video duration {content_duration}s is below platform minimum of {min_duration}s")
            score -= 20

        # Aspect ratio validation
        required_ratio = video_policy.get('aspect_ratio')
        content_ratio = content_video.get('aspect_ratio')

        if required_ratio and content_ratio:
            if required_ratio != content_ratio:
                # Check if strict validation is required
                if policy.get('validation', {}).get('aspect_ratio_strict', False):
                    errors.append(f"Aspect ratio {content_ratio} does not match required {required_ratio}")
                    score -= 25
                else:
                    warnings.append(f"Aspect ratio {content_ratio} differs from preferred {required_ratio}")

        # Metadata validation
        metadata_policy = policy.get('metadata', {})
        content_metadata = content.get('metadata', {})

        # Title validation
        title_policy = metadata_policy.get('title', {})
        content_title = content_metadata.get('title', '')

        if title_policy.get('required', False) and not content_title:
            errors.append("Title is required but missing")
            score -= 20

        max_title_length = title_policy.get('max_length')
        if max_title_length and len(content_title) > max_title_length:
            errors.append(f"Title length {len(content_title)} exceeds limit of {max_title_length}")
            score -= 15

        # Caption validation (for platforms that use captions instead of titles)
        caption_policy = metadata_policy.get('caption', {})
        content_caption = content_metadata.get('caption', '')

        if caption_policy.get('required', False) and not content_caption:
            errors.append("Caption is required but missing")
            score -= 20

        max_caption_length = caption_policy.get('max_length')
        if max_caption_length and len(content_caption) > max_caption_length:
            errors.append(f"Caption length {len(content_caption)} exceeds limit of {max_caption_length}")
            score -= 15

        # Hashtag validation
        hashtag_policy = metadata_policy.get('hashtags', {})
        content_hashtags = content_metadata.get('hashtags', [])

        max_hashtags = hashtag_policy.get('max_count')
        if max_hashtags and len(content_hashtags) > max_hashtags:
            errors.append(f"Too many hashtags ({len(content_hashtags)}), maximum is {max_hashtags}")
            score -= 10

        # Platform-specific validation rules
        validation_rules = policy.get('validation', {})

        if validation_rules.get('title_contains_show_name', False):
            show_name = content_metadata.get('show_name', '')
            if show_name and show_name.lower() not in content_title.lower():
                warnings.append("Title should contain show name for better discoverability")

        if validation_rules.get('caption_has_hashtags', False) and not content_hashtags:
            warnings.append("Platform recommends including hashtags in caption")

        # Ensure score doesn't go below 0
        score = max(0.0, score)

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            score=score
        )

    def apply_transformations(self, platform: str, content: Dict[str, Any]) -> TransformationResult:
        """
        Apply platform-specific transformations to content

        Args:
            platform: Target platform
            content: Content to transform

        Returns:
            TransformationResult with transformed content
        """
        policy = self.get_policy(platform)
        if not policy:
            return TransformationResult(
                content=content,
                applied_transformations=[],
                warnings=[f"Unknown platform: {platform}"]
            )

        transformed_content = content.copy()
        applied_transformations = []
        warnings = []

        transformations = policy.get('transformations', {})

        # Video transformations
        if transformations.get('aspect_ratio_correction'):
            # Apply aspect ratio correction logic here
            applied_transformations.append("aspect_ratio_correction")

        if transformations.get('resolution_upscaling'):
            # Apply resolution upscaling logic here
            applied_transformations.append("resolution_upscaling")

        if transformations.get('compression_quality'):
            # Apply compression quality settings here
            applied_transformations.append("compression_quality")

        if transformations.get('audio_normalization'):
            # Apply audio normalization logic here
            applied_transformations.append("audio_normalization")

        # Metadata transformations
        metadata_transforms = self._apply_metadata_transformations(platform, content.get('metadata', {}))
        if metadata_transforms['transformed']:
            transformed_content['metadata'] = metadata_transforms['metadata']
            applied_transformations.extend(metadata_transforms['transformations'])
            warnings.extend(metadata_transforms['warnings'])

        return TransformationResult(
            content=transformed_content,
            applied_transformations=applied_transformations,
            warnings=warnings
        )

    def _apply_metadata_transformations(self, platform: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply metadata transformations for platform

        Args:
            platform: Target platform
            metadata: Metadata to transform

        Returns:
            Dict with transformed metadata and transformation info
        """
        policy = self.get_policy(platform)
        if not policy:
            return {
                'transformed': False,
                'metadata': metadata,
                'transformations': [],
                'warnings': []
            }

        transformed_metadata = metadata.copy()
        transformations = []
        warnings = []

        metadata_policy = policy.get('metadata', {})

        # Apply title template
        title_policy = metadata_policy.get('title', {})
        title_template = title_policy.get('template')
        if title_template and metadata.get('title'):
            try:
                transformed_title = self._apply_template(title_template, metadata)
                if transformed_title != metadata.get('title'):
                    transformed_metadata['title'] = transformed_title
                    transformations.append("title_template")
            except Exception as e:
                warnings.append(f"Failed to apply title template: {e}")

        # Apply caption template (for Instagram, TikTok)
        caption_policy = metadata_policy.get('caption', {})
        caption_template = caption_policy.get('template')
        if caption_template:
            try:
                transformed_caption = self._apply_template(caption_template, metadata)
                transformed_metadata['caption'] = transformed_caption
                transformations.append("caption_template")
            except Exception as e:
                warnings.append(f"Failed to apply caption template: {e}")

        # Apply hashtag formatting
        hashtag_policy = metadata_policy.get('hashtags', {})
        hashtags = metadata.get('hashtags', [])
        if hashtags:
            formatted_hashtags = self._format_hashtags(hashtags, hashtag_policy)
            if formatted_hashtags != hashtags:
                transformed_metadata['hashtags'] = formatted_hashtags
                transformations.append("hashtag_formatting")

        return {
            'transformed': len(transformations) > 0,
            'metadata': transformed_metadata,
            'transformations': transformations,
            'warnings': warnings
        }

    def _apply_template(self, template: str, variables: Dict[str, Any]) -> str:
        """
        Apply template with variable substitution

        Args:
            template: Template string with {variable} placeholders
            variables: Dictionary of variable values

        Returns:
            Template with variables substituted
        """
        result = template

        # Handle common variables
        var_map = {
            'title': variables.get('title', ''),
            'show': variables.get('show_name', ''),
            'guest': ', '.join(variables.get('guests', [])),
            'guests': ', '.join(variables.get('guests', [])),
            'topics': ', '.join(variables.get('topics', [])),
            'summary': variables.get('summary', ''),
            'hook_line': variables.get('hook_line', ''),
            'canonical_url': variables.get('canonical_url', ''),
            'hashtags': ' '.join(variables.get('hashtags', []))
        }

        for key, value in var_map.items():
            placeholder = f"{{{key}}}"
            result = result.replace(placeholder, str(value))

        return result.strip()

    def _format_hashtags(self, hashtags: List[str], policy: Dict[str, Any]) -> List[str]:
        """
        Format hashtags according to platform policy

        Args:
            hashtags: List of hashtag strings
            policy: Hashtag policy configuration

        Returns:
            Formatted hashtags
        """
        formatted = []
        style = policy.get('style', 'camelCase')
        format_type = policy.get('format', 'space_separated')

        for hashtag in hashtags:
            # Remove existing # if present
            clean_tag = hashtag.lstrip('#')

            if style == 'camelCase':
                # Convert to camelCase
                words = clean_tag.replace('_', ' ').replace('-', ' ').split()
                if words:
                    camel_case = words[0].lower() + ''.join(word.capitalize() for word in words[1:])
                    formatted.append(f"#{camel_case}")
            elif style == 'lowercase':
                formatted.append(f"#{clean_tag.lower()}")
            else:
                formatted.append(f"#{clean_tag}")

        return formatted

    def get_platform_requirements(self, platform: str) -> Dict[str, Any]:
        """
        Get human-readable platform requirements summary

        Args:
            platform: Target platform

        Returns:
            Dictionary with platform requirements
        """
        policy = self.get_policy(platform)
        if not policy:
            return {}

        video = policy.get('video', {})
        metadata = policy.get('metadata', {})

        return {
            'display_name': policy.get('display_name', platform.title()),
            'icon': policy.get('icon', '📱'),
            'video': {
                'aspect_ratio': video.get('aspect_ratio', 'Any'),
                'max_duration': f"{video.get('max_duration', 0)//60}:{video.get('max_duration', 0)%60:02d}",
                'min_duration': f"{video.get('min_duration', 0)//60}:{video.get('min_duration', 0)%60:02d}",
                'resolution': video.get('resolution', {}).get('preferred', 'Any')
            },
            'metadata': {
                'title_max_length': metadata.get('title', {}).get('max_length'),
                'caption_max_length': metadata.get('caption', {}).get('max_length'),
                'hashtags_max_count': metadata.get('hashtags', {}).get('max_count')
            },
            'features': policy.get('features', {})
        }


# Convenience function
def create_policy_engine(config_dir: Optional[str] = None) -> PlatformPolicyEngine:
    """
    Create and return a configured policy engine

    Args:
        config_dir: Directory containing platform YAML files

    Returns:
        PlatformPolicyEngine: Configured policy engine instance
    """
    return PlatformPolicyEngine(config_dir)
