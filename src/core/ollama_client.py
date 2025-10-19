"""
Ollama Client for AI Analysis

Provides a simple interface to Ollama for generating summaries, 
takeaways, analysis, and extracting topics from transcripts.
"""

import httpx
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from .logging import get_logger
from .exceptions import ProcessingError

logger = get_logger('pipeline.ollama_client')


@dataclass
class OllamaAnalysis:
    """Result of Ollama AI analysis"""
    executive_summary: str
    key_takeaways: List[str]
    deep_analysis: str
    topics: List[str]
    segment_titles: List[Dict[str, Any]]
    show_name: str  # Extracted show name from transcript
    host_name: str  # Extracted host name from transcript
    processing_time: float


class OllamaClient:
    """
    Client for interacting with Ollama API
    
    Provides methods for generating AI analysis including:
    - Executive summaries
    - Key takeaways
    - Deep analysis
    - Topic extraction
    - Segment title generation
    """
    
    def __init__(self, host: str = "http://localhost:11434", 
                 model: str = "llama3.1:latest",
                 timeout: int = 300):
        """
        Initialize Ollama client
        
        Args:
            host: Ollama server URL
            model: Model to use for generation
            timeout: Request timeout in seconds
        """
        self.host = host.rstrip('/')
        self.model = model
        self.timeout = timeout
        self.logger = logger
        
        # Verify connection
        self._verify_connection()
    
    def _verify_connection(self) -> None:
        """Verify that Ollama is accessible"""
        try:
            response = httpx.get(f"{self.host}/api/tags", timeout=5)
            if response.status_code != 200:
                raise ProcessingError(
                    f"Ollama server returned status {response.status_code}",
                    stage="ollama_init"
                )
            
            # Check if our model is available
            data = response.json()
            models = [m.get('name', '') for m in data.get('models', [])]
            
            if not any(self.model in m for m in models):
                self.logger.warning(
                    f"Model {self.model} not found in Ollama. Available models: {models}",
                    available_models=models,
                    requested_model=self.model
                )
            else:
                self.logger.info(
                    "Ollama connection verified",
                    host=self.host,
                    model=self.model
                )
        except httpx.RequestError as e:
            raise ProcessingError(
                f"Cannot connect to Ollama at {self.host}. Is Ollama running?",
                stage="ollama_init"
            ) from e
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Generate text using Ollama
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt for context
            
        Returns:
            Generated text
        """
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "top_p": 0.9
                }
            }
            
            if system_prompt:
                payload["system"] = system_prompt
            
            self.logger.debug(
                "Sending request to Ollama",
                prompt_length=len(prompt),
                model=self.model
            )
            
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.host}/api/generate",
                    json=payload
                )
                
                if response.status_code != 200:
                    raise ProcessingError(
                        f"Ollama API error: {response.status_code} - {response.text}",
                        stage="ollama_generate"
                    )
                
                result = response.json()
                generated_text = result.get('response', '').strip()
                
                self.logger.debug(
                    "Received response from Ollama",
                    response_length=len(generated_text)
                )
                
                return generated_text
        
        except httpx.TimeoutException:
            raise ProcessingError(
                f"Ollama request timed out after {self.timeout}s",
                stage="ollama_generate"
            )
        except Exception as e:
            raise ProcessingError(
                f"Ollama generation failed: {str(e)}",
                stage="ollama_generate"
            ) from e
    
    def generate_executive_summary(self, transcript: str) -> str:
        """
        Generate a 2-3 paragraph executive summary
        
        Args:
            transcript: Full transcript text (will be truncated if too long)
            
        Returns:
            Executive summary text
        """
        self.logger.info("Generating executive summary")
        
        # Limit transcript length to avoid token limits
        max_chars = 15000
        truncated_transcript = transcript[:max_chars]
        if len(transcript) > max_chars:
            truncated_transcript += "... [transcript continues]"
        
        prompt = f"""You are a professional news analyst. Analyze this transcript and provide a concise, engaging 2-3 paragraph executive summary that captures the essence of the discussion.

Transcript:
{truncated_transcript}

