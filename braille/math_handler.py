"""
Math expression detection and routing for Braille conversion.
Handles basic math operators: + - * ^ / % =
Routes to appropriate UEB math table when detected.
"""

import re

# Simple math operators supported in UPSC exams
MATH_OPERATORS = r'[+\-*/^%=<>≤≥≠×÷]'

def contains_math(text):
    """
    Detect if text contains mathematical expressions.
    
    Args:
        text: String to check
        
    Returns:
        bool: True if math operators detected
    """
    if not text:
        return False
    return bool(re.search(MATH_OPERATORS, str(text)))

def is_math_heavy(text, threshold=0.3):
    """
    Determine if text is primarily mathematical.
    
    Args:
        text: String to check
        threshold: Ratio of math chars to trigger (default 0.3)
        
    Returns:
        bool: True if text is primarily math
    """
    if not text:
        return False
    
    text = str(text)
    math_chars = len(re.findall(MATH_OPERATORS, text))
    total_chars = len(text.strip())
    
    if total_chars == 0:
        return False
    
    return (math_chars / total_chars) >= threshold

def split_text_and_math(text):
    """
    Split text into alternating text and math segments.
    
    Args:
        text: String to split
        
    Returns:
        list: [(segment_type, segment_text), ...]
              segment_type is 'text' or 'math'
    """
    if not text:
        return []
    
    text = str(text)
    segments = []
    current_segment = []
    current_type = None
    
    for char in text:
        is_math_char = bool(re.match(MATH_OPERATORS, char))
        char_type = 'math' if is_math_char else 'text'
        
        if current_type is None:
            current_type = char_type
            current_segment.append(char)
        elif current_type == char_type:
            current_segment.append(char)
        else:
            # Type changed, save current segment
            if current_segment:
                segments.append((current_type, ''.join(current_segment)))
            current_segment = [char]
            current_type = char_type
    
    # Save last segment
    if current_segment:
        segments.append((current_type, ''.join(current_segment)))
    
    return segments

def should_use_math_table(text):
    """
    Decide if UEB math table should be used for this text.
    
    Args:
        text: String to check
        
    Returns:
        bool: True if math table should be used
    """
    # For exam papers, use math table only if text contains operators
    # and is reasonably short (likely a formula, not narrative)
    if not contains_math(text):
        return False
    
    text = str(text).strip()
    
    # Very short expressions with math - likely formulas
    if len(text) < 50 and contains_math(text):
        return True
    
    # Math-heavy text
    if is_math_heavy(text, threshold=0.2):
        return True
    
    return False
