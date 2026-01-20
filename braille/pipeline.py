"""
Main pipeline for Braille conversion.
Implements the 2-layer mechanism requested by the user.

Layer 1: Preprocessing (Scan & Convert Braille to Text)
Layer 2: Translation (Text to Braille)
"""

from braille.preprocessor import scan_and_convert_braille_to_text
from braille.louis_adapter import translate as louis_translate

def translate_pipeline(text, force_fallback=False):
    """
    Execute the 2-layer Braille translation mechanism.
    
    Layer 1: Scan for existing Braille characters and convert to natural language.
             (e.g. '⠁' -> 'a')
    
    Layer 2: Translate the refined natural language text to Braille using the standard adapter.
             (e.g. 'a' -> '⠁')
             
    This ensures that any Braille characters accidentally present in the input 
    are normalized to text before being re-translated, preventing double-encoding
    or corruption.
    """
    if not text:
        return ""
        
    # Layer 1: Pre-process (Scan and Convert)
    layer1_output = scan_and_convert_braille_to_text(text)
    
    # Layer 2: Generate Braille (Translate)
    braille_output = louis_translate(layer1_output, force_fallback=force_fallback)
    
    return braille_output