Provide only the summary, no preamble."""
        
        return self.generate(prompt)
    
    def extract_key_takeaways(self, transcript: str, count: int = 7) -> List[str]:
        """
        Extract key takeaways from transcript
        
        Args:
            transcript: Full transcript text
            count: Number of takeaways to extract
            
        Returns:
            List of key takeaway strings
        """
        self.logger.info(f"Extracting {count} key takeaways")
        
        # Limit transcript length
        max_chars = 15000
        truncated_transcript = transcript[:max_chars]
        if len(transcript) > max_chars:
            truncated_transcript += "... [transcript continues]"
        
        prompt = f"""Analyze this transcript and extract {count} key takeaways or insights. Format as a simple list, one per line, starting with a dash.

Transcript:
{truncated_transcript}

Provide only the list, no preamble or conclusion."""
        
        response = self.generate(prompt)
        
        # Parse the response into a list
        takeaways = []
        for line in response.split('\n'):
            line = line.strip()
            if line and (line.startswith('-') or line.startswith('•') or line.startswith('*')):
                # Remove list marker
                takeaway = line.lstrip('-•* ').strip()
                if takeaway:
                    takeaways.append(takeaway)
        
        # If parsing failed, try splitting by newlines
        if not takeaways:
            takeaways = [line.strip() for line in response.split('\n') 
                        if line.strip() and len(line.strip()) > 10]
        
        return takeaways[:count]
    
    def generate_deep_analysis(self, transcript: str) -> str:
        """
        Generate deep news analysis
        
        Args:
            transcript: Full transcript text
            
        Returns:
            Deep analysis text
        """
        self.logger.info("Generating deep analysis")
        
        # Limit transcript length
        max_chars = 15000
        truncated_transcript = transcript[:max_chars]
        if len(transcript) > max_chars:
            truncated_transcript += "... [transcript continues]"
        
        prompt = f"""You are a news analyst. Analyze this transcript for:
1. Main themes and topics discussed
2. Significance and implications
3. Context and background
4. Potential impact or consequences

Provide a structured analysis in 2-3 paragraphs.

Transcript:
{truncated_transcript}

Provide only the analysis, no preamble."""
        
        return self.generate(prompt)
    
    def extract_show_name(self, transcript: str) -> str:
        """
        Extract show name from transcript introduction
        
        Args:
            transcript: Full transcript text
            
        Returns:
            Show name or empty string
        """
        self.logger.info("Extracting show name from transcript")
        
        # Use first 1000 chars (usually contains intro)
        intro = transcript[:1000]
        
        prompt = f"""Extract the show/program name from this transcript introduction. Return ONLY the show name, nothing else.

Transcript intro:
{intro}

Show name:"""
        
        response = self.generate(prompt).strip()
        
        # Clean up response
        show_name = response.strip('"\'.,;:')
        
        # Validate (reasonable length)
        if show_name and 3 < len(show_name) < 100:
            self.logger.info(f"Extracted show name: {show_name}")
            return show_name
        
        self.logger.warning(f"Could not extract valid show name from transcript")
        return ""
    
    def extract_host_name(self, transcript: str) -> str:
        """
        Extract host name from transcript introduction
        
        Args:
            transcript: Full transcript text
            
        Returns:
            Host name or empty string
        """
        self.logger.info("Extracting host name from transcript")
        
        # Use first 1000 chars (usually contains intro)
        intro = transcript[:1000]
        
        prompt = f"""Extract the host's full name from this transcript introduction. Return ONLY the host's name, nothing else.

Transcript intro:
{intro}

Host name:"""
        
        response = self.generate(prompt).strip()
        
        # Clean up response
        host_name = response.strip('"\'.,;:')
        
        # Validate (reasonable length)
        if host_name and 3 < len(host_name) < 100:
            self.logger.info(f"Extracted host name: {host_name}")
            return host_name
        
        self.logger.warning(f"Could not extract valid host name from transcript")
        return ""
    
    def extract_topics(self, transcript: str, count: int = 10) -> List[str]:
        """
        Extract key topics/keywords from transcript
        
        Args:
            transcript: Full transcript text
            count: Number of topics to extract
            
        Returns:
            List of topic strings
        """
        self.logger.info(f"Extracting {count} topics")
        
        # Limit transcript length
        max_chars = 15000
        truncated_transcript = transcript[:max_chars]
        if len(transcript) > max_chars:
            truncated_transcript += "... [transcript continues]"
        
        prompt = f"""Extract {count} key topics, themes, or keywords from this transcript. Provide only the topics as a comma-separated list.

