"""
Editorial Layer for the Video Processing Pipeline

Generates engaging, journalistic-quality content summaries, key takeaways,
and topic tags with TV/journalistic presentation standards.
"""

import re
import json
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

from .config import PipelineConfig
from .logging import get_logger
from .models import EpisodeObject, EditorialContent, EnrichmentResult, EpisodeMetadata
from .exceptions import ProcessingError

logger = get_logger('pipeline.editorial')


@dataclass
class ContentQualityMetrics:
    """Metrics for assessing content quality"""
    readability_score: float
    engagement_score: float
    seo_score: float
    fact_check_score: float
    overall_score: float
    issues: List[str]
    recommendations: List[str]


class EditorialLayer:
    """
    Editorial layer for generating TV/journalistic content
    
    Generates key takeaways, summaries, topic tags, and related content
    identification using journalistic writing standards.
    """
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.logger = logger
        
        # Journalistic writing standards
        self.max_summary_length = 300
        self.max_takeaway_length = 150
        self.min_topic_confidence = 0.7
        self.max_topics = 8
        
        # SEO optimization parameters
        self.target_summary_words = 50
        self.key_phrase_density_target = 0.02
        
        # Editorial quality thresholds
        self.min_readability_score = 0.6
        self.min_engagement_score = 0.7
        self.min_fact_check_score = 0.8
    
    def generate_editorial_content(self, episode: EpisodeObject) -> EditorialContent:
        """
        Generate complete editorial content for an episode
        
        Args:
            episode: Episode object with transcription and enrichment data
            
        Returns:
            EditorialContent: Generated editorial content
            
        Raises:
            ProcessingError: If content generation fails
        """
        self.logger.info(
            "Generating editorial content",
            episode_id=episode.episode_id
        )
        
        try:
            # Extract required data
            transcript_text = self._get_transcript_text(episode)
            enrichment = episode.enrichment
            metadata = episode.metadata
            
            # Generate key takeaway
            key_takeaway = self.generate_key_takeaway(
                transcript_text, 
                enrichment, 
                metadata
            )
            
            # Generate episode summary
            summary = self.create_episode_summary(
                transcript_text,
                metadata, 
                enrichment
            )
            
            # Extract topic tags
            topic_tags = self.extract_topic_tags(
                transcript_text, 
                enrichment
            )
            
            # Find related episodes (placeholder for now)
            related_episodes = self.find_related_content(episode, [])
            
            editorial_content = EditorialContent(
                key_takeaway=key_takeaway,
                summary=summary,
                topic_tags=topic_tags,
                related_episodes=related_episodes
            )
            
            self.logger.info(
                "Editorial content generated successfully",
                episode_id=episode.episode_id,
                summary_length=len(summary) if summary else 0,
                takeaway_length=len(key_takeaway) if key_takeaway else 0,
                num_topics=len(topic_tags)
            )
            
            return editorial_content
        
        except Exception as e:
            error_msg = f"Failed to generate editorial content: {str(e)}"
            self.logger.error(error_msg, episode_id=episode.episode_id, exception=e)
            raise ProcessingError(error_msg, stage="editorial_generation")
    
    def generate_key_takeaway(self, transcript: str, enrichment: Optional[EnrichmentResult], 
                            metadata: EpisodeMetadata) -> str:
        """
        Generate a compelling key takeaway using editorial writing standards
        
        Args:
            transcript: Full transcript text
            enrichment: AI enrichment results
            metadata: Episode metadata
            
        Returns:
            str: Key takeaway (max 150 characters)
        """
        try:
            # Extract key insights from transcript
            key_insights = self._extract_key_insights(transcript, enrichment)
            
            # Get main topic from metadata or enrichment
            main_topic = self._identify_main_topic(transcript, enrichment, metadata)
            
            # Generate takeaway based on insights and topic
            if key_insights and main_topic:
                # Create engaging takeaway with journalistic hook
                takeaway = self._craft_takeaway_with_hook(key_insights, main_topic)
            elif key_insights:
                # Use strongest insight as takeaway
                takeaway = key_insights[0]
            elif main_topic:
                # Create topic-based takeaway
                takeaway = f"Exploring {main_topic}: insights from industry experts"
            else:
                # Fallback to metadata-based takeaway
                show_name = metadata.show_name or "this episode"
                takeaway = f"Key insights and expert perspectives from {show_name}"
            
            # Ensure proper length and formatting
            takeaway = self._format_takeaway(takeaway)
            
            return takeaway
        
        except Exception as e:
            self.logger.warning(
                "Failed to generate key takeaway, using fallback",
                exception=e
            )
            return f"Expert insights from {metadata.show_name or 'this episode'}"
    
    def create_episode_summary(self, transcript: str, metadata: EpisodeMetadata, 
                             enrichment: Optional[EnrichmentResult]) -> str:
        """
        Create an engaging episode summary with professional tone
        
        Args:
            transcript: Full transcript text
            metadata: Episode metadata
            enrichment: AI enrichment results
            
        Returns:
            str: Episode summary (target ~50 words, max 300 characters)
        """
        try:
            # Extract key discussion points
            discussion_points = self._extract_discussion_points(transcript, enrichment)
            
            # Get guest information
            guests = self._extract_guest_info(enrichment)
            
            # Get main topics
            topics = self._extract_main_topics(transcript, enrichment)
            
            # Craft summary with journalistic structure
            summary = self._craft_journalistic_summary(
                metadata, discussion_points, guests, topics
            )
            
            # Optimize for SEO and readability
            summary = self._optimize_summary_seo(summary, topics)
            
            return summary
        
        except Exception as e:
            self.logger.warning(
                "Failed to generate episode summary, using fallback",
                exception=e
            )
            return self._create_fallback_summary(metadata)
    
    def extract_topic_tags(self, transcript: str, 
                          enrichment: Optional[EnrichmentResult]) -> List[str]:
        """
        Extract topic tags optimized for media content
        
        Args:
            transcript: Full transcript text
            enrichment: AI enrichment results
            
        Returns:
            List[str]: Topic tags (max 8, sorted by relevance)
        """
        try:
            tags = []
            
            # Extract from enrichment data if available
            if enrichment and enrichment.entities:
                entities_data = enrichment.entities
                
                # Get topics from entity extraction
                if 'topics' in entities_data:
                    for topic in entities_data['topics']:
                        if isinstance(topic, dict):
                            tag = topic.get('name', '').strip()
                            confidence = topic.get('confidence', 0)
                        else:
                            tag = str(topic).strip()
                            confidence = 0.8  # Default confidence
                        
                        if tag and confidence >= self.min_topic_confidence:
                            tags.append(tag)
                
                # Extract from people/organizations
                if 'candidates' in entities_data:
                    for candidate in entities_data['candidates'][:3]:  # Top 3 people
                        role = candidate.get('role_guess', '').strip()
                        if role and len(role.split()) <= 3:  # Keep role tags short
                            tags.append(role.title())
            
            # Extract from transcript using keyword analysis
            transcript_tags = self._extract_transcript_keywords(transcript)
            tags.extend(transcript_tags)
            
            # Clean and deduplicate tags
            tags = self._clean_and_deduplicate_tags(tags)
            
            # Sort by relevance and limit
            tags = self._rank_tags_by_relevance(tags, transcript)[:self.max_topics]
            
            return tags
        
        except Exception as e:
            self.logger.warning(
                "Failed to extract topic tags, using fallback",
                exception=e
            )
            return self._extract_fallback_tags(transcript)
    
    def find_related_content(self, episode: EpisodeObject, 
                           all_episodes: List[EpisodeObject]) -> List[str]:
        """
        Identify related episodes for cross-referencing
        
        Args:
            episode: Current episode
            all_episodes: List of all available episodes
            
        Returns:
            List[str]: Episode IDs of related content
        """
        try:
            related = []
            
            if not all_episodes:
                return related
            
            # Get current episode topics and guests
            current_topics = set()
            current_guests = set()
            
            if episode.editorial and episode.editorial.topic_tags:
                current_topics.update(tag.lower() for tag in episode.editorial.topic_tags)
            
            if episode.enrichment and episode.enrichment.proficiency_scores:
                scores_data = episode.enrichment.proficiency_scores
                if 'scored_people' in scores_data:
                    for person in scores_data['scored_people']:
                        name = person.get('name', '').lower()
                        if name:
                            current_guests.add(name)
            
            # Find episodes with similar topics or guests
            for other_episode in all_episodes:
                if other_episode.episode_id == episode.episode_id:
                    continue
                
                similarity_score = 0
                
                # Check topic overlap
                if other_episode.editorial and other_episode.editorial.topic_tags:
                    other_topics = set(tag.lower() for tag in other_episode.editorial.topic_tags)
                    topic_overlap = len(current_topics & other_topics)
                    similarity_score += topic_overlap * 0.3
                
                # Check guest overlap
                if other_episode.enrichment and other_episode.enrichment.proficiency_scores:
                    other_scores = other_episode.enrichment.proficiency_scores
                    if 'scored_people' in other_scores:
                        other_guests = set()
                        for person in other_scores['scored_people']:
                            name = person.get('name', '').lower()
                            if name:
                                other_guests.add(name)
                        
                        guest_overlap = len(current_guests & other_guests)
                        similarity_score += guest_overlap * 0.5
                
                # Check same show
                if (episode.get_show_slug() == other_episode.get_show_slug()):
                    similarity_score += 0.2
                
                # Add if similarity threshold met
                if similarity_score >= 0.5:
                    related.append((other_episode.episode_id, similarity_score))
            
            # Sort by similarity and return top 3
            related.sort(key=lambda x: x[1], reverse=True)
            return [episode_id for episode_id, _ in related[:3]]
        
        except Exception as e:
            self.logger.warning(
                "Failed to find related content",
                episode_id=episode.episode_id,
                exception=e
            )
            return []
    
    def validate_content_quality(self, editorial_content: EditorialContent,
                               transcript: str) -> ContentQualityMetrics:
        """
        Validate editorial content quality for readability and engagement
        
        Args:
            editorial_content: Generated editorial content
            transcript: Original transcript for fact-checking
            
        Returns:
            ContentQualityMetrics: Quality assessment metrics
        """
        try:
            issues = []
            recommendations = []
            
            # Readability assessment
            readability_score = self._assess_readability(editorial_content)
            if readability_score < self.min_readability_score:
                issues.append("Content readability below target")
                recommendations.append("Simplify language and sentence structure")
            
            # Engagement assessment
            engagement_score = self._assess_engagement(editorial_content)
            if engagement_score < self.min_engagement_score:
                issues.append("Content engagement below target")
                recommendations.append("Add more compelling hooks and active voice")
            
            # SEO optimization assessment
            seo_score = self._assess_seo_optimization(editorial_content)
            if seo_score < 0.7:
                recommendations.append("Optimize keyword density and meta descriptions")
            
            # Fact-checking validation
            fact_check_score = self._validate_against_source(editorial_content, transcript)
            if fact_check_score < self.min_fact_check_score:
                issues.append("Potential factual inconsistencies detected")
                recommendations.append("Review content against source material")
            
            # Calculate overall score
            overall_score = (
                readability_score * 0.25 +
                engagement_score * 0.35 +
                seo_score * 0.20 +
                fact_check_score * 0.20
            )
            
            return ContentQualityMetrics(
                readability_score=readability_score,
                engagement_score=engagement_score,
                seo_score=seo_score,
                fact_check_score=fact_check_score,
                overall_score=overall_score,
                issues=issues,
                recommendations=recommendations
            )
        
        except Exception as e:
            self.logger.warning(
                "Failed to validate content quality",
                exception=e
            )
            return ContentQualityMetrics(
                readability_score=0.5,
                engagement_score=0.5,
                seo_score=0.5,
                fact_check_score=0.5,
                overall_score=0.5,
                issues=["Quality validation failed"],
                recommendations=["Manual review recommended"]
            )
    
    # Private helper methods
    
    def _get_transcript_text(self, episode: EpisodeObject) -> str:
        """Extract transcript text from episode"""
        if episode.transcription and episode.transcription.text:
            return episode.transcription.text
        raise ProcessingError("No transcript available for editorial processing")
    
    def _extract_key_insights(self, transcript: str, 
                            enrichment: Optional[EnrichmentResult]) -> List[str]:
        """Extract key insights from transcript and enrichment data"""
        insights = []
        
        # Look for insight patterns in transcript
        insight_patterns = [
            r"the key (?:point|insight|finding) is (.+?)[\.\!\?]",
            r"what's (?:important|crucial|significant) (?:here|is) (.+?)[\.\!\?]",
            r"the (?:main|primary|central) (?:issue|challenge|opportunity) (.+?)[\.\!\?]",
            r"(?:research|data|studies) (?:shows?|indicates?|suggests?) (.+?)[\.\!\?]"
        ]
        
        for pattern in insight_patterns:
            matches = re.findall(pattern, transcript, re.IGNORECASE)
            for match in matches[:2]:  # Limit to 2 per pattern
                insight = match.strip()
                if len(insight) > 20 and len(insight) < 100:
                    insights.append(insight)
        
        return insights[:3]  # Return top 3 insights
    
    def _identify_main_topic(self, transcript: str, enrichment: Optional[EnrichmentResult],
                           metadata: EpisodeMetadata) -> Optional[str]:
        """Identify the main topic of discussion"""
        # Try metadata first
        if metadata.topic:
            return metadata.topic
        
        # Try enrichment data
        if enrichment and enrichment.entities and 'topics' in enrichment.entities:
            topics = enrichment.entities['topics']
            if topics:
                # Get highest confidence topic
                if isinstance(topics[0], dict):
                    return topics[0].get('name')
                else:
                    return str(topics[0])
        
        # Extract from transcript title patterns
        title_patterns = [
            r"(?:today|this episode) (?:we're|we are) (?:talking about|discussing) (.+?)[\.\,]",
            r"(?:the topic|subject) (?:today|is) (.+?)[\.\,]",
            r"(?:we're here to|let's) (?:talk about|discuss) (.+?)[\.\,]"
        ]
        
        for pattern in title_patterns:
            match = re.search(pattern, transcript[:500], re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _craft_takeaway_with_hook(self, insights: List[str], topic: str) -> str:
        """Craft an engaging takeaway with journalistic hook"""
        if not insights:
            return f"Expert insights on {topic}"
        
        # Use the strongest insight as the base
        main_insight = insights[0]
        
        # Create engaging hooks
        hooks = [
            f"Why {topic} matters: {main_insight}",
            f"The {topic} reality: {main_insight}",
            f"Breaking down {topic}: {main_insight}",
            f"{topic} explained: {main_insight}"
        ]
        
        # Choose the hook that fits best within length limit
        for hook in hooks:
            if len(hook) <= self.max_takeaway_length:
                return hook
        
        # Fallback: truncate if needed
        return main_insight[:self.max_takeaway_length-3] + "..."
    
    def _format_takeaway(self, takeaway: str) -> str:
        """Format takeaway for proper length and style"""
        # Clean up the text
        takeaway = re.sub(r'\s+', ' ', takeaway.strip())
        
        # Ensure proper capitalization
        takeaway = takeaway[0].upper() + takeaway[1:] if takeaway else ""
        
        # Truncate if too long
        if len(takeaway) > self.max_takeaway_length:
            # Try to break at a word boundary
            truncated = takeaway[:self.max_takeaway_length-3]
            last_space = truncated.rfind(' ')
            if last_space > self.max_takeaway_length * 0.8:
                takeaway = truncated[:last_space] + "..."
            else:
                takeaway = truncated + "..."
        
        return takeaway   
 
    def _extract_discussion_points(self, transcript: str, 
                                 enrichment: Optional[EnrichmentResult]) -> List[str]:
        """Extract key discussion points from transcript"""
        points = []
        
        # Look for discussion markers
        discussion_patterns = [
            r"(?:let's|let us) (?:talk about|discuss|explore) (.+?)[\.\!\?]",
            r"(?:the question is|what about|how about) (.+?)[\.\!\?]",
            r"(?:another|next) (?:point|topic|issue) (?:is|:) (.+?)[\.\!\?]",
            r"(?:we also|also) (?:need to|should) (?:consider|discuss) (.+?)[\.\!\?]"
        ]
        
        for pattern in discussion_patterns:
            matches = re.findall(pattern, transcript, re.IGNORECASE)
            for match in matches[:2]:
                point = match.strip()
                if len(point) > 10 and len(point) < 80:
                    points.append(point)
        
        return points[:3]
    
    def _extract_guest_info(self, enrichment: Optional[EnrichmentResult]) -> List[Dict[str, Any]]:
        """Extract guest information from enrichment data"""
        guests = []
        
        if not enrichment or not enrichment.proficiency_scores:
            return guests
        
        scores_data = enrichment.proficiency_scores
        if 'scored_people' in scores_data:
            for person in scores_data['scored_people'][:3]:  # Top 3 guests
                guest_info = {
                    'name': person.get('name', ''),
                    'title': person.get('job_title', ''),
                    'affiliation': person.get('affiliation', ''),
                    'badge': person.get('credibilityBadge', 'Guest'),
                    'score': person.get('proficiencyScore', 0)
                }
                
                if guest_info['name']:
                    guests.append(guest_info)
        
        return guests
    
    def _extract_main_topics(self, transcript: str, 
                           enrichment: Optional[EnrichmentResult]) -> List[str]:
        """Extract main topics from transcript and enrichment"""
        topics = []
        
        # From enrichment data
        if enrichment and enrichment.entities and 'topics' in enrichment.entities:
            for topic in enrichment.entities['topics'][:3]:
                if isinstance(topic, dict):
                    topic_name = topic.get('name', '')
                else:
                    topic_name = str(topic)
                
                if topic_name:
                    topics.append(topic_name)
        
        # From transcript keywords if no enrichment topics
        if not topics:
            topics = self._extract_transcript_keywords(transcript)[:3]
        
        return topics
    
    def _craft_journalistic_summary(self, metadata: EpisodeMetadata, 
                                  discussion_points: List[str],
                                  guests: List[Dict[str, Any]], 
                                  topics: List[str]) -> str:
        """Craft summary using journalistic structure"""
        summary_parts = []
        
        # Lead: What happened/what's the story
        if topics:
            lead = f"Exploring {', '.join(topics[:2])}"
            if len(topics) > 2:
                lead += f" and {topics[2]}"
        else:
            lead = f"In-depth discussion on {metadata.topic or 'current issues'}"
        
        summary_parts.append(lead)
        
        # Who: Key participants
        if guests:
            guest_names = []
            for guest in guests[:2]:  # Top 2 guests
                name = guest['name']
                title = guest['title']
                if title:
                    guest_names.append(f"{name}, {title}")
                else:
                    guest_names.append(name)
            
            if guest_names:
                who_part = f"featuring {' and '.join(guest_names)}"
                summary_parts.append(who_part)
        
        # What: Key discussion points
        if discussion_points:
            what_part = f"covering {discussion_points[0].lower()}"
            if len(discussion_points) > 1:
                what_part += f" and {discussion_points[1].lower()}"
            summary_parts.append(what_part)
        
        # Combine parts
        summary = ". ".join(summary_parts) + "."
        
        # Ensure proper length
        if len(summary) > self.max_summary_length:
            # Truncate at sentence boundary
            sentences = summary.split('. ')
            truncated = ""
            for sentence in sentences:
                if len(truncated + sentence + ". ") <= self.max_summary_length:
                    truncated += sentence + ". "
                else:
                    break
            summary = truncated.rstrip()
        
        return summary
    
    def _optimize_summary_seo(self, summary: str, topics: List[str]) -> str:
        """Optimize summary for SEO while maintaining readability"""
        if not topics:
            return summary
        
        # Ensure main topic appears in summary
        main_topic = topics[0].lower()
        summary_lower = summary.lower()
        
        if main_topic not in summary_lower:
            # Try to naturally incorporate the topic
            if summary.endswith('.'):
                summary = summary[:-1] + f", focusing on {main_topic}."
            else:
                summary += f" The discussion centers on {main_topic}."
        
        return summary
    
    def _create_fallback_summary(self, metadata: EpisodeMetadata) -> str:
        """Create fallback summary when generation fails"""
        show_name = metadata.show_name or "this episode"
        topic = metadata.topic or "current topics"
        
        return f"Join the conversation on {show_name} as experts discuss {topic} and share insights on the latest developments."
    
    def _extract_transcript_keywords(self, transcript: str) -> List[str]:
        """Extract keywords from transcript using simple NLP"""
        # Common stop words to exclude
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have',
            'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
            'may', 'might', 'can', 'this', 'that', 'these', 'those', 'i', 'you',
            'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them',
            'my', 'your', 'his', 'her', 'its', 'our', 'their', 'what', 'when',
            'where', 'why', 'how', 'who', 'which', 'so', 'if', 'then', 'than',
            'as', 'like', 'just', 'now', 'well', 'very', 'much', 'more', 'most',
            'some', 'any', 'all', 'no', 'not', 'only', 'also', 'even', 'still'
        }
        
        # Extract potential keywords
        words = re.findall(r'\b[a-zA-Z]{3,}\b', transcript.lower())
        
        # Count word frequency
        word_freq = {}
        for word in words:
            if word not in stop_words:
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # Get top keywords by frequency
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        
        # Filter for meaningful keywords
        keywords = []
        for word, freq in sorted_words[:20]:
            if freq >= 3 and len(word) >= 4:  # Minimum frequency and length
                keywords.append(word.title())
        
        return keywords[:8]
    
    def _clean_and_deduplicate_tags(self, tags: List[str]) -> List[str]:
        """Clean and deduplicate topic tags"""
        cleaned_tags = []
        seen_tags = set()
        
        for tag in tags:
            # Clean the tag
            clean_tag = re.sub(r'[^\w\s-]', '', tag.strip())
            clean_tag = re.sub(r'\s+', ' ', clean_tag)
            clean_tag = clean_tag.title()
            
            # Skip if empty or too short
            if len(clean_tag) < 3:
                continue
            
            # Check for duplicates (case-insensitive)
            tag_lower = clean_tag.lower()
            if tag_lower not in seen_tags:
                seen_tags.add(tag_lower)
                cleaned_tags.append(clean_tag)
        
        return cleaned_tags
    
    def _rank_tags_by_relevance(self, tags: List[str], transcript: str) -> List[str]:
        """Rank tags by relevance to transcript content"""
        tag_scores = []
        transcript_lower = transcript.lower()
        
        for tag in tags:
            score = 0
            tag_lower = tag.lower()
            
            # Count occurrences in transcript
            occurrences = transcript_lower.count(tag_lower)
            score += occurrences * 0.5
            
            # Boost score for tags appearing in first 500 characters (likely intro)
            if tag_lower in transcript_lower[:500]:
                score += 2
            
            # Boost score for multi-word tags (more specific)
            if len(tag.split()) > 1:
                score += 1
            
            # Boost score for capitalized terms (likely proper nouns)
            if any(word[0].isupper() for word in tag.split() if word):
                score += 0.5
            
            tag_scores.append((tag, score))
        
        # Sort by score and return tags
        tag_scores.sort(key=lambda x: x[1], reverse=True)
        return [tag for tag, _ in tag_scores]
    
    def _extract_fallback_tags(self, transcript: str) -> List[str]:
        """Extract fallback tags when main extraction fails"""
        # Simple keyword extraction as fallback
        keywords = self._extract_transcript_keywords(transcript)
        return keywords[:5]
    
    def _assess_readability(self, content: EditorialContent) -> float:
        """Assess content readability"""
        score = 0.8  # Base score
        
        # Check summary readability
        if content.summary:
            words = len(content.summary.split())
            sentences = len(re.split(r'[.!?]+', content.summary))
            
            if sentences > 0:
                avg_words_per_sentence = words / sentences
                
                # Penalize very long sentences
                if avg_words_per_sentence > 20:
                    score -= 0.2
                elif avg_words_per_sentence > 15:
                    score -= 0.1
                
                # Reward concise writing
                if 8 <= avg_words_per_sentence <= 12:
                    score += 0.1
        
        # Check takeaway readability
        if content.key_takeaway:
            if len(content.key_takeaway) > self.max_takeaway_length:
                score -= 0.1
        
        return max(0.0, min(1.0, score))
    
    def _assess_engagement(self, content: EditorialContent) -> float:
        """Assess content engagement potential"""
        score = 0.7  # Base score
        
        # Check for engaging elements in summary
        if content.summary:
            summary_lower = content.summary.lower()
            
            # Reward active voice indicators
            active_indicators = ['explores', 'reveals', 'discusses', 'examines', 'features']
            if any(indicator in summary_lower for indicator in active_indicators):
                score += 0.1
            
            # Reward specific details
            if any(char.isdigit() for char in content.summary):
                score += 0.05
            
            # Penalize passive voice
            passive_indicators = ['is discussed', 'are examined', 'was revealed']
            if any(indicator in summary_lower for indicator in passive_indicators):
                score -= 0.1
        
        # Check takeaway engagement
        if content.key_takeaway:
            takeaway_lower = content.key_takeaway.lower()
            
            # Reward compelling hooks
            hooks = ['why', 'how', 'what', 'the truth', 'reality', 'secret']
            if any(hook in takeaway_lower for hook in hooks):
                score += 0.1
        
        # Reward good topic diversity
        if content.topic_tags and len(content.topic_tags) >= 3:
            score += 0.1
        
        return max(0.0, min(1.0, score))
    
    def _assess_seo_optimization(self, content: EditorialContent) -> float:
        """Assess SEO optimization"""
        score = 0.6  # Base score
        
        # Check summary length (target ~50 words)
        if content.summary:
            word_count = len(content.summary.split())
            if 40 <= word_count <= 60:
                score += 0.2
            elif 30 <= word_count <= 70:
                score += 0.1
        
        # Check topic tag quality
        if content.topic_tags:
            if len(content.topic_tags) >= 3:
                score += 0.1
            if len(content.topic_tags) >= 5:
                score += 0.1
        
        return max(0.0, min(1.0, score))
    
    def _validate_against_source(self, content: EditorialContent, transcript: str) -> float:
        """Validate content against source material for fact-checking"""
        score = 0.9  # Base high score (assume accurate unless issues found)
        
        # Check if summary claims are supported by transcript
        if content.summary:
            # Look for specific claims that might not be in transcript
            summary_words = set(content.summary.lower().split())
            transcript_words = set(transcript.lower().split())
            
            # Check for unsupported specific terms
            specific_terms = [word for word in summary_words 
                            if len(word) > 6 and word.isalpha()]
            
            unsupported_count = 0
            for term in specific_terms[:10]:  # Check up to 10 terms
                if term not in transcript_words:
                    unsupported_count += 1
            
            # Penalize for potentially unsupported claims
            if unsupported_count > 3:
                score -= 0.2
            elif unsupported_count > 1:
                score -= 0.1
        
        return max(0.0, min(1.0, score))


