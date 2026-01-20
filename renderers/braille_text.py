"""
High-level text to Braille conversion.
Handles question paper text structure.
"""

from braille.louis_adapter import get_status
from braille.pipeline import translate_pipeline

def text_to_braille(text):
    """
    Convert text to Braille using the 2-layer pipeline.
    
    Layer 1: Scan & Convert existing Braille to Natural Language
    Layer 2: Generate fresh Braille
    
    Args:
        text: String to convert
        
    Returns:
        str: Braille text
    """
    return translate_pipeline(text)

def convert_question(question_text, clean_text_fn):
    """
    Convert a question to Braille with proper cleaning.
    
    Args:
        question_text: Question text
        clean_text_fn: Function to clean Unicode chars
        
    Returns:
        str: Braille question text
    """
    cleaned = clean_text_fn(question_text)
    return translate_pipeline(cleaned)

def convert_option(option_text, clean_text_fn):
    """
    Convert an option to Braille with proper cleaning.
    
    Args:
        option_text: Option text
        clean_text_fn: Function to clean Unicode chars
        
    Returns:
        str: Braille option text
    """
    cleaned = clean_text_fn(option_text)
    return translate_pipeline(cleaned)

def convert_passage(passage_text, clean_text_fn):
    """
    Convert a passage to Braille with proper cleaning.
    
    Args:
        passage_text: Passage text
        clean_text_fn: Function to clean Unicode chars
        
    Returns:
        str: Braille passage text
    """
    cleaned = clean_text_fn(passage_text)
    return translate_pipeline(cleaned)

def convert_statement(statement_text, clean_text_fn):
    """
    Convert a statement to Braille with proper cleaning.
    
    Args:
        statement_text: Statement text
        clean_text_fn: Function to clean Unicode chars
        
    Returns:
        str: Braille statement text
    """
    cleaned = clean_text_fn(statement_text)
    return translate_pipeline(cleaned)

def get_braille_status():
    """
    Get current Braille system status for diagnostics.
    
    Returns:
        dict: Status info
    """
    return get_status()
