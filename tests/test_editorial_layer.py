"""
Tests for the Editorial Layer

Tests content generation, quality validation, SEO optimization,
and fact-checking functionality.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from src.core.editorial import (
    EditorialLayer, 
    EditorialQualityValidator,
    EditorialSEOOptimizer,
    EditorialFactChecker,
    ContentQualityMetrics
)
from src.core.config import PipelineConfig
from src.core.models import (
    EpisodeObject, 
    EditorialContent, 
    EpisodeMetadata, 
    TranscriptionResult,
    EnrichmentResult,
    SourceInfo,
    MediaInfo,
    ProcessingStage
)


@pytest.fixture
def config():
    """Create test configuration"""
    return PipelineConfig()


@pytest.fixture
def sample_episode():
    """Create sample episode for testing"""
    metadata = EpisodeMetadata(
        show_name="Tech Talk",
        show_slug="tech-talk",
        season=1,
        episode=5,
        date="2024-01-15",
        topic="Artificial Intelligence",
        topic_slug="artificial-intelligence"
    )
    
    source = SourceInfo(
        path="/test/video.mp4",
        file_size=1000000,
        last_modified=datetime.now()
    )
    
    media = MediaInfo(
        duration_seconds=3600.0,
        video_codec="h264",
        audio_codec="aac"
    )
    
    transcription = TranscriptionResult(
        text="Today we're discussing artificial intelligence and machine learning. "
             "Our guest is Dr. Sarah Johnson, a leading AI researcher at MIT. "
             "She explains how AI is transforming healthcare and finance. "
             "The key insight is that AI requires careful ethical consideration. "
             "Research shows that 70% of companies are adopting AI technologies. "
             "According to Dr. Johnson, the future of AI depends on responsible development.",
        vtt_content="WEBVTT\n\n00:00:00.000 --> 00:00:05.000\nToday we're discussing artificial intelligence",
        confidence=0.95
    )
    
    # Mock enrichment data
    enrichment = EnrichmentResult(
        entities={
            'candidates': [
                {
                    'name': 'Dr. Sarah Johnson',
                    'role_guess': 'AI Researcher',
                    'confidence': 0.9,
                    'quotes': ['AI requires careful ethical consideration']
                }
            ],
            'topics': ['Artificial Intelligence', 'Machine Learning', 'Healthcare', 'Finance']
        },
        proficiency_scores={
            'scored_people': [
                {
                    'name': 'Dr. Sarah Johnson',
                    'job_title': 'AI Researcher',
                    'affiliation': 'MIT',
                    'proficiencyScore': 0.85,
                    'credibilityBadge': 'Verified Expert'
                }
            ]
        }
    )
    
    episode = EpisodeObject(
        episode_id="tech-talk-s1e5-2024-01-15-artificial-intelligence",
        content_hash="test_hash",
        source=source,
        media=media,
        metadata=metadata,
        processing_stage=ProcessingStage.ENRICHED,
        transcription=transcription,
        enrichment=enrichment
    )
    
    return episode


class TestEditorialLayer:
    """Test the main EditorialLayer functionality"""
    
    def test_generate_editorial_content(self, config, sample_episode):
        """Test complete editorial content generation"""
        editorial_layer = EditorialLayer(config)
        
        result = editorial_layer.generate_editorial_content(sample_episode)
        
        assert isinstance(result, EditorialContent)
        assert result.key_takeaway is not None
        assert result.summary is not None
        assert len(result.topic_tags) > 0
        assert isinstance(result.related_episodes, list)
    
    def test_generate_key_takeaway(self, config, sample_episode):
        """Test key takeaway generation"""
        editorial_layer = EditorialLayer(config)
        
        takeaway = editorial_layer.generate_key_takeaway(
            sample_episode.transcription.text,
            sample_episode.enrichment,
            sample_episode.metadata
        )
        
        assert isinstance(takeaway, str)
        assert len(takeaway) > 0
        assert len(takeaway) <= editorial_layer.max_takeaway_length
        assert "artificial intelligence" in takeaway.lower() or "ai" in takeaway.lower()
    
    def test_create_episode_summary(self, config, sample_episode):
        """Test episode summary creation"""
        editorial_layer = EditorialLayer(config)
        
        summary = editorial_layer.create_episode_summary(
            sample_episode.transcription.text,
            sample_episode.metadata,
            sample_episode.enrichment
        )
        
        assert isinstance(summary, str)
        assert len(summary) > 0
        assert len(summary) <= editorial_layer.max_summary_length
        assert "Dr. Sarah Johnson" in summary or "AI" in summary
    
    def test_extract_topic_tags(self, config, sample_episode):
        """Test topic tag extraction"""
        editorial_layer = EditorialLayer(config)
        
        tags = editorial_layer.extract_topic_tags(
            sample_episode.transcription.text,
            sample_episode.enrichment
        )
        
        assert isinstance(tags, list)
        assert len(tags) > 0
        assert len(tags) <= editorial_layer.max_topics
        assert any("artificial intelligence" in tag.lower() or "ai" in tag.lower() for tag in tags)
    
    def test_validate_content_quality(self, config, sample_episode):
        """Test content quality validation"""
        editorial_layer = EditorialLayer(config)
        
        # Generate content first
        editorial_content = editorial_layer.generate_editorial_content(sample_episode)
        
        # Validate quality
        quality_metrics = editorial_layer.validate_content_quality(
            editorial_content,
            sample_episode.transcription.text
        )
        
        assert isinstance(quality_metrics, ContentQualityMetrics)
        assert 0.0 <= quality_metrics.overall_score <= 1.0
        assert 0.0 <= quality_metrics.readability_score <= 1.0
        assert 0.0 <= quality_metrics.engagement_score <= 1.0
        assert isinstance(quality_metrics.issues, list)
        assert isinstance(quality_metrics.recommendations, list)


class TestEditorialQualityValidator:
    """Test editorial quality validation"""
    
    def test_validate_editorial_workflow(self, config, sample_episode):
        """Test editorial workflow validation"""
        validator = EditorialQualityValidator(config)
        
        # Create editorial content
        editorial_content = EditorialContent(
            key_takeaway="AI requires ethical consideration for responsible development",
            summary="Tech Talk explores AI with Dr. Sarah Johnson, covering healthcare and finance applications.",
            topic_tags=["Artificial Intelligence", "Healthcare", "Finance", "Ethics"]
        )
        
        result = validator.validate_editorial_workflow(editorial_content, sample_episode)
        
        assert isinstance(result, dict)
        assert 'ready_for_review' in result
        assert 'review_priority' in result
        assert 'required_checks' in result
        assert 'recommendations' in result
        assert 'quality_flags' in result
        
        # Should be ready for review with complete content
        assert result['ready_for_review'] is True


class TestEditorialSEOOptimizer:
    """Test SEO optimization functionality"""
    
    def test_optimize_for_seo(self, config, sample_episode):
        """Test SEO optimization"""
        optimizer = EditorialSEOOptimizer(config)
        
        editorial_content = EditorialContent(
            key_takeaway="AI Ethics: Why Responsible Development Matters",
            summary="Exploring artificial intelligence ethics with MIT researcher Dr. Sarah Johnson, covering healthcare applications and responsible AI development.",
            topic_tags=["Artificial Intelligence", "AI Ethics", "Healthcare", "MIT"]
        )
        
        result = optimizer.optimize_for_seo(editorial_content, sample_episode)
        
        assert isinstance(result, dict)
        assert 'seo_score' in result
        assert 'meta_tags' in result
        assert 'structured_data' in result
        assert 0.0 <= result['seo_score'] <= 1.0
        
        # Check meta tags
        meta_tags = result['meta_tags']
        assert 'title' in meta_tags
        assert 'description' in meta_tags
        assert 'keywords' in meta_tags
        
        # Check structured data
        structured_data = result['structured_data']
        assert structured_data['@type'] == 'TVEpisode'
        assert 'name' in structured_data
        assert 'description' in structured_data


class TestEditorialFactChecker:
    """Test fact-checking functionality"""
    
    def test_validate_against_source_material(self, config, sample_episode):
        """Test fact-checking validation"""
        fact_checker = EditorialFactChecker(config)
        
        editorial_content = EditorialContent(
            key_takeaway="Research shows 70% of companies adopt AI technologies",
            summary="Dr. Sarah Johnson from MIT discusses AI applications in healthcare and finance.",
            topic_tags=["Artificial Intelligence", "Healthcare", "Finance"]
        )
        
        result = fact_checker.validate_against_source_material(editorial_content, sample_episode)
        
        assert isinstance(result, dict)
        assert 'accuracy_score' in result
        assert 'potential_issues' in result
        assert 'verified_claims' in result
        assert 'confidence_level' in result
        
        assert 0.0 <= result['accuracy_score'] <= 1.0
        assert result['confidence_level'] in ['high', 'medium', 'low']
        
        # Should have high accuracy since content matches transcript
        assert result['accuracy_score'] >= 0.7


class TestEditorialIntegration:
    """Test integration between editorial components"""
    
    def test_complete_editorial_pipeline(self, config, sample_episode):
        """Test complete editorial processing pipeline"""
        # Initialize all components
        editorial_layer = EditorialLayer(config)
        validator = EditorialQualityValidator(config)
        seo_optimizer = EditorialSEOOptimizer(config)
        fact_checker = EditorialFactChecker(config)
        
        # Generate editorial content
        editorial_content = editorial_layer.generate_editorial_content(sample_episode)
        
        # Validate quality
        quality_metrics = editorial_layer.validate_content_quality(
            editorial_content,
            sample_episode.transcription.text
        )
        
        # Validate workflow
        workflow_result = validator.validate_editorial_workflow(editorial_content, sample_episode)
        
        # Optimize for SEO
        seo_result = seo_optimizer.optimize_for_seo(editorial_content, sample_episode)
        
        # Fact-check content
        fact_check_result = fact_checker.validate_against_source_material(
            editorial_content, sample_episode
        )
        
        # Verify all components worked
        assert editorial_content is not None
        assert quality_metrics.overall_score > 0
        assert workflow_result['ready_for_review'] is True
        assert seo_result['seo_score'] > 0
        assert fact_check_result['accuracy_score'] > 0
        
        # Update editorial content with scores
        editorial_content.quality_score = quality_metrics.overall_score
        editorial_content.seo_score = seo_result['seo_score']
        editorial_content.fact_check_score = fact_check_result['accuracy_score']
        
        # Verify updated content
        assert editorial_content.quality_score is not None
        assert editorial_content.seo_score is not None
        assert editorial_content.fact_check_score is not None


if __name__ == "__main__":
    pytest.main([__file__])