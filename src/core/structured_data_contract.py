"""
Structured Data Contract System for Content Publishing Platform

Implements the standardized JSON-LD schema extending Schema.org VideoObject 
and TVEpisode for both web pages and social packages.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Set
from enum import Enum
import re
import json
from urllib.parse import urlparse

from .publishing_models import Episode, Series, Host, Person, ValidationResult, ValidationError, ValidationWarning, ErrorType, Severity


class SchemaType(Enum):
    """Supported Schema.org types"""
    VIDEO_OBJECT = "VideoObject"
    TV_EPISODE = "TVEpisode"
    TV_SERIES = "TVSeries"
    PERSON = "Person"
    ORGANIZATION = "Organization"


@dataclass
class FieldDefinition:
    """Definition of a required or optional field in the structured data contract"""
    name: str
    required: bool
    field_type: type
    description: str
    validation_pattern: Optional[str] = None
    allowed_values: Optional[List[str]] = None
    max_length: Optional[int] = None
    
    def validate_value(self, value: Any) -> List[str]:
        """Validate a field value against this definition"""
        errors = []
        
        # Check if required field is present
        if self.required and (value is None or value == ""):
            errors.append(f"Required field '{self.name}' is missing or empty")
            return errors
        
        # Skip validation if field is optional and not provided
        if not self.required and (value is None or value == ""):
            return errors
        
        # Type validation
        if not isinstance(value, self.field_type):
            if self.field_type == str and isinstance(value, (int, float)):
                value = str(value)  # Allow conversion to string
            else:
                errors.append(f"Field '{self.name}' must be of type {self.field_type.__name__}, got {type(value).__name__}")
                return errors
        
        # Pattern validation
        if self.validation_pattern and isinstance(value, str):
            if not re.match(self.validation_pattern, value):
                errors.append(f"Field '{self.name}' does not match required pattern: {self.validation_pattern}")
        
        # Allowed values validation
        if self.allowed_values and value not in self.allowed_values:
            errors.append(f"Field '{self.name}' must be one of {self.allowed_values}, got '{value}'")
        
        # Length validation
        if self.max_length and isinstance(value, str) and len(value) > self.max_length:
            errors.append(f"Field '{self.name}' exceeds maximum length of {self.max_length} characters")
        
        return errors


@dataclass
class StructuredDataContract:
    """
    Structured Data Contract defining required and optional fields for JSON-LD schema
    
    Based on Schema.org VideoObject and TVEpisode specifications with extensions
    for content publishing platform requirements.
    """
    
    # Core Schema.org fields
    CORE_FIELDS = [
        FieldDefinition("@context", True, str, "Schema.org context URL", 
                       validation_pattern=r"https://schema\.org/?"),
        FieldDefinition("@type", True, str, "Schema.org type",
                       allowed_values=["VideoObject", "TVEpisode"]),
        FieldDefinition("@id", True, str, "Unique identifier for the content"),
        FieldDefinition("identifier", True, str, "Stable UUID or slug identifier"),
        FieldDefinition("name", True, str, "Episode title", max_length=200),
        FieldDefinition("headline", True, str, "Episode headline", max_length=110),
        FieldDefinition("description", True, str, "Episode description", max_length=5000),
        FieldDefinition("uploadDate", True, str, "Upload date in ISO 8601 format",
                       validation_pattern=r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"),
        FieldDefinition("datePublished", True, str, "Publication date in ISO 8601 format",
                       validation_pattern=r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"),
        FieldDefinition("dateModified", True, str, "Last modification date in ISO 8601 format",
                       validation_pattern=r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"),
        FieldDefinition("duration", True, str, "Duration in ISO 8601 format",
                       validation_pattern=r"PT(\d+H)?(\d+M)?(\d+(\.\d+)?S)?"),
    ]
    
    # Extended fields for video content
    VIDEO_FIELDS = [
        FieldDefinition("contentUrl", False, str, "Direct URL to video content"),
        FieldDefinition("embedUrl", False, str, "Embeddable URL for video player"),
        FieldDefinition("thumbnailUrl", False, str, "URL to video thumbnail image"),
        FieldDefinition("videoQuality", False, str, "Video quality designation",
                       allowed_values=["HD", "SD", "4K", "1080p", "720p", "480p"]),
        FieldDefinition("encodingFormat", False, str, "Video encoding format",
                       allowed_values=["video/mp4", "video/webm", "video/avi", "video/mov"]),
        FieldDefinition("bitrate", False, str, "Video bitrate"),
        FieldDefinition("videoFrameSize", False, str, "Video frame dimensions",
                       validation_pattern=r"\d+x\d+"),
    ]
    
    # TV Episode specific fields
    TV_EPISODE_FIELDS = [
        FieldDefinition("episodeNumber", False, int, "Episode number within series"),
        FieldDefinition("seasonNumber", False, int, "Season number"),
        FieldDefinition("partOfSeries", True, dict, "Reference to parent TV series"),
        FieldDefinition("partOfSeason", False, dict, "Reference to parent season"),
    ]
    
    # Person and organization fields
    PERSON_FIELDS = [
        FieldDefinition("director", False, list, "Directors of the content"),
        FieldDefinition("actor", False, list, "Actors/hosts in the content"),
        FieldDefinition("creator", False, list, "Content creators"),
        FieldDefinition("producer", False, list, "Content producers"),
    ]
    
    # Publishing platform fields
    PUBLISHING_FIELDS = [
        FieldDefinition("publisher", True, dict, "Publishing organization"),
        FieldDefinition("copyrightHolder", False, dict, "Copyright holder information"),
        FieldDefinition("license", False, str, "Content license URL"),
        FieldDefinition("isAccessibleForFree", True, bool, "Whether content is free to access"),
        FieldDefinition("isFamilyFriendly", True, bool, "Family-friendly content flag"),
        FieldDefinition("inLanguage", True, str, "Content language code",
                       validation_pattern=r"[a-z]{2}(-[A-Z]{2})?"),
    ]
    
    # Social media and distribution fields
    SOCIAL_FIELDS = [
        FieldDefinition("keywords", False, list, "Content keywords/tags"),
        FieldDefinition("genre", False, list, "Content genres"),
        FieldDefinition("about", False, list, "Topics the content is about"),
        FieldDefinition("mentions", False, list, "People or organizations mentioned"),
        FieldDefinition("associatedMedia", False, list, "Associated media files"),
    ]
    
    # Validation and quality fields
    VALIDATION_FIELDS = [
        FieldDefinition("contentRating", False, str, "Content rating",
                       allowed_values=["G", "PG", "PG-13", "R", "NC-17", "TV-Y", "TV-Y7", "TV-G", "TV-PG", "TV-14", "TV-MA"]),
        FieldDefinition("accessibilityFeature", False, list, "Accessibility features"),
        FieldDefinition("accessibilityHazard", False, list, "Accessibility hazards"),
        FieldDefinition("accessibilitySummary", False, str, "Accessibility summary"),
    ]
    
    def __init__(self, schema_type: SchemaType = SchemaType.VIDEO_OBJECT):
        """Initialize structured data contract with specified schema type"""
        self.schema_type = schema_type
        self.required_fields: Set[str] = set()
        self.optional_fields: Set[str] = set()
        self.field_definitions: Dict[str, FieldDefinition] = {}
        
        # Build field definitions based on schema type
        self._build_field_definitions()
    
    def _build_field_definitions(self):
        """Build field definitions based on schema type"""
        # Always include core fields
        all_fields = self.CORE_FIELDS.copy()
        
        # Add video-specific fields
        all_fields.extend(self.VIDEO_FIELDS)
        
        # Add TV episode fields if applicable
        if self.schema_type == SchemaType.TV_EPISODE:
            all_fields.extend(self.TV_EPISODE_FIELDS)
        
        # Add person and organization fields
        all_fields.extend(self.PERSON_FIELDS)
        
        # Add publishing fields
        all_fields.extend(self.PUBLISHING_FIELDS)
        
        # Add social media fields
        all_fields.extend(self.SOCIAL_FIELDS)
        
        # Add validation fields
        all_fields.extend(self.VALIDATION_FIELDS)
        
        # Process field definitions
        for field_def in all_fields:
            self.field_definitions[field_def.name] = field_def
            if field_def.required:
                self.required_fields.add(field_def.name)
            else:
                self.optional_fields.add(field_def.name)    

    def validate_schema(self, data: Dict[str, Any]) -> ValidationResult:
        """
        Validate structured data against the contract
        
        Args:
            data: JSON-LD structured data to validate
            
        Returns:
            ValidationResult with validation status and any errors/warnings
        """
        errors = []
        warnings = []
        
        # Check required fields
        for field_name in self.required_fields:
            if field_name not in data:
                errors.append(ValidationError(
                    error_type=ErrorType.SCHEMA_VALIDATION,
                    message=f"Required field '{field_name}' is missing",
                    location=f"root.{field_name}",
                    severity=Severity.ERROR
                ))
        
        # Validate field values
        for field_name, value in data.items():
            if field_name in self.field_definitions:
                field_def = self.field_definitions[field_name]
                field_errors = field_def.validate_value(value)
                
                for error_msg in field_errors:
                    errors.append(ValidationError(
                        error_type=ErrorType.SCHEMA_VALIDATION,
                        message=error_msg,
                        location=f"root.{field_name}",
                        severity=Severity.ERROR
                    ))
            else:
                # Unknown field - add as warning
                warnings.append(ValidationWarning(
                    message=f"Unknown field '{field_name}' not in schema definition",
                    location=f"root.{field_name}"
                ))
        
        # Validate specific field combinations and relationships
        validation_errors, validation_warnings = self._validate_field_relationships(data)
        errors.extend(validation_errors)
        warnings.extend(validation_warnings)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            metadata={
                "schema_type": self.schema_type.value,
                "total_fields": len(data),
                "required_fields_count": len(self.required_fields),
                "optional_fields_count": len(self.optional_fields)
            }
        )
    
    def _validate_field_relationships(self, data: Dict[str, Any]) -> tuple[List[ValidationError], List[ValidationWarning]]:
        """Validate relationships between fields and complex validation rules"""
        errors = []
        warnings = []
        
        # Validate URL fields
        url_fields = ["@id", "contentUrl", "embedUrl", "thumbnailUrl", "license"]
        for field_name in url_fields:
            if field_name in data:
                url_value = data[field_name]
                if isinstance(url_value, str) and not self._is_valid_url(url_value):
                    errors.append(ValidationError(
                        error_type=ErrorType.SCHEMA_VALIDATION,
                        message=f"Field '{field_name}' must be a valid URL",
                        location=f"root.{field_name}",
                        severity=Severity.ERROR
                    ))
        
        # Validate date fields
        date_fields = ["uploadDate", "datePublished", "dateModified"]
        for field_name in date_fields:
            if field_name in data:
                date_value = data[field_name]
                if isinstance(date_value, str) and not self._is_valid_iso_date(date_value):
                    errors.append(ValidationError(
                        error_type=ErrorType.SCHEMA_VALIDATION,
                        message=f"Field '{field_name}' must be a valid ISO 8601 date",
                        location=f"root.{field_name}",
                        severity=Severity.ERROR
                    ))
        
        # Validate duration format
        if "duration" in data:
            duration_value = data["duration"]
            if isinstance(duration_value, str) and not self._is_valid_iso_duration(duration_value):
                errors.append(ValidationError(
                    error_type=ErrorType.SCHEMA_VALIDATION,
                    message="Field 'duration' must be a valid ISO 8601 duration (PT format)",
                    location="root.duration",
                    severity=Severity.ERROR
                ))
        
        # Validate TV episode specific relationships
        if self.schema_type == SchemaType.TV_EPISODE:
            if "partOfSeries" not in data:
                errors.append(ValidationError(
                    error_type=ErrorType.SCHEMA_VALIDATION,
                    message="TV episodes must reference a parent series via 'partOfSeries'",
                    location="root.partOfSeries",
                    severity=Severity.ERROR
                ))
        
        return errors, warnings
    
    def _is_valid_url(self, url: str) -> bool:
        """Validate URL format"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    def _is_valid_iso_date(self, date_str: str) -> bool:
        """Validate ISO 8601 date format"""
        try:
            datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return True
        except ValueError:
            return False
    
    def _is_valid_iso_duration(self, duration_str: str) -> bool:
        """Validate ISO 8601 duration format"""
        pattern = r'^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?$'
        return bool(re.match(pattern, duration_str))
    
    def generate_schema_from_episode(self, episode: Episode) -> Dict[str, Any]:
        """
        Generate JSON-LD structured data from Episode model
        
        Args:
            episode: Episode object to convert
            
        Returns:
            Dictionary containing JSON-LD structured data
        """
        # Base schema structure
        schema = {
            "@context": "https://schema.org",
            "@type": self.schema_type.value,
            "@id": f"https://example.com/episodes/{episode.episode_id}",
            "identifier": episode.episode_id,
            "name": episode.title,
            "headline": episode.title[:110],  # Truncate for headline
            "description": episode.description,
            "uploadDate": episode.upload_date.isoformat(),
            "datePublished": episode.upload_date.isoformat(),
            "dateModified": datetime.now().isoformat(),
            "duration": self._timedelta_to_iso_duration(episode.duration),
            "inLanguage": "en-US",  # Default language
            "isAccessibleForFree": True,
            "isFamilyFriendly": True,
        }
        
        # Add content URLs if available
        if episode.content_url:
            schema["contentUrl"] = episode.content_url
        
        if episode.thumbnail_url:
            schema["thumbnailUrl"] = episode.thumbnail_url
        
        # Add series information for TV episodes
        if self.schema_type == SchemaType.TV_EPISODE:
            schema["partOfSeries"] = {
                "@type": "TVSeries",
                "@id": f"https://example.com/series/{episode.series.series_id}",
                "name": episode.series.title,
                "description": episode.series.description
            }
            
            if episode.episode_number:
                schema["episodeNumber"] = episode.episode_number
            
            if episode.season_number:
                schema["seasonNumber"] = episode.season_number
        
        # Add host/actor information
        if episode.hosts:
            schema["actor"] = []
            for host in episode.hosts:
                schema["actor"].append({
                    "@type": "Person",
                    "@id": f"https://example.com/people/{host.person_id}",
                    "name": host.name,
                    "description": host.bio or f"Host of {episode.series.title}"
                })
        
        # Add publisher information
        schema["publisher"] = {
            "@type": "Organization",
            "name": "Content Publishing Platform",
            "url": "https://example.com"
        }
        
        # Add keywords/tags
        if episode.tags:
            schema["keywords"] = episode.tags
        
        return schema
    
    def _timedelta_to_iso_duration(self, td: timedelta) -> str:
        """Convert timedelta to ISO 8601 duration format"""
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        duration_parts = []
        if hours > 0:
            duration_parts.append(f"{hours}H")
        if minutes > 0:
            duration_parts.append(f"{minutes}M")
        if seconds > 0 or not duration_parts:  # Always include seconds if no other parts
            duration_parts.append(f"{seconds}S")
        
        return "PT" + "".join(duration_parts)


