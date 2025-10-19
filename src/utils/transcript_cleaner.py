"""
Transcript Cleaning Utilities

Fixes common Whisper hallucination issues:
- Repetitive text (e.g., "I don't know" repeated 20 times)
- Stuttering/duplicated phrases
- Cleaning artifacts

"""

import re
from typing import List


def remove_repetitions(text: str, max_repeats: int = 3) -> str:
    """
    Remove repetitive phrases from transcript
    
    Args:
        text: Input text
        max_repeats: Maximum allowed consecutive repeats
        
    Returns:
        Cleaned text
    """
    # Split into sentences
    sentences = re.split(r'([.!?]\s+)', text)
    
    cleaned = []
    last_sentences = []
    
    for i, sentence in enumerate(sentences):
        # Skip empty
        if not sentence.strip():
            continue
        
        # Keep punctuation
        if sentence.strip() in '.!?':
            if cleaned:
                cleaned[-1] += sentence
            continue
        
        # Normalize for comparison
        normalized = sentence.lower().strip()
        
        # Check if this sentence repeats too many times
        if normalized in last_sentences[-max_repeats:]:
            # Skip this repetition
            continue
        
        cleaned.append(sentence)
        last_sentences.append(normalized)
        
        # Keep only recent history
        if len(last_sentences) > max_repeats * 2:
            last_sentences.pop(0)
    
    return ''.join(cleaned)


def remove_phrase_repetitions(text: str, min_phrase_length: int = 10) -> str:
    """
    Remove repeated phrases within sentences
    
    Example: "I don't know. I don't know. I don't know." -> "I don't know."
    
    Args:
        text: Input text
        min_phrase_length: Minimum phrase length to consider
        
    Returns:
        Cleaned text
    """
    # Pattern: Find sequences like "phrase. phrase. phrase."
    # where phrase repeats 3+ times
    pattern = r'\b(\w+(?:\s+\w+){1,8})\.\s+(?:\1\.\s+){2,}'
    
    def replace_repetition(match):
        phrase = match.group(1)
        return f"{phrase}. "
    
    cleaned = re.sub(pattern, replace_repetition, text, flags=re.IGNORECASE)
    
    # Also handle comma-separated repetitions
    # "word, word, word, word" -> "word"
    pattern2 = r'\b(\w+)(?:,\s+\1){3,}'
    
    def replace_comma_repetition(match):
        word = match.group(1)
        return word
    
    cleaned = re.sub(pattern2, replace_comma_repetition, cleaned, flags=re.IGNORECASE)
    
    return cleaned


def clean_transcript(text: str) -> str:
    """
    Apply all cleaning operations to transcript
    
    Args:
        text: Raw transcript text
        
    Returns:
        Cleaned transcript text
    """
    # Remove phrase repetitions first
    text = remove_phrase_repetitions(text)
    
    # Remove sentence repetitions
    text = remove_repetitions(text, max_repeats=2)
    
    # Clean up multiple spaces
    text = re.sub(r'\s+', ' ', text)
    
    # Clean up multiple periods
    text = re.sub(r'\.{3,}', '...', text)
    
    # Fix spacing around punctuation
    text = re.sub(r'\s+([.,!?;:])', r'\1', text)
    text = re.sub(r'([.,!?;:])\s+', r'\1 ', text)
    
    # Remove trailing/leading whitespace
    text = text.strip()
    
    return text


def split_into_paragraphs(text: str, sentences_per_paragraph: int = 4) -> List[str]:
    """
    Split transcript into readable paragraphs
    
    Args:
        text: Transcript text
        sentences_per_paragraph: Sentences per paragraph
        
    Returns:
        List of paragraph strings
    """
    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    paragraphs = []
    current_paragraph = []
    
    for sentence in sentences:
        if not sentence.strip():
            continue
        
        current_paragraph.append(sentence)
        
        if len(current_paragraph) >= sentences_per_paragraph:
            paragraphs.append(' '.join(current_paragraph))
            current_paragraph = []
    
    # Add remaining sentences
    if current_paragraph:
        paragraphs.append(' '.join(current_paragraph))
    
    return paragraphs