class EditorialQualityValidator:
    """Validator for editorial content quality and standards"""
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.logger = get_logger('pipeline.editorial_validator')
    
    def validate_editorial_workflow(self, editorial_content: EditorialContent,
                                  episode: EpisodeObject) -> Dict[str, Any]:
        """
        Validate editorial content for review workflow support
        
        Args:
            editorial_content: Generated editorial content
            episode: Source episode object
            
        Returns:
            Dict[str, Any]: Validation results with workflow recommendations
        """
        try:
            validation_result = {
                'ready_for_review': True,
                'review_priority': 'standard',
                'required_checks': [],
                'recommendations': [],
                'quality_flags': []
            }
            
            # Check content completeness
            if not editorial_content.summary:
                validation_result['ready_for_review'] = False
                validation_result['required_checks'].append('Generate episode summary')
            
            if not editorial_content.key_takeaway:
                validation_result['ready_for_review'] = False
                validation_result['required_checks'].append('Generate key takeaway')
            
            # Check content quality
            if editorial_content.summary and len(editorial_content.summary) < 50:
                validation_result['quality_flags'].append('Summary may be too brief')
                validation_result['recommendations'].append('Expand summary with more details')
            
            if editorial_content.topic_tags and len(editorial_content.topic_tags) < 3:
                validation_result['quality_flags'].append('Limited topic tags')
                validation_result['recommendations'].append('Add more relevant topic tags')
            
            # Determine review priority based on content
            if episode.enrichment and episode.enrichment.proficiency_scores:
                scores_data = episode.enrichment.proficiency_scores
                if 'scored_people' in scores_data:
                    high_profile_guests = [
                        p for p in scores_data['scored_people']
                        if p.get('credibilityBadge') == 'Verified Expert'
                    ]
                    if high_profile_guests:
                        validation_result['review_priority'] = 'high'
                        validation_result['recommendations'].append(
                            'High-profile guests detected - prioritize for editorial review'
                        )
            
            # Check for sensitive topics that need extra review
            sensitive_keywords = [
                'government', 'policy', 'regulation', 'controversy', 'scandal',
                'investigation', 'lawsuit', 'criminal', 'fraud', 'corruption'
            ]
            
            content_text = f"{editorial_content.summary or ''} {editorial_content.key_takeaway or ''}"
            if any(keyword in content_text.lower() for keyword in sensitive_keywords):
                validation_result['review_priority'] = 'high'
                validation_result['required_checks'].append('Legal and compliance review')
            
            return validation_result
        
        except Exception as e:
            self.logger.error(
                "Editorial workflow validation failed",
                episode_id=episode.episode_id,
                exception=e
            )
            return {
                'ready_for_review': False,
                'review_priority': 'high',
                'required_checks': ['Manual validation required'],
                'recommendations': ['System validation failed - manual review needed'],
                'quality_flags': ['Validation error']
            }