Transcript:
{truncated_transcript}

Provide only the comma-separated list, nothing else."""
        
        response = self.generate(prompt)
        
        # Parse topics
        topics = [topic.strip() for topic in response.split(',') if topic.strip()]
        
        # Clean up topics (remove quotes, extra whitespace)
        cleaned_topics = []
        for topic in topics:
            topic = topic.strip('"\'')
            topic = topic.strip()
            if topic and len(topic) < 50:  # Reasonable topic length
                cleaned_topics.append(topic)
        
        return cleaned_topics[:count]
    
    def generate_segment_title(self, segment_text: str) -> str:
        """
        Generate a short title for a transcript segment
        
        Args:
            segment_text: Text of the segment
            
        Returns:
            Generated title (3-6 words)
        """
        # Limit segment text
        max_chars = 500
        truncated_text = segment_text[:max_chars]
        
        prompt = f"""Generate a short, descriptive title (3-6 words) for this transcript segment. Provide ONLY the title, nothing else.

Segment text:
{truncated_text}

Title:"""
        
        response = self.generate(prompt).strip()
        
        # Clean up the title
        title = response.strip('"\'')
        title = title.replace('Title:', '').strip()
        
        # Validate title length
        if len(title) > 100:
            title = ' '.join(title.split()[:6])  # Limit to 6 words
        
        return title if title else "Discussion Segment"
    
    def analyze_transcript(self, transcript: str, episode_id: str) -> OllamaAnalysis:
        """
        Perform complete AI analysis on transcript
        
        Args:
            transcript: Full transcript text
            episode_id: Episode identifier for logging
            
        Returns:
            OllamaAnalysis with all generated content
        """
        import time
        start_time = time.time()
        
        self.logger.info(
            "Starting complete transcript analysis",
            episode_id=episode_id,
            transcript_length=len(transcript)
        )
        
        try:
            # Extract show name and host from transcript
            show_name = self.extract_show_name(transcript)
            host_name = self.extract_host_name(transcript)
            
            # Generate executive summary
            summary = self.generate_executive_summary(transcript)
            
            # Extract key takeaways
            takeaways = self.extract_key_takeaways(transcript, count=7)
            
            # Generate deep analysis
            analysis = self.generate_deep_analysis(transcript)
            
            # Extract topics
            topics = self.extract_topics(transcript, count=10)
            
            # Generate segment titles (create segments from transcript)
            segments = self._create_transcript_segments(transcript)
            segment_titles = []
            for i, segment in enumerate(segments[:20], 1):  # Limit to 20 segments
                title = self.generate_segment_title(segment['text'])
                segment_titles.append({
                    'segment': i,
                    'title': title,
                    'text': segment['text'],
                    'start_line': i * 10,
                    'end_line': (i + 1) * 10
                })
            
            processing_time = time.time() - start_time
            
            self.logger.info(
                "Complete transcript analysis finished",
                episode_id=episode_id,
                processing_time=processing_time,
                show_name=show_name,
                host_name=host_name,
                summary_length=len(summary),
                takeaways_count=len(takeaways),
                topics_count=len(topics),
                segments_count=len(segment_titles)
            )
            
            return OllamaAnalysis(
                executive_summary=summary,
                key_takeaways=takeaways,
                deep_analysis=analysis,
                topics=topics,
                segment_titles=segment_titles,
                show_name=show_name,
                host_name=host_name,
                processing_time=processing_time
            )
        
        except Exception as e:
            self.logger.error(
                "Transcript analysis failed",
                episode_id=episode_id,
                error=str(e)
            )
            raise
    
    def _create_transcript_segments(self, transcript: str, chunk_size: int = 10) -> List[Dict[str, str]]:
        """
        Split transcript into segments for title generation
        
        Args:
            transcript: Full transcript
            chunk_size: Number of lines per segment
            
        Returns:
            List of segment dictionaries with text
        """
        lines = [line.strip() for line in transcript.split('\n') if line.strip()]
        segments = []
        
        for i in range(0, len(lines), chunk_size):
            chunk = lines[i:i + chunk_size]
            segment_text = ' '.join(chunk)
            segments.append({'text': segment_text})
        
        return segments
