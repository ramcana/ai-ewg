"""
Journalistic Article Formatter

Transforms transcript + AI analysis into structured journalistic article format:
- Article-style narrative
- Section headings from segment titles
- Inline references
- Professional formatting
"""

from typing import List, Dict, Any
import re


class JournalisticFormatter:
    """Formats transcripts as professional journalistic articles"""
    
    def __init__(self):
        pass
    
    def format_article(
        self,
        transcript: str,
        ai_analysis: Dict[str, Any],
        episode_metadata: Dict[str, Any]
    ) -> str:
        """
        Format transcript as journalistic article
        
        Args:
            transcript: Cleaned transcript text
            ai_analysis: AI enrichment data
            episode_metadata: Episode metadata
            
        Returns:
            HTML-formatted article
        """
        sections = []
        
        # Lead paragraph (from executive summary)
        if ai_analysis.get('executive_summary'):
            sections.append(self._format_lead(ai_analysis['executive_summary']))
        
        # Key points box
        if ai_analysis.get('key_takeaways'):
            sections.append(self._format_key_points(ai_analysis['key_takeaways']))
        
        # Main article body with segment headings
        if ai_analysis.get('segment_titles'):
            sections.append(self._format_segmented_article(
                transcript,
                ai_analysis['segment_titles']
            ))
        else:
            # Fallback: format as paragraphs
            sections.append(self._format_simple_article(transcript))
        
        # Analysis section
        if ai_analysis.get('deep_analysis'):
            sections.append(self._format_analysis_box(ai_analysis['deep_analysis']))
        
        return '\n\n'.join(sections)
    
    def _format_lead(self, executive_summary: str) -> str:
        """Format executive summary as article lead"""
        return f'''<div class="article-lead">
    <p class="lead-paragraph">{executive_summary}</p>
</div>'''
    
    def _format_key_points(self, takeaways: List[str]) -> str:
        """Format key takeaways as highlighted box"""
        items = '\n'.join([f'        <li>{self._escape_html(t)}</li>' for t in takeaways])
        
        return f'''<div class="key-points-box">
    <h3>Key Points</h3>
    <ul class="key-points-list">
{items}
    </ul>
</div>'''
    
    def _format_segmented_article(
        self,
        transcript: str,
        segment_titles: List[Dict[str, Any]]
    ) -> str:
        """
        Format article with section headings from AI segment titles
        
        Args:
            transcript: Full transcript
            segment_titles: List of {title, start_line, end_line}
            
        Returns:
            HTML article with sections
        """
        # Split transcript into lines
        lines = transcript.split('\n')
        
        sections = []
        sections.append('<div class="article-body">')
        
        for i, segment in enumerate(segment_titles):
            title = segment.get('title', f'Section {i+1}')
            start_line = segment.get('start_line', 0)
            end_line = segment.get('end_line', len(lines))
            
            # Get segment text
            segment_lines = lines[start_line:end_line]
            segment_text = ' '.join(segment_lines).strip()
            
            if not segment_text:
                continue
            
            # Format as article section
            sections.append(f'<div class="article-section">')
            sections.append(f'    <h3 class="section-heading">{self._escape_html(title)}</h3>')
            
            # Split into paragraphs (every 3-4 sentences)
            paragraphs = self._split_into_paragraphs(segment_text, sentences_per_para=3)
            
            for para in paragraphs:
                sections.append(f'    <p class="article-paragraph">{self._escape_html(para)}</p>')
            
            sections.append('</div>')
        
        sections.append('</div>')
        
        return '\n'.join(sections)
    
    def _format_simple_article(self, transcript: str) -> str:
        """Fallback: Format transcript as simple paragraphs"""
        paragraphs = self._split_into_paragraphs(transcript, sentences_per_para=4)
        
        html_paragraphs = [
            f'<p class="article-paragraph">{self._escape_html(p)}</p>'
            for p in paragraphs
        ]
        
        return f'''<div class="article-body">
{''.join(html_paragraphs)}
</div>'''
    
    def _format_analysis_box(self, analysis: str) -> str:
        """Format deep analysis as highlighted box"""
        return f'''<div class="analysis-box">
    <h3>Analysis & Context</h3>
    <p class="analysis-text">{self._escape_html(analysis)}</p>
</div>'''
    
    def _split_into_paragraphs(
        self,
        text: str,
        sentences_per_para: int = 4
    ) -> List[str]:
        """Split text into paragraphs"""
        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        paragraphs = []
        current_para = []
        
        for sentence in sentences:
            if not sentence.strip():
                continue
            
            current_para.append(sentence.strip())
            
            if len(current_para) >= sentences_per_para:
                paragraphs.append(' '.join(current_para))
                current_para = []
        
        # Add remaining
        if current_para:
            paragraphs.append(' '.join(current_para))
        
        return paragraphs
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters"""
        if not text:
            return ''
        return (
            text.replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#39;')
        )
    
    def get_article_css(self) -> str:
        """
        Get CSS styles for journalistic article format
        
        Returns:
            CSS string
        """
        return """
/* Journalistic Article Styles */
.article-lead {
    background: #f8f9fa;
    border-left: 4px solid #0066cc;
    padding: 1.5rem;
    margin: 2rem 0;
    font-size: 1.2rem;
    line-height: 1.8;
}

.lead-paragraph {
    font-weight: 500;
    color: #2c3e50;
    margin: 0;
}

.key-points-box {
    background: #e8f5e9;
    border-left: 4px solid #4caf50;
    padding: 1.5rem;
    margin: 2rem 0;
}

.key-points-box h3 {
    margin-top: 0;
    color: #2e7d32;
    font-size: 1.3rem;
}

.key-points-list {
    margin: 1rem 0 0 0;
    padding-left: 1.5rem;
}

.key-points-list li {
    margin-bottom: 0.75rem;
    line-height: 1.6;
    color: #1b5e20;
}

.article-body {
    margin: 2rem 0;
}

.article-section {
    margin-bottom: 3rem;
}

.section-heading {
    color: #1976d2;
    font-size: 1.5rem;
    font-weight: 600;
    margin-bottom: 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 2px solid #e3f2fd;
}

.article-paragraph {
    font-size: 1.1rem;
    line-height: 1.8;
    margin-bottom: 1.25rem;
    color: #37474f;
    text-align: justify;
}

.analysis-box {
    background: #fff3e0;
    border-left: 4px solid #ff9800;
    padding: 1.5rem;
    margin: 2rem 0;
}

.analysis-box h3 {
    margin-top: 0;
    color: #e65100;
    font-size: 1.3rem;
}

.analysis-text {
    line-height: 1.7;
    color: #4e342e;
}

/* Make article more newspaper-like */
@media (min-width: 768px) {
    .article-paragraph {
        column-count: 1;
        text-indent: 0;
    }
}
"""