class EditorialSEOOptimizer:
    """SEO optimization for editorial content"""
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.logger = get_logger('pipeline.seo_optimizer')
        
        # SEO targets
        self.target_title_length = 60
        self.target_description_length = 160
        self.target_keyword_density = 0.02
        self.max_keyword_density = 0.05
    
    def optimize_for_seo(self, editorial_content: EditorialContent,
                        episode: EpisodeObject) -> Dict[str, Any]:
        """
        Optimize editorial content for SEO
        
        Args:
            editorial_content: Editorial content to optimize
            episode: Source episode object
            
        Returns:
            Dict[str, Any]: SEO optimization results and recommendations
        """
        try:
            optimization_result = {
                'seo_score': 0.0,
                'optimizations_applied': [],
                'recommendations': [],
                'meta_tags': {},
                'structured_data': {}
            }
            
            # Optimize title (key takeaway)
            if editorial_content.key_takeaway:
                title_optimization = self._optimize_title(
                    editorial_content.key_takeaway,
                    editorial_content.topic_tags
                )
                optimization_result['meta_tags']['title'] = title_optimization['optimized_title']
                optimization_result['optimizations_applied'].extend(title_optimization['changes'])
            
            # Optimize description (summary)
            if editorial_content.summary:
                desc_optimization = self._optimize_description(
                    editorial_content.summary,
                    editorial_content.topic_tags
                )
                optimization_result['meta_tags']['description'] = desc_optimization['optimized_description']
                optimization_result['optimizations_applied'].extend(desc_optimization['changes'])
            
            # Generate keywords meta tag
            if editorial_content.topic_tags:
                keywords = self._generate_seo_keywords(editorial_content.topic_tags, episode)
                optimization_result['meta_tags']['keywords'] = ', '.join(keywords)
            
            # Generate structured data
            structured_data = self._generate_structured_data(editorial_content, episode)
            optimization_result['structured_data'] = structured_data
            
            # Calculate SEO score
            seo_score = self._calculate_seo_score(optimization_result, editorial_content)
            optimization_result['seo_score'] = seo_score
            
            # Generate recommendations
            recommendations = self._generate_seo_recommendations(optimization_result, editorial_content)
            optimization_result['recommendations'] = recommendations
            
            return optimization_result
        
        except Exception as e:
            self.logger.error(
                "SEO optimization failed",
                episode_id=episode.episode_id,
                exception=e
            )
            return {
                'seo_score': 0.0,
                'optimizations_applied': [],
                'recommendations': ['SEO optimization failed - manual review needed'],
                'meta_tags': {},
                'structured_data': {}
            }
    
    def _optimize_title(self, title: str, topics: List[str]) -> Dict[str, Any]:
        """Optimize title for SEO"""
        optimized_title = title
        changes = []
        
        # Ensure optimal length
        if len(title) > self.target_title_length:
            # Truncate at word boundary
            truncated = title[:self.target_title_length-3]
            last_space = truncated.rfind(' ')
            if last_space > self.target_title_length * 0.8:
                optimized_title = truncated[:last_space] + "..."
            else:
                optimized_title = truncated + "..."
            changes.append('Truncated title for optimal length')
        
        # Add primary keyword if not present
        if topics and topics[0].lower() not in optimized_title.lower():
            if len(optimized_title) + len(topics[0]) + 3 <= self.target_title_length:
                optimized_title = f"{topics[0]}: {optimized_title}"
                changes.append('Added primary keyword to title')
        
        return {
            'optimized_title': optimized_title,
            'changes': changes
        }
    
    def _optimize_description(self, description: str, topics: List[str]) -> Dict[str, Any]:
        """Optimize description for SEO"""
        optimized_description = description
        changes = []
        
        # Ensure optimal length
        if len(description) > self.target_description_length:
            # Truncate at sentence boundary
            sentences = description.split('. ')
            truncated = ""
            for sentence in sentences:
                if len(truncated + sentence + ". ") <= self.target_description_length:
                    truncated += sentence + ". "
                else:
                    break
            optimized_description = truncated.rstrip()
            changes.append('Truncated description for optimal length')
        elif len(description) < self.target_description_length * 0.7:
            # Add call-to-action if too short
            if topics:
                cta = f" Learn more about {topics[0].lower()}."
                if len(description + cta) <= self.target_description_length:
                    optimized_description = description + cta
                    changes.append('Added call-to-action to description')
        
        return {
            'optimized_description': optimized_description,
            'changes': changes
        }
    
    def _generate_seo_keywords(self, topic_tags: List[str], episode: EpisodeObject) -> List[str]:
        """Generate SEO keywords from topic tags and episode data"""
        keywords = []
        
        # Add topic tags
        keywords.extend(topic_tags[:5])
        
        # Add show name
        show_name = episode.get_show_name()
        if show_name and show_name != 'Unknown':
            keywords.append(show_name)
        
        # Add guest names (if high-profile)
        if episode.enrichment and episode.enrichment.proficiency_scores:
            scores_data = episode.enrichment.proficiency_scores
            if 'scored_people' in scores_data:
                for person in scores_data['scored_people'][:2]:
                    if person.get('credibilityBadge') in ['Verified Expert', 'Identified Contributor']:
                        name = person.get('name', '')
                        if name:
                            keywords.append(name)
        
        # Remove duplicates and limit
        seen = set()
        unique_keywords = []
        for keyword in keywords:
            if keyword.lower() not in seen:
                seen.add(keyword.lower())
                unique_keywords.append(keyword)
        
        return unique_keywords[:10]
    
    def _generate_structured_data(self, editorial_content: EditorialContent,
                                episode: EpisodeObject) -> Dict[str, Any]:
        """Generate JSON-LD structured data"""
        structured_data = {
            "@context": "https://schema.org",
            "@type": "TVEpisode",
            "name": editorial_content.key_takeaway or episode.metadata.title,
            "description": editorial_content.summary,
            "partOfSeries": {
                "@type": "TVSeries",
                "name": episode.get_show_name()
            }
        }
        
        # Add episode details
        if episode.metadata.season:
            structured_data["seasonNumber"] = episode.metadata.season
        if episode.metadata.episode:
            structured_data["episodeNumber"] = episode.metadata.episode
        if episode.metadata.date:
            structured_data["datePublished"] = episode.metadata.date
        
        # Add duration if available
        if episode.media.duration_seconds:
            structured_data["duration"] = f"PT{int(episode.media.duration_seconds)}S"
        
        # Add keywords
        if editorial_content.topic_tags:
            structured_data["keywords"] = editorial_content.topic_tags
        
        # Add guests as cast members
        if episode.enrichment and episode.enrichment.proficiency_scores:
            scores_data = episode.enrichment.proficiency_scores
            if 'scored_people' in scores_data:
                cast = []
                for person in scores_data['scored_people']:
                    cast_member = {
                        "@type": "Person",
                        "name": person.get('name', '')
                    }
                    if person.get('job_title'):
                        cast_member["jobTitle"] = person.get('job_title')
                    if person.get('affiliation'):
                        cast_member["worksFor"] = {
                            "@type": "Organization",
                            "name": person.get('affiliation')
                        }
                    cast.append(cast_member)
                
                if cast:
                    structured_data["actor"] = cast
        
        return structured_data
    
    def _calculate_seo_score(self, optimization_result: Dict[str, Any],
                           editorial_content: EditorialContent) -> float:
        """Calculate overall SEO score"""
        score = 0.0
        
        # Title optimization (25%)
        title = optimization_result['meta_tags'].get('title', '')
        if title:
            if 30 <= len(title) <= 60:
                score += 0.25
            elif 20 <= len(title) <= 70:
                score += 0.15
        
        # Description optimization (25%)
        description = optimization_result['meta_tags'].get('description', '')
        if description:
            if 120 <= len(description) <= 160:
                score += 0.25
            elif 100 <= len(description) <= 180:
                score += 0.15
        
        # Keywords (20%)
        keywords = optimization_result['meta_tags'].get('keywords', '')
        if keywords:
            keyword_count = len(keywords.split(', '))
            if 5 <= keyword_count <= 10:
                score += 0.20
            elif 3 <= keyword_count <= 12:
                score += 0.10
        
        # Structured data (20%)
        if optimization_result['structured_data']:
            score += 0.20
        
        # Content quality (10%)
        if editorial_content.topic_tags and len(editorial_content.topic_tags) >= 3:
            score += 0.10
        
        return min(1.0, score)
    
    def _generate_seo_recommendations(self, optimization_result: Dict[str, Any],
                                    editorial_content: EditorialContent) -> List[str]:
        """Generate SEO improvement recommendations"""
        recommendations = []
        
        # Title recommendations
        title = optimization_result['meta_tags'].get('title', '')
        if not title:
            recommendations.append('Add SEO-optimized title')
        elif len(title) < 30:
            recommendations.append('Expand title for better SEO (target 30-60 characters)')
        elif len(title) > 70:
            recommendations.append('Shorten title for better SEO (target 30-60 characters)')
        
        # Description recommendations
        description = optimization_result['meta_tags'].get('description', '')
        if not description:
            recommendations.append('Add meta description')
        elif len(description) < 120:
            recommendations.append('Expand description (target 120-160 characters)')
        elif len(description) > 180:
            recommendations.append('Shorten description (target 120-160 characters)')
        
        # Keywords recommendations
        keywords = optimization_result['meta_tags'].get('keywords', '')
        if not keywords:
            recommendations.append('Add relevant keywords')
        else:
            keyword_count = len(keywords.split(', '))
            if keyword_count < 3:
                recommendations.append('Add more relevant keywords (target 5-10)')
            elif keyword_count > 12:
                recommendations.append('Reduce number of keywords (target 5-10)')
        
        # Content recommendations
        if not editorial_content.topic_tags or len(editorial_content.topic_tags) < 3:
            recommendations.append('Add more topic tags for better categorization')
        
        return recommendations


