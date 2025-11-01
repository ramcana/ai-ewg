"""
Metadata Generation Engine

Generates titles, captions, and hashtags using local LLM with explicit fallback
to keyword extraction when LLM is unavailable. Ensures language consistency
with episode transcript and provides engaging social media content.
"""

import re
import json
import subprocess
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from collections import Counter

try:
    import spacy
except ImportError:
    spacy = None

from .topic_segmentation import TopicSegment
from .logging import get_logger
from .exceptions import LLMError, ClipGenerationError
from .clip_resource_manager import with_clip_resource_management

logger = get_logger('clip_generation.metadata_generation')


@dataclass
class GeneratedMetadata:
    """Container for generated clip metadata"""
    title: str
    caption: str
    hashtags: List[str]
    keywords: List[str]
    generation_method: str  # 'llm' or 'fallback'
    language: str = "en"


class MetadataGenerationEngine:
    """
    Generates titles, captions, and hashtags using local LLM with explicit fallback
    
    Uses local LLM for engaging content generation with heuristic-based fallback
    when LLM is unavailable. Ensures language consistency and social media optimization.
    """
    
    def __init__(self, 
                 llm_enabled: bool = True,
                 llm_model: str = "llama3",
                 llm_timeout: int = 30,
                 max_title_length: int = 60,
                 max_hashtags: int = 6):
        """
        Initialize metadata generation engine
        
        Args:
            llm_enabled: Whether to use LLM for generation
            llm_model: Local LLM model name (Ollama/Qwen/Llama3)
            llm_timeout: Timeout for LLM requests in seconds
            max_title_length: Maximum title length in characters
            max_hashtags: Maximum number of hashtags to generate
        """
        self.llm_enabled = llm_enabled
        self.llm_model = llm_model
        self.llm_timeout = llm_timeout
        self.max_title_length = max_title_length
        self.max_hashtags = max_hashtags
        
        # Initialize NLP components for fallback
        self.nlp = None
        self._initialize_nlp()
        
        # Compile patterns for keyword extraction
        self._compile_patterns()
        
        logger.info("MetadataGenerationEngine initialized",
                   llm_enabled=llm_enabled,
                   llm_model=llm_model,
                   max_title_length=max_title_length,
                   max_hashtags=max_hashtags,
                   nlp_available=self.nlp is not None)
    
    def _initialize_nlp(self) -> None:
        """Initialize spaCy NLP pipeline for fallback keyword extraction"""
        if spacy is None:
            logger.warning("spaCy not available, fallback will be limited")
            return
        
        try:
            # Try to load English model
            self.nlp = spacy.load("en_core_web_sm")
            logger.info("spaCy English model loaded successfully")
        except OSError:
            try:
                # Fallback to medium model
                self.nlp = spacy.load("en_core_web_md")
                logger.info("spaCy medium model loaded as fallback")
            except OSError:
                logger.warning("No spaCy English model found. Install with: python -m spacy download en_core_web_sm")
                self.nlp = None
    
    def _compile_patterns(self) -> None:
        """Compile regex patterns for keyword extraction"""
        # Patterns for identifying key phrases
        self.key_phrase_patterns = {
            'action_words': re.compile(r'\b(learn|discover|find|get|make|create|build|start|stop|avoid|prevent|improve|increase|decrease)\b', re.IGNORECASE),
            'question_words': re.compile(r'\b(how|what|why|when|where|who|which)\b', re.IGNORECASE),
            'superlatives': re.compile(r'\b(best|worst|top|bottom|first|last|biggest|smallest|most|least)\b', re.IGNORECASE),
            'numbers': re.compile(r'\b(\d+)\b'),
            'time_references': re.compile(r'\b(today|now|future|past|years?|months?|days?|minutes?|seconds?)\b', re.IGNORECASE)
        }
        
        # Common stop words to filter out
        self.stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
            'will', 'would', 'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these', 'those',
            'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them'
        }
    
    def generate_title(self, segment: TopicSegment) -> str:
        """
        Generate hook title with character limits
        
        Creates engaging 1-line hook titles with maximum 60 characters using
        local LLM or keyword-based fallback.
        
        Args:
            segment: Topic segment to generate title for
            
        Returns:
            Generated title string (max 60 characters)
        """
        try:
            logger.debug("Generating title for segment",
                        segment_start_ms=segment.start_ms,
                        segment_duration_s=segment.duration_ms / 1000)
            
            if self.llm_enabled:
                # Try LLM generation first
                llm_title = self._generate_title_with_llm(segment)
                if llm_title:
                    title = self._truncate_title(llm_title)
                    logger.debug("Title generated with LLM", title=title)
                    return title
            
            # Fallback to keyword-based generation
            title = self._generate_title_fallback(segment)
            logger.debug("Title generated with fallback", title=title)
            return title
            
        except Exception as e:
            logger.error("Title generation failed", error=str(e))
            # Ultimate fallback
            return self._create_basic_title(segment)
    
    def _generate_title_with_llm(self, segment: TopicSegment) -> Optional[str]:
        """
        Generate title using local LLM
        
        Args:
            segment: Topic segment
            
        Returns:
            Generated title or None if failed
        """
        try:
            prompt = self._create_title_prompt(segment)
            response = self._call_ollama_api(prompt)
            
            if response:
                # Extract title from response
                title = self._parse_title_response(response)
                if title and len(title.strip()) > 0:
                    return title.strip()
            
            return None
            
        except Exception as e:
            logger.warning("LLM title generation failed", error=str(e))
            return None
    
    def _create_title_prompt(self, segment: TopicSegment) -> str:
        """
        Create prompt for LLM title generation
        
        Args:
            segment: Topic segment
            
        Returns:
            Formatted prompt string
        """
        text = segment.text[:300]  # Limit context for focus
        duration_s = segment.duration_ms / 1000
        
        prompt = f"""Create an engaging social media title for this video clip. The title should:
- Be maximum 60 characters
- Create curiosity or urgency
- Be suitable for platforms like TikTok, Instagram, YouTube Shorts
- Capture the main hook or key point
- Use active, engaging language

Video clip ({duration_s:.1f} seconds):
"{text}"

Generate only the title, no explanation:"""
        
        return prompt
    
    def _parse_title_response(self, response: str) -> Optional[str]:
        """
        Parse title from LLM response
        
        Args:
            response: LLM response text
            
        Returns:
            Extracted title or None
        """
        # Clean up response
        title = response.strip()
        
        # Remove quotes if present
        if title.startswith('"') and title.endswith('"'):
            title = title[1:-1]
        elif title.startswith("'") and title.endswith("'"):
            title = title[1:-1]
        
        # Remove common prefixes
        prefixes_to_remove = [
            "Title:", "title:", "TITLE:",
            "Here's the title:", "The title is:",
            "Generated title:", "Social media title:"
        ]
        
        for prefix in prefixes_to_remove:
            if title.startswith(prefix):
                title = title[len(prefix):].strip()
        
        # Basic validation
        if len(title) > 0 and len(title) <= 100:  # Allow some buffer for truncation
            return title
        
        return None
    
    def _generate_title_fallback(self, segment: TopicSegment) -> str:
        """
        Generate title using keyword-based fallback
        
        Args:
            segment: Topic segment
            
        Returns:
            Generated title
        """
        text = segment.text
        
        # Extract key elements
        keywords = self.extract_keywords(segment)
        
        # Look for question patterns
        if '?' in text[:100]:
            # Use question as title
            first_sentence = text.split('.')[0].split('!')[0].split('?')[0] + '?'
            if len(first_sentence) <= self.max_title_length:
                return first_sentence
        
        # Look for imperative statements
        first_sentence = text.split('.')[0].split('!')[0].split('?')[0]
        if any(word in first_sentence.lower() for word in ['you need', 'you should', 'you must', 'learn', 'discover']):
            return self._truncate_title(first_sentence)
        
        # Look for claims or statistics
        if any(pattern.search(text[:100]) for pattern in self.key_phrase_patterns.values()):
            return self._truncate_title(first_sentence)
        
        # Use top keywords to create title
        if keywords:
            if len(keywords) >= 2:
                title = f"The Truth About {keywords[0]} and {keywords[1]}"
            else:
                title = f"What You Need to Know About {keywords[0]}"
            
            return self._truncate_title(title)
        
        # Ultimate fallback
        return self._create_basic_title(segment)
    
    def _create_basic_title(self, segment: TopicSegment) -> str:
        """
        Create basic title as ultimate fallback
        
        Args:
            segment: Topic segment
            
        Returns:
            Basic title
        """
        # Use first few words
        words = segment.text.split()[:8]
        title = ' '.join(words)
        
        if len(title) > self.max_title_length:
            title = title[:self.max_title_length - 3] + "..."
        
        return title if title else "Interesting Clip"
    
    def _truncate_title(self, title: str) -> str:
        """
        Truncate title to maximum length
        
        Args:
            title: Original title
            
        Returns:
            Truncated title
        """
        if len(title) <= self.max_title_length:
            return title
        
        # Try to truncate at word boundary
        truncated = title[:self.max_title_length - 3]
        last_space = truncated.rfind(' ')
        
        if last_space > self.max_title_length // 2:
            return truncated[:last_space] + "..."
        else:
            return truncated + "..."
    
    def generate_caption(self, segment: TopicSegment) -> str:
        """
        Create engaging caption with hashtags
        
        Generates 1-2 sentence captions with context for social media platforms.
        
        Args:
            segment: Topic segment to generate caption for
            
        Returns:
            Generated caption string
        """
        try:
            logger.debug("Generating caption for segment",
                        segment_start_ms=segment.start_ms)
            
            if self.llm_enabled:
                # Try LLM generation first
                llm_caption = self._generate_caption_with_llm(segment)
                if llm_caption:
                    logger.debug("Caption generated with LLM")
                    return llm_caption
            
            # Fallback to keyword-based generation
            caption = self._generate_caption_fallback(segment)
            logger.debug("Caption generated with fallback")
            return caption
            
        except Exception as e:
            logger.error("Caption generation failed", error=str(e))
            # Ultimate fallback
            return self._create_basic_caption(segment)
    
    def _generate_caption_with_llm(self, segment: TopicSegment) -> Optional[str]:
        """
        Generate caption using local LLM
        
        Args:
            segment: Topic segment
            
        Returns:
            Generated caption or None if failed
        """
        try:
            prompt = self._create_caption_prompt(segment)
            response = self._call_ollama_api(prompt)
            
            if response:
                caption = self._parse_caption_response(response)
                if caption and len(caption.strip()) > 0:
                    return caption.strip()
            
            return None
            
        except Exception as e:
            logger.warning("LLM caption generation failed", error=str(e))
            return None
    
    def _create_caption_prompt(self, segment: TopicSegment) -> str:
        """
        Create prompt for LLM caption generation
        
        Args:
            segment: Topic segment
            
        Returns:
            Formatted prompt string
        """
        text = segment.text[:400]  # More context for captions
        duration_s = segment.duration_ms / 1000
        
        prompt = f"""Create an engaging social media caption for this video clip. The caption should:
- Be 1-2 sentences maximum
- Provide context and hook viewers
- Be conversational and engaging
- Encourage engagement (comments, shares)
- Be suitable for TikTok, Instagram, YouTube Shorts

Video clip ({duration_s:.1f} seconds):
"{text}"

Generate only the caption, no hashtags or explanation:"""
        
        return prompt
    
    def _parse_caption_response(self, response: str) -> Optional[str]:
        """
        Parse caption from LLM response
        
        Args:
            response: LLM response text
            
        Returns:
            Extracted caption or None
        """
        # Clean up response
        caption = response.strip()
        
        # Remove quotes if present
        if caption.startswith('"') and caption.endswith('"'):
            caption = caption[1:-1]
        elif caption.startswith("'") and caption.endswith("'"):
            caption = caption[1:-1]
        
        # Remove common prefixes
        prefixes_to_remove = [
            "Caption:", "caption:", "CAPTION:",
            "Here's the caption:", "The caption is:",
            "Generated caption:", "Social media caption:"
        ]
        
        for prefix in prefixes_to_remove:
            if caption.startswith(prefix):
                caption = caption[len(prefix):].strip()
        
        # Remove hashtags if included (we generate them separately)
        caption = re.sub(r'#\w+', '', caption).strip()
        
        # Basic validation - should be 1-2 sentences
        sentence_count = len([s for s in caption.split('.') if s.strip()])
        if sentence_count <= 3 and len(caption) > 10:
            return caption
        
        return None
    
    def _generate_caption_fallback(self, segment: TopicSegment) -> str:
        """
        Generate caption using keyword-based fallback
        
        Args:
            segment: Topic segment
            
        Returns:
            Generated caption
        """
        text = segment.text
        keywords = self.extract_keywords(segment)
        
        # Get first 1-2 sentences
        sentences = [s.strip() for s in text.split('.') if s.strip()]
        
        if len(sentences) >= 2:
            caption = f"{sentences[0]}. {sentences[1]}."
        elif len(sentences) == 1:
            caption = f"{sentences[0]}."
        else:
            caption = text[:150] + "..." if len(text) > 150 else text
        
        # Add engaging element if keywords available
        if keywords:
            if '?' not in caption:
                caption += f" What do you think about {keywords[0].lower()}?"
        
        return caption
    
    def _create_basic_caption(self, segment: TopicSegment) -> str:
        """
        Create basic caption as ultimate fallback
        
        Args:
            segment: Topic segment
            
        Returns:
            Basic caption
        """
        # Use first sentence or first 100 characters
        text = segment.text
        first_sentence = text.split('.')[0].strip()
        
        if len(first_sentence) > 100:
            caption = text[:100] + "..."
        else:
            caption = first_sentence + "."
        
        return caption
    
    def generate_hashtags(self, segment: TopicSegment, keywords: Optional[List[str]] = None) -> List[str]:
        """
        Create hashtag packs limited to 6 relevant tags
        
        Generates relevant hashtags based on segment content and keywords.
        
        Args:
            segment: Topic segment
            keywords: Pre-extracted keywords (optional)
            
        Returns:
            List of hashtags (max 6)
        """
        try:
            logger.debug("Generating hashtags for segment",
                        segment_start_ms=segment.start_ms)
            
            if keywords is None:
                keywords = self.extract_keywords(segment)
            
            hashtags = []
            
            # Convert keywords to hashtags
            for keyword in keywords[:3]:  # Use top 3 keywords
                hashtag = self._keyword_to_hashtag(keyword)
                if hashtag and hashtag not in hashtags:
                    hashtags.append(hashtag)
            
            # Add topic-based hashtags
            topic_hashtags = self._generate_topic_hashtags(segment)
            for hashtag in topic_hashtags:
                if hashtag not in hashtags and len(hashtags) < self.max_hashtags:
                    hashtags.append(hashtag)
            
            # Add platform-specific hashtags
            platform_hashtags = self._get_platform_hashtags()
            for hashtag in platform_hashtags:
                if hashtag not in hashtags and len(hashtags) < self.max_hashtags:
                    hashtags.append(hashtag)
            
            logger.debug("Hashtags generated", hashtags=hashtags)
            return hashtags[:self.max_hashtags]
            
        except Exception as e:
            logger.error("Hashtag generation failed", error=str(e))
            return ["#viral", "#trending", "#fyp"]
    
    def _keyword_to_hashtag(self, keyword: str) -> Optional[str]:
        """
        Convert keyword to valid hashtag
        
        Args:
            keyword: Source keyword
            
        Returns:
            Hashtag string or None if invalid
        """
        # Clean keyword
        clean_keyword = re.sub(r'[^a-zA-Z0-9]', '', keyword.lower())
        
        # Validate hashtag
        if len(clean_keyword) >= 3 and clean_keyword.isalnum():
            return f"#{clean_keyword}"
        
        return None
    
    def _generate_topic_hashtags(self, segment: TopicSegment) -> List[str]:
        """
        Generate topic-relevant hashtags
        
        Args:
            segment: Topic segment
            
        Returns:
            List of topic hashtags
        """
        text = segment.text.lower()
        topic_hashtags = []
        
        # Topic categories with associated hashtags
        topic_categories = {
            'business': ['#business', '#entrepreneur', '#success', '#money'],
            'technology': ['#tech', '#innovation', '#ai', '#future'],
            'health': ['#health', '#wellness', '#fitness', '#lifestyle'],
            'education': ['#education', '#learning', '#knowledge', '#tips'],
            'entertainment': ['#entertainment', '#fun', '#comedy', '#viral'],
            'news': ['#news', '#breaking', '#current', '#update'],
            'sports': ['#sports', '#fitness', '#athlete', '#competition'],
            'travel': ['#travel', '#adventure', '#explore', '#wanderlust'],
            'food': ['#food', '#cooking', '#recipe', '#delicious'],
            'fashion': ['#fashion', '#style', '#outfit', '#trend']
        }
        
        # Check for topic keywords in text
        for topic, hashtags in topic_categories.items():
            if topic in text or any(word in text for word in [topic, topic + 's']):
                topic_hashtags.extend(hashtags[:2])  # Add first 2 hashtags from category
                break
        
        return topic_hashtags
    
    def _get_platform_hashtags(self) -> List[str]:
        """
        Get platform-specific hashtags for social media
        
        Returns:
            List of platform hashtags
        """
        return [
            "#fyp",
            "#viral",
            "#trending",
            "#shorts",
            "#reels",
            "#tiktok"
        ]
    
    def extract_keywords(self, segment: TopicSegment) -> List[str]:
        """
        Explicit fallback keyword extraction when LLM unavailable
        
        Uses heuristic-based extraction from segment text including:
        - Named entities from spaCy
        - High-frequency meaningful words  
        - Topic-relevant terms from segment context
        
        Args:
            segment: Topic segment
            
        Returns:
            List of extracted keywords
        """
        try:
            logger.debug("Extracting keywords from segment",
                        segment_start_ms=segment.start_ms)
            
            text = segment.text
            keywords = []
            
            # Method 1: Named entity extraction with spaCy
            if self.nlp is not None:
                spacy_keywords = self._extract_spacy_entities(text)
                keywords.extend(spacy_keywords)
            
            # Method 2: High-frequency meaningful words
            frequency_keywords = self._extract_frequency_keywords(text)
            keywords.extend(frequency_keywords)
            
            # Method 3: Pattern-based extraction
            pattern_keywords = self._extract_pattern_keywords(text)
            keywords.extend(pattern_keywords)
            
            # Remove duplicates and filter
            unique_keywords = []
            seen = set()
            
            for keyword in keywords:
                keyword_lower = keyword.lower()
                if (keyword_lower not in seen and 
                    keyword_lower not in self.stop_words and
                    len(keyword) >= 3):
                    unique_keywords.append(keyword)
                    seen.add(keyword_lower)
            
            # Sort by relevance (simple heuristic: longer words first, then alphabetical)
            unique_keywords.sort(key=lambda x: (-len(x), x.lower()))
            
            result = unique_keywords[:10]  # Return top 10 keywords
            
            logger.debug("Keywords extracted", keywords=result)
            return result
            
        except Exception as e:
            logger.error("Keyword extraction failed", error=str(e))
            return []
    
    def _extract_spacy_entities(self, text: str) -> List[str]:
        """
        Extract named entities using spaCy
        
        Args:
            text: Input text
            
        Returns:
            List of entity keywords
        """
        try:
            doc = self.nlp(text)
            entities = []
            
            for ent in doc.ents:
                # Focus on relevant entity types
                if ent.label_ in ['PERSON', 'ORG', 'GPE', 'PRODUCT', 'EVENT', 'WORK_OF_ART']:
                    # Clean entity text
                    entity_text = ent.text.strip()
                    if len(entity_text) >= 3 and entity_text.isalpha():
                        entities.append(entity_text)
            
            return entities[:5]  # Top 5 entities
            
        except Exception as e:
            logger.debug("spaCy entity extraction failed", error=str(e))
            return []
    
    def _extract_frequency_keywords(self, text: str) -> List[str]:
        """
        Extract high-frequency meaningful words
        
        Args:
            text: Input text
            
        Returns:
            List of frequency-based keywords
        """
        # Tokenize and clean words
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        
        # Filter out stop words
        meaningful_words = [word for word in words if word not in self.stop_words]
        
        # Count frequencies
        word_counts = Counter(meaningful_words)
        
        # Get most common words
        common_words = [word for word, count in word_counts.most_common(10) if count >= 2]
        
        return common_words
    
    def _extract_pattern_keywords(self, text: str) -> List[str]:
        """
        Extract keywords using pattern matching
        
        Args:
            text: Input text
            
        Returns:
            List of pattern-based keywords
        """
        keywords = []
        
        # Extract words following key patterns
        for pattern_name, pattern in self.key_phrase_patterns.items():
            matches = pattern.findall(text)
            keywords.extend(matches)
        
        # Extract capitalized words (potential proper nouns)
        capitalized_words = re.findall(r'\b[A-Z][a-z]{2,}\b', text)
        keywords.extend(capitalized_words[:5])
        
        return keywords
    
    @with_clip_resource_management("llm")
    def _call_ollama_api(self, prompt: str, max_retries: int = 2) -> Optional[str]:
        """
        Call Ollama API for LLM inference with retry mechanism
        
        Args:
            prompt: Input prompt
            max_retries: Maximum number of retry attempts
            
        Returns:
            LLM response text or None if failed
            
        Raises:
            LLMError: If all retry attempts fail
        """
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                logger.debug("Attempting Ollama API call", 
                           attempt=attempt + 1, 
                           max_attempts=max_retries + 1)
                
                # Prepare Ollama API request
                payload = {
                    "model": self.llm_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,  # Moderate creativity for engaging content
                        "top_p": 0.9,
                        "max_tokens": 100  # Reasonable limit for titles/captions
                    }
                }
                
                # Use subprocess to call curl
                cmd = [
                    "curl", "-s", "-X", "POST",
                    "http://localhost:11434/api/generate",
                    "-H", "Content-Type: application/json",
                    "-d", json.dumps(payload),
                    "--max-time", str(self.llm_timeout)
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=self.llm_timeout + 5)
                
                if result.returncode != 0:
                    error_msg = f"Ollama API call failed with return code {result.returncode}: {result.stderr}"
                    last_error = LLMError(error_msg, model_name=self.llm_model, operation="generate")
                    logger.warning("Ollama API call failed", 
                                 attempt=attempt + 1,
                                 return_code=result.returncode,
                                 stderr=result.stderr)
                    continue
                
                # Parse JSON response
                try:
                    response_data = json.loads(result.stdout)
                except json.JSONDecodeError as e:
                    error_msg = f"Failed to parse Ollama response: {str(e)}"
                    last_error = LLMError(error_msg, model_name=self.llm_model, operation="parse_response")
                    logger.warning("Failed to parse Ollama response", 
                                 attempt=attempt + 1,
                                 error=str(e))
                    continue
                
                if "response" in response_data:
                    response_text = response_data["response"].strip()
                    if response_text:
                        logger.debug("Ollama API call successful", 
                                   attempt=attempt + 1,
                                   response_length=len(response_text))
                        return response_text
                    else:
                        error_msg = "Ollama returned empty response"
                        last_error = LLMError(error_msg, model_name=self.llm_model, operation="empty_response")
                        logger.warning("Ollama returned empty response", attempt=attempt + 1)
                        continue
                else:
                    error_msg = f"Unexpected Ollama response format: {response_data}"
                    last_error = LLMError(error_msg, model_name=self.llm_model, operation="unexpected_format")
                    logger.warning("Unexpected Ollama response format", 
                                 attempt=attempt + 1,
                                 response=response_data)
                    continue
                    
            except subprocess.TimeoutExpired:
                error_msg = f"Ollama API call timed out after {self.llm_timeout} seconds"
                last_error = LLMError(error_msg, model_name=self.llm_model, operation="timeout")
                logger.warning("Ollama API call timed out", 
                             attempt=attempt + 1,
                             timeout=self.llm_timeout)
                continue
            except Exception as e:
                error_msg = f"Unexpected error during Ollama API call: {str(e)}"
                last_error = LLMError(error_msg, model_name=self.llm_model, operation="unexpected_error")
                logger.error("Unexpected error during Ollama API call", 
                           attempt=attempt + 1,
                           error=str(e))
                continue
        
        # All attempts failed
        if last_error:
            logger.error("All Ollama API attempts failed, falling back to keyword extraction",
                       max_attempts=max_retries + 1,
                       final_error=str(last_error))
        
        return None
    
    def generate_metadata(self, segment: TopicSegment) -> GeneratedMetadata:
        """
        Generate complete metadata for a segment
        
        Args:
            segment: Topic segment to generate metadata for
            
        Returns:
            Complete generated metadata
        """
        try:
            logger.info("Generating complete metadata for segment",
                       segment_start_ms=segment.start_ms,
                       segment_duration_s=segment.duration_ms / 1000)
            
            # Extract keywords first (used by other methods)
            keywords = self.extract_keywords(segment)
            
            # Generate title
            title = self.generate_title(segment)
            
            # Generate caption
            caption = self.generate_caption(segment)
            
            # Generate hashtags
            hashtags = self.generate_hashtags(segment, keywords)
            
            # Determine generation method
            generation_method = "llm" if self.llm_enabled else "fallback"
            
            metadata = GeneratedMetadata(
                title=title,
                caption=caption,
                hashtags=hashtags,
                keywords=keywords,
                generation_method=generation_method,
                language="en"  # TODO: Detect language from segment
            )
            
            logger.info("Metadata generation completed",
                       title_length=len(title),
                       caption_length=len(caption),
                       hashtag_count=len(hashtags),
                       keyword_count=len(keywords),
                       method=generation_method)
            
            return metadata
            
        except Exception as e:
            logger.error("Complete metadata generation failed", error=str(e))
            # Return minimal fallback metadata
            return GeneratedMetadata(
                title="Interesting Clip",
                caption="Check out this interesting moment from the episode.",
                hashtags=["#viral", "#trending", "#fyp"],
                keywords=[],
                generation_method="error_fallback",
                language="en"
            )