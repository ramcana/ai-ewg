"""
JSON-LD Schema Generator for Media Content

Generates structured data markup optimized for news and media discovery
with comprehensive TVEpisode and Person schema support, organization
and affiliation markup, and schema validation utilities.
"""

import json
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from urllib.parse import quote

from .config import PipelineConfig
from .logging import get_logger
from .models import EpisodeObject, EditorialContent, EnrichmentResult, EpisodeMetadata
from .exceptions import ProcessingError

logger = get_logger('pipeline.schema_generator')


@dataclass
class SchemaValidationResult:
    """Result of schema validation"""
    valid: bool
    schema_type: str
    warnings: List[str]
    errors: List[str]
    recommendations: List[str]
    compliance_score: float


class JSONLDSchemaGenerator:
    """
    JSON-LD schema generator for TV/journalistic content
    
    Creates structured data markup optimized for search engines and
    media discovery platforms with full compliance to Schema.org
    specifications for TVEpisode, Person, and Organization types.
    """
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.logger = logger
        
        # Schema configuration
        self.base_url = config.get('web', {}).get('base_url', '')
        self.organization_name = config.get('organization', {}).get('name', '')
        self.organization_url = config.get('organization', {}).get('url', '')
        
        # Schema.org context
        self.schema_context = "https://schema.org"
        
        # Supported schema types
        self.supported_types = {
            'TVEpisode', 'TVSeries', 'Person', 'Organization', 
            'VideoObject', 'AudioObject', 'CreativeWork'
        }
    
    def generate_tv_episode_schema(self, episode: EpisodeObject) -> Dict[str, Any]:
        """
        Generate comprehensive TVEpisode schema with complete metadata
        
        Args:
            episode: Episode object with all processing data
            
        Returns:
            Dict[str, Any]: Complete JSON-LD TVEpisode schema
        """
        try:
            self.logger.debug(
                "Generating TVEpisode schema",
                episode_id=episode.episode_id
            )
            
            # Base TVEpisode schema
            schema = {
                "@context": self.schema_context,
                "@type": "TVEpisode",
                "identifier": episode.episode_id,
                "url": self._generate_episode_url(episode),
                "dateCreated": episode.created_at.isoformat() if episode.created_at else None,
                "dateModified": episode.updated_at.isoformat() if episode.updated_at else None
            }
            
            # Add core episode information
            self._add_episode_core_info(schema, episode)
            
            # Add series information
            self._add_tv_series_info(schema, episode)
            
            # Add person/cast information
            self._add_cast_information(schema, episode)
            
            # Add organization information
            self._add_organization_info(schema, episode)
            
            # Add content and media information
            self._add_content_info(schema, episode)
            self._add_media_info(schema, episode)
            
            # Add editorial and SEO information
            self._add_editorial_info(schema, episode)
            
            # Add accessibility information
            self._add_accessibility_info(schema, episode)
            
            # Add production information
            self._add_production_info(schema, episode)
            
            self.logger.debug(
                "TVEpisode schema generated successfully",
                episode_id=episode.episode_id,
                schema_fields=len(schema)
            )
            
            return schema
        
        except Exception as e:
            error_msg = f"Failed to generate TVEpisode schema: {str(e)}"
            self.logger.error(error_msg, episode_id=episode.episode_id, exception=e)
            
            # Return minimal fallback schema
            return {
                "@context": self.schema_context,
                "@type": "TVEpisode",
                "identifier": episode.episode_id,
                "name": episode.episode_id
            }
    
    def generate_person_schema(self, person_data: Dict[str, Any], 
                             episode_context: Optional[EpisodeObject] = None) -> Dict[str, Any]:
        """
        Generate Person schema with complete metadata and affiliations
        
        Args:
            person_data: Person data from enrichment results
            episode_context: Optional episode context for additional info
            
        Returns:
            Dict[str, Any]: Complete Person schema
        """
        try:
            name = person_data.get('name', '')
            if not name:
                raise ValueError("Person name is required for schema generation")
            
            # Base Person schema
            schema = {
                "@type": "Person",
                "name": name
            }
            
            # Add job title and professional information
            if person_data.get('job_title'):
                schema["jobTitle"] = person_data['job_title']
            
            # Add affiliation as Organization
            if person_data.get('affiliation'):
                schema["worksFor"] = self._create_organization_schema(
                    person_data['affiliation']
                )
            
            # Add credibility and verification information
            self._add_person_credibility_info(schema, person_data)
            
            # Add biographical information
            self._add_person_biographical_info(schema, person_data)
            
            # Add same-as links for verification
            if person_data.get('same_as'):
                same_as_links = person_data['same_as']
                if isinstance(same_as_links, list):
                    schema["sameAs"] = same_as_links
                elif isinstance(same_as_links, str):
                    schema["sameAs"] = [same_as_links]
            
            # Add knowledge area/expertise
            if person_data.get('expertise_areas'):
                schema["knowsAbout"] = person_data['expertise_areas']
            
            return schema
        
        except Exception as e:
            self.logger.warning(
                "Failed to generate Person schema",
                person_name=person_data.get('name', 'Unknown'),
                exception=e
            )
            
            # Return minimal schema
            return {
                "@type": "Person",
                "name": person_data.get('name', 'Unknown Person')
            }
    
    def generate_organization_schema(self, org_name: str, 
                                   org_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generate Organization schema with complete metadata
        
        Args:
            org_name: Organization name
            org_data: Optional additional organization data
            
        Returns:
            Dict[str, Any]: Complete Organization schema
        """
        try:
            schema = {
                "@type": "Organization",
                "name": org_name
            }
            
            if org_data:
                # Add URL if available
                if org_data.get('url'):
                    schema["url"] = org_data['url']
                
                # Add description
                if org_data.get('description'):
                    schema["description"] = org_data['description']
                
                # Add location
                if org_data.get('location'):
                    schema["location"] = org_data['location']
                
                # Add industry/sector
                if org_data.get('industry'):
                    schema["industry"] = org_data['industry']
                
                # Add founding date
                if org_data.get('founded'):
                    schema["foundingDate"] = org_data['founded']
            
            return schema
        
        except Exception as e:
            self.logger.warning(
                "Failed to generate Organization schema",
                org_name=org_name,
                exception=e
            )
            
            return {
                "@type": "Organization",
                "name": org_name
            }
    
    def generate_video_object_schema(self, episode: EpisodeObject) -> Dict[str, Any]:
        """
        Generate VideoObject schema for the episode video content
        
        Args:
            episode: Episode object with media information
            
        Returns:
            Dict[str, Any]: VideoObject schema
        """
        try:
            schema = {
                "@type": "VideoObject",
                "name": self._get_episode_title(episode),
                "identifier": episode.episode_id
            }
            
            # Add description
            if episode.editorial and episode.editorial.summary:
                schema["description"] = episode.editorial.summary
            
            # Add duration
            if episode.media.duration_seconds:
                schema["duration"] = self._format_duration_iso8601(episode.media.duration_seconds)
            
            # Add video quality information
            if episode.media.resolution:
                schema["videoQuality"] = episode.media.resolution
            
            # Add encoding format
            if episode.media.video_codec:
                schema["encodingFormat"] = episode.media.video_codec
            
            # Add upload date
            if episode.created_at:
                schema["uploadDate"] = episode.created_at.isoformat()
            
            # Add content URL (placeholder)
            video_url = self._generate_video_url(episode)
            if video_url:
                schema["contentUrl"] = video_url
            
            # Add thumbnail URL (placeholder)
            thumbnail_url = self._generate_thumbnail_url(episode)
            if thumbnail_url:
                schema["thumbnailUrl"] = thumbnail_url
            
            # Add transcript as associated media
            if episode.transcription:
                schema["transcript"] = {
                    "@type": "MediaObject",
                    "encodingFormat": "text/plain",
                    "contentUrl": self._generate_transcript_url(episode)
                }
            
            return schema
        
        except Exception as e:
            self.logger.warning(
                "Failed to generate VideoObject schema",
                episode_id=episode.episode_id,
                exception=e
            )
            
            return {
                "@type": "VideoObject",
                "name": episode.episode_id
            }
    
    def validate_schema(self, schema: Dict[str, Any]) -> SchemaValidationResult:
        """
        Validate JSON-LD schema for compliance and completeness
        
        Args:
            schema: JSON-LD schema to validate
            
        Returns:
            SchemaValidationResult: Comprehensive validation results
        """
        try:
            schema_type = schema.get("@type", "Unknown")
            
            validation_result = SchemaValidationResult(
                valid=True,
                schema_type=schema_type,
                warnings=[],
                errors=[],
                recommendations=[],
                compliance_score=0.0
            )
            
            # Validate based on schema type
            if schema_type == "TVEpisode":
                self._validate_tv_episode_schema(schema, validation_result)
            elif schema_type == "Person":
                self._validate_person_schema(schema, validation_result)
            elif schema_type == "Organization":
                self._validate_organization_schema(schema, validation_result)
            elif schema_type == "VideoObject":
                self._validate_video_object_schema(schema, validation_result)
            else:
                validation_result.warnings.append(f"Unknown schema type: {schema_type}")
            
            # Calculate compliance score
            validation_result.compliance_score = self._calculate_compliance_score(
                schema, validation_result
            )
            
            # Determine overall validity
            validation_result.valid = len(validation_result.errors) == 0
            
            return validation_result
        
        except Exception as e:
            self.logger.error(
                "Schema validation failed",
                schema_type=schema.get("@type", "Unknown"),
                exception=e
            )
            
            return SchemaValidationResult(
                valid=False,
                schema_type="Unknown",
                warnings=[],
                errors=[f"Validation error: {str(e)}"],
                recommendations=["Manual schema review required"],
                compliance_score=0.0
            )
    
    # Private helper methods
    
    def _add_episode_core_info(self, schema: Dict[str, Any], episode: EpisodeObject) -> None:
        """Add core episode information to schema"""
        metadata = episode.metadata
        
        # Episode name/title
        title = self._get_episode_title(episode)
        schema["name"] = title
        
        # Episode description
        description = self._get_episode_description(episode)
        if description:
            schema["description"] = description
        
        # Episode numbers
        if metadata.season:
            schema["seasonNumber"] = metadata.season
        if metadata.episode:
            schema["episodeNumber"] = metadata.episode
        
        # Publication information
        if metadata.date:
            schema["datePublished"] = metadata.date
        
        # Content language
        schema["inLanguage"] = "en"  # Default to English
        
        # Content rating (default to general audience)
        schema["contentRating"] = "General Audience"
    
    def _add_tv_series_info(self, schema: Dict[str, Any], episode: EpisodeObject) -> None:
        """Add TV series information to schema"""
        if not episode.metadata.show_name:
            return
        
        series_schema = {
            "@type": "TVSeries",
            "name": episode.metadata.show_name,
            "identifier": episode.metadata.show_slug
        }
        
        # Add series URL if base URL is configured
        if self.base_url:
            series_url = f"{self.base_url.rstrip('/')}/{episode.metadata.show_slug}/"
            series_schema["url"] = series_url
        
        # Add genre (default for talk shows)
        series_schema["genre"] = ["Talk Show", "Interview", "News"]
        
        schema["partOfSeries"] = series_schema
    
    def _add_cast_information(self, schema: Dict[str, Any], episode: EpisodeObject) -> None:
        """Add cast/guest information to schema"""
        if not episode.enrichment or not episode.enrichment.proficiency_scores:
            return
        
        scores_data = episode.enrichment.proficiency_scores
        if 'scored_people' not in scores_data:
            return
        
        actors = []
        for person_data in scores_data['scored_people']:
            person_schema = self.generate_person_schema(person_data, episode)
            actors.append(person_schema)
        
        if actors:
            schema["actor"] = actors
    
    def _add_organization_info(self, schema: Dict[str, Any], episode: EpisodeObject) -> None:
        """Add organization information to schema"""
        # Production company (from show)
        if episode.metadata.show_name:
            schema["productionCompany"] = {
                "@type": "Organization",
                "name": episode.metadata.show_name
            }
        
        # Publisher organization
        if self.organization_name:
            publisher_schema = {
                "@type": "Organization",
                "name": self.organization_name
            }
            
            if self.organization_url:
                publisher_schema["url"] = self.organization_url
            
            schema["publisher"] = publisher_schema
    
    def _add_content_info(self, schema: Dict[str, Any], episode: EpisodeObject) -> None:
        """Add content information to schema"""
        # Genre classification
        schema["genre"] = ["Talk Show", "Interview"]
        
        # Keywords from topic tags
        if episode.editorial and episode.editorial.topic_tags:
            schema["keywords"] = episode.editorial.topic_tags
        
        # Content topics
        if episode.editorial and episode.editorial.topic_tags:
            schema["about"] = [
                {"@type": "Thing", "name": tag} 
                for tag in episode.editorial.topic_tags[:5]
            ]
        
        # Transcript excerpt
        if episode.transcription and episode.transcription.text:
            # Include first 500 characters as preview
            transcript_preview = episode.transcription.text[:500]
            if len(episode.transcription.text) > 500:
                transcript_preview += "..."
            schema["transcript"] = transcript_preview
    
    def _add_media_info(self, schema: Dict[str, Any], episode: EpisodeObject) -> None:
        """Add media information to schema"""
        media = episode.media
        
        # Duration in ISO 8601 format
        if media.duration_seconds:
            schema["duration"] = self._format_duration_iso8601(media.duration_seconds)
        
        # Video quality
        if media.resolution:
            schema["videoQuality"] = media.resolution
        
        # Encoding format
        if media.video_codec:
            schema["encodingFormat"] = media.video_codec
        
        # Associated media (video object)
        video_schema = self.generate_video_object_schema(episode)
        schema["associatedMedia"] = video_schema
    
    def _add_editorial_info(self, schema: Dict[str, Any], episode: EpisodeObject) -> None:
        """Add editorial information to schema"""
        if not episode.editorial:
            return
        
        editorial = episode.editorial
        
        # Headline (key takeaway)
        if editorial.key_takeaway:
            schema["headline"] = editorial.key_takeaway
        
        # Abstract (summary)
        if editorial.summary:
            schema["abstract"] = editorial.summary
        
        # Article body (for news-style content)
        if editorial.summary and editorial.key_takeaway:
            article_body = f"{editorial.key_takeaway}\n\n{editorial.summary}"
            schema["articleBody"] = article_body
    
    def _add_accessibility_info(self, schema: Dict[str, Any], episode: EpisodeObject) -> None:
        """Add accessibility information to schema"""
        accessibility_features = []
        
        # Transcript availability
        if episode.transcription:
            accessibility_features.append("transcript")
        
        # Captions availability (if VTT exists)
        if episode.transcription and episode.transcription.vtt_content:
            accessibility_features.append("captions")
        
        # Audio description (placeholder)
        # accessibility_features.append("audioDescription")
        
        if accessibility_features:
            schema["accessibilityFeature"] = accessibility_features
        
        # Accessibility summary
        schema["accessibilitySummary"] = "Episode includes transcript and captions for accessibility"
    
    def _add_production_info(self, schema: Dict[str, Any], episode: EpisodeObject) -> None:
        """Add production information to schema"""
        # Production date (creation date)
        if episode.created_at:
            schema["dateCreated"] = episode.created_at.isoformat()
        
        # Content location (if available)
        # This could be extracted from metadata or enrichment data
        # schema["contentLocation"] = {...}
        
        # Creator information (placeholder)
        if episode.metadata.show_name:
            schema["creator"] = {
                "@type": "Organization",
                "name": episode.metadata.show_name
            }
    
    def _add_person_credibility_info(self, schema: Dict[str, Any], person_data: Dict[str, Any]) -> None:
        """Add credibility information to person schema"""
        # Credibility badge as award or recognition
        badge = person_data.get('credibilityBadge', '')
        if badge and badge != 'Guest':
            schema["award"] = badge
        
        # Proficiency score as rating (if high enough)
        score = person_data.get('proficiencyScore', 0)
        if score >= 0.7:
            schema["rating"] = {
                "@type": "Rating",
                "ratingValue": score,
                "bestRating": 1.0,
                "worstRating": 0.0
            }
        
        # Reasoning as description
        reasoning = person_data.get('reasoning', '')
        if reasoning and len(reasoning) < 500:
            schema["description"] = reasoning
    
    def _add_person_biographical_info(self, schema: Dict[str, Any], person_data: Dict[str, Any]) -> None:
        """Add biographical information to person schema"""
        # This would be enhanced with additional biographical data
        # from disambiguation results
        
        # Professional background
        if person_data.get('professional_background'):
            schema["hasOccupation"] = {
                "@type": "Occupation",
                "name": person_data['professional_background']
            }
        
        # Education (if available)
        if person_data.get('education'):
            schema["alumniOf"] = {
                "@type": "EducationalOrganization",
                "name": person_data['education']
            }
    
    def _create_organization_schema(self, org_name: str) -> Dict[str, Any]:
        """Create organization schema for affiliations"""
        return {
            "@type": "Organization",
            "name": org_name
        }
    
    def _format_duration_iso8601(self, duration_seconds: float) -> str:
        """Format duration in ISO 8601 format"""
        hours = int(duration_seconds // 3600)
        minutes = int((duration_seconds % 3600) // 60)
        seconds = int(duration_seconds % 60)
        
        duration_str = "PT"
        if hours > 0:
            duration_str += f"{hours}H"
        if minutes > 0:
            duration_str += f"{minutes}M"
        if seconds > 0:
            duration_str += f"{seconds}S"
        
        return duration_str
    
    def _get_episode_title(self, episode: EpisodeObject) -> str:
        """Get the best available title for the episode"""
        if episode.metadata.title:
            return episode.metadata.title
        elif episode.editorial and episode.editorial.key_takeaway:
            return episode.editorial.key_takeaway
        elif episode.metadata.topic:
            return f"{episode.metadata.show_name or 'Episode'}: {episode.metadata.topic}"
        else:
            return episode.episode_id
    
    def _get_episode_description(self, episode: EpisodeObject) -> str:
        """Get the best available description for the episode"""
        if episode.editorial and episode.editorial.summary:
            return episode.editorial.summary
        elif episode.metadata.description:
            return episode.metadata.description
        elif episode.metadata.topic:
            return f"Discussion about {episode.metadata.topic}"
        else:
            return f"Episode {episode.episode_id}"
    
    def _generate_episode_url(self, episode: EpisodeObject) -> str:
        """Generate episode URL"""
        if not self.base_url:
            return ""
        
        path_parts = [episode.metadata.show_slug]
        if episode.metadata.season:
            path_parts.append(f"season-{episode.metadata.season}")
        path_parts.append(episode.episode_id)
        
        url_path = "/".join(path_parts)
        return f"{self.base_url.rstrip('/')}/{url_path}/"
    
    def _generate_video_url(self, episode: EpisodeObject) -> str:
        """Generate video content URL"""
        if not self.base_url:
            return ""
        
        episode_url = self._generate_episode_url(episode)
        return f"{episode_url}video.mp4"  # Placeholder
    
    def _generate_thumbnail_url(self, episode: EpisodeObject) -> str:
        """Generate thumbnail URL"""
        if not self.base_url:
            return ""
        
        episode_url = self._generate_episode_url(episode)
        return f"{episode_url}thumbnail.jpg"  # Placeholder
    
    def _generate_transcript_url(self, episode: EpisodeObject) -> str:
        """Generate transcript URL"""
        if not self.base_url:
            return ""
        
        episode_url = self._generate_episode_url(episode)
        return f"{episode_url}transcript.txt"
    
    # Schema validation methods
    
    def _validate_tv_episode_schema(self, schema: Dict[str, Any], 
                                  result: SchemaValidationResult) -> None:
        """Validate TVEpisode schema"""
        # Required fields
        required_fields = ["@context", "@type", "name"]
        for field in required_fields:
            if field not in schema:
                result.errors.append(f"Missing required field: {field}")
        
        # Check @context
        if schema.get("@context") != self.schema_context:
            result.errors.append(f"Invalid @context, must be '{self.schema_context}'")
        
        # Check @type
        if schema.get("@type") != "TVEpisode":
            result.errors.append("Invalid @type, must be 'TVEpisode'")
        
        # Recommended fields
        recommended_fields = ["description", "partOfSeries", "datePublished", "duration"]
        for field in recommended_fields:
            if field not in schema:
                result.warnings.append(f"Missing recommended field: {field}")
        
        # Validate partOfSeries
        if "partOfSeries" in schema:
            series = schema["partOfSeries"]
            if not isinstance(series, dict) or series.get("@type") != "TVSeries":
                result.warnings.append("partOfSeries should be a TVSeries object")
        
        # Validate duration format
        if "duration" in schema:
            duration = schema["duration"]
            if not isinstance(duration, str) or not duration.startswith("PT"):
                result.warnings.append("Duration should be in ISO 8601 format (PT...)")
        
        # SEO recommendations
        if "keywords" not in schema:
            result.recommendations.append("Add keywords for better SEO")
        
        if "genre" not in schema:
            result.recommendations.append("Add genre classification")
    
    def _validate_person_schema(self, schema: Dict[str, Any], 
                              result: SchemaValidationResult) -> None:
        """Validate Person schema"""
        # Required fields
        if schema.get("@type") != "Person":
            result.errors.append("Person @type must be 'Person'")
        
        if "name" not in schema:
            result.errors.append("Person must have name field")
        
        # Recommended fields
        recommended_fields = ["jobTitle", "worksFor"]
        for field in recommended_fields:
            if field not in schema:
                result.warnings.append(f"Person missing {field}")
        
        # Validate worksFor
        if "worksFor" in schema:
            org = schema["worksFor"]
            if not isinstance(org, dict) or org.get("@type") != "Organization":
                result.warnings.append("worksFor should be an Organization object")
    
    def _validate_organization_schema(self, schema: Dict[str, Any], 
                                    result: SchemaValidationResult) -> None:
        """Validate Organization schema"""
        if schema.get("@type") != "Organization":
            result.errors.append("Organization @type must be 'Organization'")
        
        if "name" not in schema:
            result.errors.append("Organization must have name field")
        
        # Recommended fields
        if "url" not in schema:
            result.recommendations.append("Add organization URL")
    
    def _validate_video_object_schema(self, schema: Dict[str, Any], 
                                    result: SchemaValidationResult) -> None:
        """Validate VideoObject schema"""
        if schema.get("@type") != "VideoObject":
            result.errors.append("VideoObject @type must be 'VideoObject'")
        
        if "name" not in schema:
            result.errors.append("VideoObject must have name field")
        
        # Recommended fields for video
        recommended_fields = ["description", "duration", "contentUrl"]
        for field in recommended_fields:
            if field not in schema:
                result.warnings.append(f"VideoObject missing {field}")
    
    def _calculate_compliance_score(self, schema: Dict[str, Any], 
                                  result: SchemaValidationResult) -> float:
        """Calculate schema compliance score"""
        total_points = 100
        
        # Deduct points for errors (major issues)
        error_penalty = len(result.errors) * 20
        
        # Deduct points for warnings (minor issues)
        warning_penalty = len(result.warnings) * 5
        
        # Deduct points for missing recommendations
        recommendation_penalty = len(result.recommendations) * 2
        
        # Calculate final score
        final_score = max(0, total_points - error_penalty - warning_penalty - recommendation_penalty)
        
        return final_score / 100.0


class SchemaTestingUtilities:
    """Testing utilities for JSON-LD schema validation"""
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.logger = get_logger('pipeline.schema_testing')
        self.schema_generator = JSONLDSchemaGenerator(config)
    
    def test_schema_with_google_validator(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Test schema with Google's Structured Data Testing Tool (simulation)
        
        Args:
            schema: JSON-LD schema to test
            
        Returns:
            Dict[str, Any]: Simulated validation results
        """
        # This would integrate with Google's testing API in a real implementation
        # For now, return a simulated result
        
        validation_result = self.schema_generator.validate_schema(schema)
        
        return {
            "valid": validation_result.valid,
            "warnings": validation_result.warnings,
            "errors": validation_result.errors,
            "compliance_score": validation_result.compliance_score,
            "google_compatible": validation_result.compliance_score >= 0.8,
            "recommendations": validation_result.recommendations
        }
    
    def generate_test_schemas(self) -> Dict[str, Dict[str, Any]]:
        """Generate test schemas for validation"""
        # This would create various test schemas for different scenarios
        return {
            "minimal_episode": {
                "@context": "https://schema.org",
                "@type": "TVEpisode",
                "name": "Test Episode"
            },
            "complete_episode": {
                "@context": "https://schema.org",
                "@type": "TVEpisode",
                "name": "Complete Test Episode",
                "description": "A complete episode for testing",
                "partOfSeries": {
                    "@type": "TVSeries",
                    "name": "Test Show"
                },
                "seasonNumber": 1,
                "episodeNumber": 1,
                "duration": "PT30M",
                "datePublished": "2024-01-01"
            }
        }
    
    def validate_all_test_schemas(self) -> Dict[str, Any]:
        """Validate all test schemas and return results"""
        test_schemas = self.generate_test_schemas()
        results = {}
        
        for schema_name, schema in test_schemas.items():
            validation_result = self.schema_generator.validate_schema(schema)
            results[schema_name] = {
                "valid": validation_result.valid,
                "compliance_score": validation_result.compliance_score,
                "issues": len(validation_result.errors) + len(validation_result.warnings)
            }
        
        return results