# Utility functions for working with structured data contracts

def create_video_contract() -> StructuredDataContract:
    """Create a structured data contract for VideoObject schema"""
    return StructuredDataContract(SchemaType.VIDEO_OBJECT)


def create_tv_episode_contract() -> StructuredDataContract:
    """Create a structured data contract for TVEpisode schema"""
    return StructuredDataContract(SchemaType.TV_EPISODE)


def validate_episode_schema(episode: Episode, schema_type: SchemaType = SchemaType.VIDEO_OBJECT) -> ValidationResult:
    """
    Validate an episode against structured data contract
    
    Args:
        episode: Episode object to validate
        schema_type: Type of schema to validate against
        
    Returns:
        ValidationResult with validation status and any errors/warnings
    """
    contract = StructuredDataContract(schema_type)
    schema_data = contract.generate_schema_from_episode(episode)
    return contract.validate_schema(schema_data)


def generate_episode_jsonld(episode: Episode, schema_type: SchemaType = SchemaType.VIDEO_OBJECT) -> str:
    """
    Generate JSON-LD structured data for an episode
    
    Args:
        episode: Episode object to convert
        schema_type: Type of schema to generate
        
    Returns:
        JSON-LD string representation
    """
    contract = StructuredDataContract(schema_type)
    schema_data = contract.generate_schema_from_episode(episode)
    return json.dumps(schema_data, indent=2, ensure_ascii=False)


