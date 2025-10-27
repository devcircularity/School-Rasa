"""
Utility functions for Rasa actions
"""
import re
from typing import Optional

def normalize_level_label(text: str) -> str:
    """
    Normalize class level labels to consistent format.
    Maps: grade/form/jss/standard → class
    
    Examples:
        "Grade 8" → "Class 8"
        "Form 2" → "Form 2" (keep Form for secondary)
        "JSS 1" → "JSS 1" (keep JSS identifier)
        "grade 6" → "Class 6"
    """
    if not text:
        return text
    
    text = text.strip()
    
    # Map common synonyms to "Class" at the beginning
    synonyms = {
        r'\bgrade\s+': 'Class ',
        r'\bstandard\s+': 'Class ',
        r'\byear\s+': 'Class ',
        r'\blevel\s+': 'Class ',
    }
    
    for pattern, replacement in synonyms.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    # Capitalize properly
    return text.title()


def normalize_class_reference(text: str) -> str:
    """
    Normalize any class reference in free text.
    Handles: "in grade 8", "for form 2", etc.
    """
    if not text:
        return text
    
    # Replace grade/standard/year with class
    text = re.sub(r'\bgrade\b', 'class', text, flags=re.IGNORECASE)
    text = re.sub(r'\bstandard\b', 'class', text, flags=re.IGNORECASE)
    text = re.sub(r'\byear\b', 'class', text, flags=re.IGNORECASE)
    
    return text


def extract_level_number(text: str) -> Optional[str]:
    """
    Extract just the level number from text like:
    - "Grade 8" → "8"
    - "Class 5 Blue" → "5"
    - "Form 2A" → "2"
    - "JSS 1" → "1"
    """
    if not text:
        return None
    
    # Pattern: word + number
    pattern = r'(?:class|grade|form|jss|standard|year|pp|level)\s*(\d+)'
    match = re.search(pattern, text, re.IGNORECASE)
    
    if match:
        return match.group(1)
    
    # If no keyword found, try just extracting first number
    number_match = re.search(r'(\d+)', text)
    return number_match.group(1) if number_match else None


def normalize_stream_name(stream: str) -> str:
    """
    Normalize stream names consistently.
    - Single letters: uppercase (A, B, X)
    - Words: title case (Red, Blue, North)
    """
    if not stream:
        return stream
    
    stream = stream.strip()
    
    # Single letter: uppercase
    if len(stream) == 1:
        return stream.upper()
    
    # Multiple letters: title case
    return stream.title()