class EditorialFactChecker:
    """Fact-checking validation for editorial content"""
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.logger = get_logger('pipeline.fact_checker')
    
    def validate_against_source_material(self, editorial_content: EditorialContent,
                                       episode: EpisodeObject) -> Dict[str, Any]:
        """
        Validate editorial content against source transcript for accuracy
        
        Args:
            editorial_content: Generated editorial content
            episode: Source episode with transcript
            
        Returns:
            Dict[str, Any]: Fact-checking validation results
        """
        try:
            validation_result = {
                'accuracy_score': 0.0,
                'potential_issues': [],
                'verified_claims': [],
                'recommendations': [],
                'confidence_level': 'high'
            }
            
            if not episode.transcription or not episode.transcription.text:
                validation_result['confidence_level'] = 'low'
                validation_result['recommendations'].append('No transcript available for fact-checking')
                return validation_result
            
            transcript = episode.transcription.text.lower()
            
            # Validate summary claims
            if editorial_content.summary:
                summary_validation = self._validate_summary_claims(
                    editorial_content.summary, transcript
                )
                validation_result['potential_issues'].extend(summary_validation['issues'])
                validation_result['verified_claims'].extend(summary_validation['verified'])
            
            # Validate key takeaway
            if editorial_content.key_takeaway:
                takeaway_validation = self._validate_takeaway_claims(
                    editorial_content.key_takeaway, transcript
                )
                validation_result['potential_issues'].extend(takeaway_validation['issues'])
                validation_result['verified_claims'].extend(takeaway_validation['verified'])
            
            # Validate topic tags
            if editorial_content.topic_tags:
                topic_validation = self._validate_topic_relevance(
                    editorial_content.topic_tags, transcript
                )
                validation_result['potential_issues'].extend(topic_validation['issues'])
                validation_result['verified_claims'].extend(topic_validation['verified'])
            
            # Calculate accuracy score
            total_claims = len(validation_result['verified_claims']) + len(validation_result['potential_issues'])
            if total_claims > 0:
                accuracy_score = len(validation_result['verified_claims']) / total_claims
            else:
                accuracy_score = 0.8  # Default if no specific claims to validate
            
            validation_result['accuracy_score'] = accuracy_score
            
            # Set confidence level
            if accuracy_score >= 0.9:
                validation_result['confidence_level'] = 'high'
            elif accuracy_score >= 0.7:
                validation_result['confidence_level'] = 'medium'
            else:
                validation_result['confidence_level'] = 'low'
                validation_result['recommendations'].append('Manual fact-checking recommended')
            
            # Generate recommendations
            if validation_result['potential_issues']:
                validation_result['recommendations'].append(
                    f"Review {len(validation_result['potential_issues'])} potential accuracy issues"
                )
            
            return validation_result
        
        except Exception as e:
            self.logger.error(
                "Fact-checking validation failed",
                episode_id=episode.episode_id,
                exception=e
            )
            return {
                'accuracy_score': 0.0,
                'potential_issues': ['Fact-checking validation failed'],
                'verified_claims': [],
                'recommendations': ['Manual fact-checking required'],
                'confidence_level': 'low'
            }
    
    def _validate_summary_claims(self, summary: str, transcript: str) -> Dict[str, Any]:
        """Validate claims made in the summary"""
        issues = []
        verified = []
        
        # Extract potential factual claims from summary
        claims = self._extract_factual_claims(summary)
        
        for claim in claims:
            if self._is_claim_supported(claim, transcript):
                verified.append(f"Summary claim: {claim}")
            else:
                issues.append(f"Unsupported summary claim: {claim}")
        
        return {'issues': issues, 'verified': verified}
    
    def _validate_takeaway_claims(self, takeaway: str, transcript: str) -> Dict[str, Any]:
        """Validate claims made in the key takeaway"""
        issues = []
        verified = []
        
        # Check if takeaway is supported by transcript content
        takeaway_words = set(takeaway.lower().split())
        transcript_words = set(transcript.split())
        
        # Check for specific claims
        specific_terms = [word for word in takeaway_words 
                        if len(word) > 5 and word.isalpha()]
        
        supported_terms = 0
        for term in specific_terms:
            if term in transcript_words:
                supported_terms += 1
            else:
                # Check for partial matches or synonyms
                if any(term in transcript_word for transcript_word in transcript_words):
                    supported_terms += 1
        
        if specific_terms:
            support_ratio = supported_terms / len(specific_terms)
            if support_ratio >= 0.7:
                verified.append("Key takeaway supported by transcript")
            else:
                issues.append("Key takeaway may not be fully supported by transcript")
        
        return {'issues': issues, 'verified': verified}
    
    def _validate_topic_relevance(self, topic_tags: List[str], transcript: str) -> Dict[str, Any]:
        """Validate relevance of topic tags to transcript content"""
        issues = []
        verified = []
        
        for topic in topic_tags:
            topic_lower = topic.lower()
            
            # Check if topic appears in transcript
            if topic_lower in transcript:
                verified.append(f"Topic '{topic}' found in transcript")
            else:
                # Check for partial matches
                topic_words = topic_lower.split()
                matches = sum(1 for word in topic_words if word in transcript)
                
                if matches >= len(topic_words) * 0.5:
                    verified.append(f"Topic '{topic}' partially supported")
                else:
                    issues.append(f"Topic '{topic}' may not be relevant to content")
        
        return {'issues': issues, 'verified': verified}
    
    def _extract_factual_claims(self, text: str) -> List[str]:
        """Extract potential factual claims from text"""
        claims = []
        
        # Look for specific claim patterns
        claim_patterns = [
            r'(\d+(?:\.\d+)?%?\s+(?:of|percent|increase|decrease|growth))',
            r'(according to [^,\.]+)',
            r'(research (?:shows|indicates|suggests) [^,\.]+)',
            r'(studies (?:show|indicate|suggest) [^,\.]+)',
            r'(data (?:shows|indicates|suggests) [^,\.]+)'
        ]
        
        for pattern in claim_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            claims.extend(matches)
        
        return claims[:5]  # Limit to 5 claims
    
    def _is_claim_supported(self, claim: str, transcript: str) -> bool:
        """Check if a claim is supported by the transcript"""
        claim_lower = claim.lower()
        transcript_lower = transcript.lower()
        
        # Direct match
        if claim_lower in transcript_lower:
            return True
        
        # Check for key terms from the claim
        claim_words = [word for word in claim_lower.split() if len(word) > 3]
        if not claim_words:
            return False
        
        matches = sum(1 for word in claim_words if word in transcript_lower)
        return matches >= len(claim_words) * 0.7