@dataclass
class ManifestValidator:
    """
    Validator for publishing manifests and content contracts
    
    Provides comprehensive validation for manifest structure, content contracts,
    and Schema.org compliance across all content types.
    """
    
    def __init__(self):
        self.video_contract = create_video_contract()
        self.tv_episode_contract = create_tv_episode_contract()
    
    def validate_publish_manifest(self, manifest_data: Dict[str, Any]) -> ValidationResult:
        """
        Comprehensive validation of publishing manifest
        
        Args:
            manifest_data: Complete manifest data to validate
            
        Returns:
            ValidationResult with detailed validation information
        """
        errors = []
        warnings = []
        
        # Validate manifest structure
        structure_result = self._validate_manifest_structure(manifest_data)
        errors.extend(structure_result.errors)
        warnings.extend(structure_result.warnings)
        
        # Validate each episode's content contract
        if "episodes" in manifest_data and isinstance(manifest_data["episodes"], list):
            for i, episode_data in enumerate(manifest_data["episodes"]):
                episode_result = self._validate_episode_content_contract(episode_data, i)
                errors.extend(episode_result.errors)
                warnings.extend(episode_result.warnings)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            metadata={
                "total_episodes": len(manifest_data.get("episodes", [])),
                "validation_timestamp": datetime.now().isoformat()
            }
        )
    
    def _validate_manifest_structure(self, manifest_data: Dict[str, Any]) -> ValidationResult:
        """Validate basic manifest structure"""
        errors = []
        warnings = []
        
        # Required manifest fields
        required_manifest_fields = [
            "manifest_version", "build_id", "episodes", "series", "hosts", "paths"
        ]
        
        for field in required_manifest_fields:
            if field not in manifest_data:
                errors.append(ValidationError(
                    error_type=ErrorType.SCHEMA_VALIDATION,
                    message=f"Required manifest field '{field}' is missing",
                    location=f"manifest.{field}",
                    severity=Severity.ERROR
                ))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def _validate_episode_content_contract(self, episode_data: Dict[str, Any], index: int) -> ValidationResult:
        """Validate individual episode content contract"""
        errors = []
        warnings = []
        
        # Required fields for content contract
        required_fields = [
            "episode_id", "title", "description", "upload_date", 
            "duration", "series", "hosts"
        ]
        
        for field in required_fields:
            if field not in episode_data:
                errors.append(ValidationError(
                    error_type=ErrorType.SCHEMA_VALIDATION,
                    message=f"Episode {index} missing required field '{field}' for content contract",
                    location=f"episodes[{index}].{field}",
                    severity=Severity.ERROR
                ))
        
        # Validate episode ID format
        if "episode_id" in episode_data:
            episode_id = episode_data["episode_id"]
            if not isinstance(episode_id, str) or len(episode_id) < 3:
                errors.append(ValidationError(
                    error_type=ErrorType.SCHEMA_VALIDATION,
                    message=f"Episode {index} has invalid episode_id format",
                    location=f"episodes[{index}].episode_id",
                    severity=Severity.ERROR
                ))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )


# Factory functions for creating validators

def create_manifest_validator() -> ManifestValidator:
    """Create a new manifest validator instance"""
    return ManifestValidator()


def validate_complete_manifest(manifest_data: Dict[str, Any]) -> ValidationResult:
    """
    Convenience function to validate a complete publishing manifest
    
    Args:
        manifest_data: Complete manifest data to validate
        
    Returns:
        ValidationResult with comprehensive validation information
    """
    validator = create_manifest_validator()
    return validator.validate_publish_manifest(manifest_data)